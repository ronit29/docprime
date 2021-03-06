from uuid import UUID
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as lab_models
from ondoc.authentication import models as auth_models
from ondoc.provider import models as prov_models
from ondoc.communications import models as comm_models
from ondoc.notification import models as notif_models
from ondoc.matrix.tasks import decrypted_invoice_pdfs, decrypted_prescription_pdfs
from django.utils.safestring import mark_safe
from . import serializers
from ondoc.api.v1.doctor import serializers as v1_doc_serializers
from ondoc.api.v1 import utils as v1_utils
from ondoc.sms.api import send_otp
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from ondoc.authentication.backends import JWTAuthentication
from django.db import transaction
from django.db.models import Q, Value, Case, When, F
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
from ondoc.procedure.models import Procedure
from django.contrib.auth import get_user_model
from django.conf import settings
import datetime, logging, re, random, jwt, os, hashlib
import json, decimal, requests
from django.utils import timezone

from ondoc.diagnostic.models import LabAppointment
from ondoc.doctor.models import OpdAppointment, DoctorClinic
from ondoc.communications.models import SMSNotification
from ondoc.notification.models import NotificationAction
from ondoc.api.v1.doctor import serializers as doctor_serializers
from ondoc.api.v1.diagnostic import serializers as diagnostic_serializers


User = get_user_model()
logger = logging.getLogger(__name__)


class DoctorBillingViewSet(viewsets.GenericViewSet):
    
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

    def get_queryset(self):
        return auth_models.GenericAdmin.objects.none()

    def get_doc_dict(self, entity, pem_type):
        return {'id': entity.doctor.id,
                'name': entity.doctor.name,
                'permission_type': pem_type
               }

    def get_hos_dict(self, entity, pem_type):
        return {'id': entity.hospital.id,
                'name': entity.hospital.name,
                'permission_type': pem_type
               }

    def get_super_user_dict(self, admin, pem_type):
        assoc_docs = []
        for doc_clinic in admin.hospital.hospital_doctors.all():
            doc = self.get_doc_dict(doc_clinic, pem_type)
            assoc_docs.append(doc)
        return assoc_docs

    def get_super_user_dict_hosp(self, admin, pem_type):
        assoc_hosp = []
        for doc_clinic in admin.doctor.doctor_clinics.all():
            doc = self.get_hos_dict(doc_clinic, pem_type)
            assoc_hosp.append(doc)
        return assoc_hosp

    def get_merchant_dict(self, merchants):
        ac_number = merchants.merchant.account_number if merchants.merchant and merchants.merchant.account_number else ''
        if ac_number:
            ac_number = "*" * (len(ac_number) - 4) + ac_number[-4:]
        return {
            'account_number': ac_number,
            'pan_number': merchants.merchant.pan_number if merchants.merchant and merchants.merchant.pan_number else '',
            'name': merchants.merchant.beneficiary_name if merchants.merchant and merchants.merchant.beneficiary_name else '',
            'ifsc': merchants.merchant.ifsc_code if merchants.merchant and merchants.merchant.ifsc_code else ''}

    def get_lab_entities(self, user):
        lab_entities = dict()

        queryset = auth_models.GenericLabAdmin.objects.select_related('lab', 'lab_network').prefetch_related(
            'lab__merchant', 'lab__merchant__merchant').filter(user=user,
                                    is_disabled=False,
                                    lab__is_live=True)
        for admin in queryset.all():
            merchant_dict = None
            lname = admin.lab.name
            for merchants in admin.lab.merchant.all():
                if merchants.verified:
                    merchant_dict = self.get_merchant_dict(merchants)

            if not lab_entities.get(lname):
                lab_entities[lname] = {'type': 'lab',
                                       'id': admin.lab.id,
                                       'super_user_permission': admin.super_user_permission,
                                       'permission_type': auth_models.GenericLabAdmin.ALL if admin.super_user_permission else admin.permission_type,
                                       'merchant': merchant_dict
                                       }
            else:
                if not lab_entities[lname]['super_user_permission']:
                    if admin.super_user_permission:
                        lab_entities[lname]['super_user_permission'] = True
                        lab_entities[lname]['permission_type'] = auth_models.GenericAdmin.ALL
                    elif lab_entities[lname]['permission_type'] != admin.permission_type:
                        lab_entities[lname]['permission_type'] = auth_models.GenericAdmin.ALL

        return lab_entities

    def list(self, request):
        user = request.user

        lab_entities = dict()
        if request.query_params and 'type' in request.query_params and request.query_params.get('type') == 'doc_lab':
            lab_entities = self.get_lab_entities(user)

        queryset = auth_models.GenericAdmin.objects.select_related('doctor', 'hospital')\
                                                   .prefetch_related('hospital__hospital_doctors', 'hospital__hospital_doctors__doctor',
                                                                     'hospital__merchant', 'hospital__merchant__merchant',
                                                                     'doctor__merchant', 'doctor__merchant__merchant',
                                                                     'doctor__doctor_clinics', 'doctor__doctor_clinics__hospital') \
                            .filter(Q(user=user, is_disabled=False),
                                    (Q(entity_type=v1_utils.GenericAdminEntity.HOSPITAL, hospital__is_live=True) |
                                     Q(entity_type=v1_utils.GenericAdminEntity.DOCTOR, doctor__is_live=True)))
        entities = {}
        for admin in queryset.all():
            if admin.entity_type == v1_utils.GenericAdminEntity.HOSPITAL:
                merchant_dict = None
                hname = admin.hospital.name
                for merchants in admin.hospital.merchant.all():
                    if merchants.verified:
                        merchant_dict = self.get_merchant_dict(merchants)

                if not entities.get(hname):
                    entities[hname] = {'type': 'hospital',
                                       'id': admin.hospital.id,
                                       'super_user_permission': admin.super_user_permission,
                                       'assoc': [],
                                       'permission_type': auth_models.GenericAdmin.ALL if admin.super_user_permission else admin.permission_type,
                                       'merchant': merchant_dict
                                       }
                    if entities[hname]['super_user_permission'] or (not admin.doctor):
                        pem_type = auth_models.GenericAdmin.ALL if entities[hname]['super_user_permission'] else admin.permission_type
                        assoc_docs = self.get_super_user_dict(admin, pem_type)
                        entities[hname]['assoc'] = assoc_docs
                    else:
                        doc = self.get_doc_dict(admin, admin.permission_type)
                        entities[hname]['assoc'].append(doc)
                else:
                    if not entities[hname]['super_user_permission']:
                        if admin.super_user_permission:
                            pem_type = auth_models.GenericAdmin.ALL
                            assoc_docs = self.get_super_user_dict(admin, pem_type)
                            entities[hname]['assoc'] = assoc_docs
                            entities[hname]['super_user_permission'] = True
                            entities[hname]['permission_type'] = auth_models.GenericAdmin.ALL
                        elif not admin.super_user_permission and not admin.doctor:
                            for doc_clinic in admin.hospital.hospital_doctors.all():
                                update = False
                                for old_docs in entities[hname]['assoc']:
                                    if old_docs['id'] == doc_clinic.doctor.id and old_docs['permission_type'] != admin.permission_type:
                                        old_docs['permission_type'] = auth_models.GenericAdmin.ALL
                                        update = True
                                if not update:
                                    doc = self.get_doc_dict(doc_clinic, admin.permission_type)
                                    entities[hname]['assoc'].append(doc)
                            if entities[hname]['permission_type'] != admin.permission_type:
                                entities[hname]['permission_type'] = auth_models.GenericAdmin.ALL
                        elif not admin.super_user_permission and admin.doctor:
                            update = False
                            for old_docs in entities[hname]['assoc']:
                                if old_docs['id'] == admin.doctor.id and old_docs['permission_type'] != admin.permission_type:
                                    old_docs['permission_type'] = auth_models.GenericAdmin.ALL
                                    update = True
                            if not update:
                                doc = self.get_doc_dict(admin, admin.permission_type)
                                entities[hname]['assoc'].append(doc)

            elif admin.entity_type == v1_utils.GenericAdminEntity.DOCTOR:
                hname = admin.doctor.name
                merchant_dict = None
                for merchants in admin.doctor.merchant.all():
                    if merchants.verified:
                        merchant_dict = self.get_merchant_dict(merchants)
                if not entities.get(hname):
                    entities[hname] = {'type': 'doctor',
                                       'id': admin.doctor.id,
                                       'super_user_permission': admin.super_user_permission,
                                       'assoc': [],
                                       'permission_type': auth_models.GenericAdmin.ALL if admin.super_user_permission else admin.permission_type,
                                       'merchant': merchant_dict
                                       }
                    if entities[hname]['super_user_permission'] or (not admin.hospital):
                        pem_type = auth_models.GenericAdmin.ALL if entities[hname][
                            'super_user_permission'] else admin.permission_type
                        assoc = self.get_super_user_dict_hosp(admin, pem_type)
                        entities[hname]['assoc'] = assoc
                    else:
                        hosp = self.get_hos_dict(admin, admin.permission_type)
                        entities[hname]['assoc'].append(hosp)
                else:
                    if not entities[hname]['super_user_permission']:
                        if admin.super_user_permission:
                            pem_type = auth_models.GenericAdmin.ALL
                            assoc_hosp = self.get_super_user_dict_hosp(admin, pem_type)
                            entities[hname]['assoc'] = assoc_hosp
                            entities[hname]['super_user_permission'] = True
                            entities[hname]['permission_type'] = auth_models.GenericAdmin.ALL
                        elif not admin.super_user_permission and not admin.hospital:
                            for doc_clinic in admin.doctor.doctor_clinics.all():
                                update = False
                                for old_docs in entities[hname]['assoc']:
                                    if old_docs['id'] == doc_clinic.hospital.id and old_docs['permission_type'] != admin.permission_type:
                                        old_docs['permission_type'] = auth_models.GenericAdmin.ALL
                                        update = True
                                if not update:
                                    doc = self.get_hos_dict(doc_clinic, admin.permission_type)
                                    entities[hname]['assoc'].append(doc)
                            if entities[hname]['permission_type'] != admin.permission_type:
                                entities[hname]['permission_type'] = auth_models.GenericAdmin.ALL
                        elif not admin.super_user_permission and admin.hospital:
                            update = False
                            for old_docs in entities[hname]['assoc']:
                                if old_docs['id'] == admin.hospital.id and old_docs['permission_type'] != admin.permission_type:
                                    old_docs['permission_type'] = auth_models.GenericAdmin.ALL
                                    update = True
                            if not update:
                                doc = self.get_hos_dict(admin, admin.permission_type)
                                entities[hname]['assoc'].append(doc)
        return Response({**entities, **lab_entities})


class HospitalProviderDataViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

    def get_queryset(self):
        return None

    def list(self, request):
        queryset = auth_models.GenericAdmin.objects.filter(is_disabled=False, user=request.user)\
                                                   .select_related('hospital').prefetch_related('hospital__encrypt_details')
        all_data = {}
        for admin in queryset.all():
            if admin.hospital and (admin.hospital.id not in all_data):
                hosp_id = admin.hospital.id
                admin_data = {"name": admin.hospital.name,
                              "id": hosp_id,
                              'pem_type': admin.permission_type,
                              "is_superuser": False
                             }
                if admin.super_user_permission:
                    admin_data['pem_type'] = auth_models.GenericAdmin.ALL
                    admin_data['is_superuser'] = True
                # if admin.hospital.provider_encrypt:
                if hasattr(admin.hospital, 'encrypt_details'):
                    admin_data['is_encrypted'] = admin.hospital.encrypt_details.is_encrypted
                    admin_data["encrypted_by"] = admin.hospital.encrypt_details.encrypted_by.phone_number if admin.hospital.encrypt_details.encrypted_by else None
                    admin_data["encrypted_hospital_id"] = admin.hospital.encrypt_details.encrypted_hospital_id
                    admin_data["encryption_hint"] = admin.hospital.encrypt_details.hint
                    admin_data["email"] = admin.hospital.encrypt_details.email
                    admin_data["phone_numbers"] = admin.hospital.encrypt_details.phone_numbers
                    admin_data["google_drive"] = admin.hospital.encrypt_details.google_drive
                    admin_data["is_consent_received"] = admin.hospital.encrypt_details.is_consent_received
                    admin_data["updated_at"] = admin.hospital.encrypt_details.updated_at
                    admin_data["created_at"] = admin.hospital.encrypt_details.created_at
                all_data[hosp_id] = admin_data
            elif admin.hospital and (hosp_id in all_data):
                if not all_data[hosp_id]['pem_type'] == auth_models.GenericAdmin.ALL:
                    if admin.super_user_permission:
                        all_data[hosp_id]['pem_type'] == auth_models.GenericAdmin.ALL
                    elif admin.permission_type != all_data[hosp_id]['pem_type']:
                        all_data[hosp_id]['pem_type'] == auth_models.GenericAdmin.ALL
        resp = all_data.values() if all_data else []
        return Response(resp)


class DoctorProfileView(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

    def get_queryset(self):
        return doc_models.models.OpdAppointment.objects.none()

    @transaction.non_atomic_requests
    def retrieve(self, request):
        from django.contrib.staticfiles.templatetags.staticfiles import static
        response = dict()
        response['is_super_user'] = False
        response['is_super_user_lab'] = False
        resp_data = None
        today = datetime.date.today()
        queryset = doc_models.OpdAppointment.objects.filter(doctor__is_live=True, hospital__is_live=True).filter(
            (Q(
                 Q(doctor__manageable_doctors__user=request.user,
                   doctor__manageable_doctors__hospital=F('hospital'),
                   doctor__manageable_doctors__is_disabled=False)
                 |
                 Q(doctor__manageable_doctors__user=request.user,
                   doctor__manageable_doctors__hospital__isnull=True,
                   doctor__manageable_doctors__is_disabled=False,
                   )
                 |
                 Q(hospital__manageable_hospitals__doctor__isnull=True,
                   hospital__manageable_hospitals__user=request.user,
                   hospital__manageable_hospitals__is_disabled=False)
             )
            |
            Q(
                Q(doctor__manageable_doctors__user=request.user,
                  doctor__manageable_doctors__super_user_permission=True,
                  doctor__manageable_doctors__is_disabled=False,
                  doctor__manageable_doctors__entity_type=v1_utils.GenericAdminEntity.DOCTOR, ) |
                Q(hospital__manageable_hospitals__user=request.user,
                  hospital__manageable_hospitals__super_user_permission=True,
                  hospital__manageable_hospitals__is_disabled=False,
                  hospital__manageable_hospitals__entity_type=v1_utils.GenericAdminEntity.HOSPITAL)
            )),
            Q(status=doc_models.OpdAppointment.ACCEPTED,
              time_slot_start__date=today)
            )\
            .distinct().count()
        lab_appointment_count = lab_models.LabAppointment.objects.filter(lab__manageable_lab_admins__user=request.user,
                                                                         lab__manageable_lab_admins__is_disabled=False,
                                                                         status=lab_models.LabAppointment.ACCEPTED,
                                                                         time_slot_start__date=today)\
                                                                 .distinct().count()
        doctor_mobile = auth_models.DoctorNumber.objects.select_related('doctor', 'hospital')\
                                                        .prefetch_related('doctor__images', 'doctor__qualifications',
                                                                          'doctor__qualifications__qualification',
                                                                          'doctor__doctor_clinics', 'doctor__languages',
                                                                          'doctor__awards', 'doctor__medical_services',
                                                                          'doctor__associations', 'doctor__experiences',
                                                                          'doctor__mobiles', 'doctor__emails', 'hospital__spoc_details',
                                                                          'doctor__qualifications__specialization',
                                                                          'doctor__qualifications__college', 'doctor__doctorpracticespecializations',
                                                                          'doctor__doctorpracticespecializations__specialization')\
                                                        .filter(phone_number=request.user.phone_number, doctor__is_live=True)
        if len(doctor_mobile):
            doc_list = [doc.doctor for doc in doctor_mobile]
            doc_serializer = serializers.DoctorProfileSerializer(doc_list, many=True, context={"request": request})
            resp_data = doc_serializer.data
        else:
            doctor = request.user.doctor if hasattr(request.user, 'doctor') else None
            if doctor and doctor.is_live:
                doc_serializer = serializers.DoctorProfileSerializer(doctor, many=False,
                                                                     context={"request": request})
                resp_data = doc_serializer.data

        if not resp_data:
            response['profiles'] = []
            response["is_doc"] = False
            response["name"] = 'Admin'
            admin_image_url = static('doctor_images/no_image.png')
            admin_image = ''
            if admin_image_url:
                admin_image = request.build_absolute_uri(admin_image_url)
            response["thumbnail"] = admin_image
        else:
            response["is_doc"] = True
            response["profiles"] = resp_data

        response["count"] = queryset
        response['lab_appointment_count'] = lab_appointment_count

        # Check access_type START
        user = request.user
        OPD_ONLY = 1
        LAB_ONLY = 2
        OPD_AND_LAB = 3

        generic_admin = auth_models.GenericAdmin.objects.filter(user=user,
                                                is_disabled=False)
        generic_lab_admin = auth_models.GenericLabAdmin.objects.filter(user=user,
                                                                is_disabled=False)
        opd_admin = len(generic_admin)
        lab_admin = len(generic_lab_admin)
        if opd_admin and lab_admin:
            response["access_type"] = OPD_AND_LAB
        elif opd_admin and not lab_admin:
            response["access_type"] = OPD_ONLY
        elif lab_admin:
            response["access_type"] = LAB_ONLY
        # Check access_type END

        for opd in generic_admin:
            if opd.super_user_permission:
                response['is_super_user'] = True
                break
        for opd in generic_lab_admin:
            if opd.super_user_permission:
                response['is_super_user_lab'] = True
                break
        return Response(response)


class DoctorPermission(permissions.BasePermission):
    message = 'Doctor is allowed to perform action only.'

    def has_permission(self, request, view):
        if request.user.user_type == User.DOCTOR:
            return True
        return False


class DoctorBlockCalendarViewSet(viewsets.GenericViewSet):

    serializer_class = serializers.DoctorLeaveSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, DoctorPermission,)
    INTERVAL_MAPPING = {doc_models.DoctorLeave.INTERVAL_MAPPING.get(key): key for key in
                        doc_models.DoctorLeave.INTERVAL_MAPPING.keys()}

    def get_queryset(self):
        user = self.request.user
        return doc_models.DoctorLeave.objects.select_related('doctor', 'hospital')\
                                             .filter(Q(deleted_at__isnull=True), Q(
                                                   Q(doctor__manageable_doctors__user=user,
                                                     doctor__manageable_doctors__entity_type=v1_utils.GenericAdminEntity.DOCTOR,
                                                     doctor__manageable_doctors__is_disabled=False,
                                                     doctor__manageable_doctors__hospital__isnull=True)
                                                   |
                                                   Q(doctor__manageable_doctors__user=user,
                                                     doctor__manageable_doctors__entity_type=v1_utils.GenericAdminEntity.DOCTOR,
                                                     doctor__manageable_doctors__is_disabled=False,
                                                     doctor__manageable_doctors__hospital__isnull=False,
                                                     doctor__manageable_doctors__hospital=F('hospital'))
                                                   |
                                                   Q(hospital__manageable_hospitals__user=user,
                                                     hospital__manageable_hospitals__is_disabled=False,
                                                     hospital__manageable_hospitals__entity_type=v1_utils.GenericAdminEntity.HOSPITAL)
                                                   )
                                                  |
                                                  Q(
                                                      Q(doctor__manageable_doctors__user=user,
                                                        doctor__manageable_doctors__super_user_permission=True,
                                                        doctor__manageable_doctors__is_disabled=False,
                                                        doctor__manageable_doctors__entity_type=v1_utils.GenericAdminEntity.DOCTOR)
                                                      |
                                                      Q(hospital__manageable_hospitals__user=user,
                                                        hospital__manageable_hospitals__is_disabled=False,
                                                        hospital__manageable_hospitals__entity_type=v1_utils.GenericAdminEntity.HOSPITAL,
                                                        hospital__manageable_hospitals__super_user_permission=True)
                                                   )
                                                  ).distinct()

    @transaction.non_atomic_requests
    def list(self, request, *args, **kwargs):
        serializer = serializers.DoctorLeaveValidateQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        doctor_id = validated_data.get('doctor_id')
        hospital_id = validated_data.get('hospital_id')
        queryset = self.get_queryset()
        if doctor_id and hospital_id:
            queryset= queryset.filter(doctor_id=doctor_id, hospital_id=hospital_id)
        elif doctor_id and not hospital_id:
            queryset = queryset.filter(doctor_id=doctor_id)
        elif hospital_id and not doctor_id:
            queryset = queryset.filter(hospital_id=hospital_id)
        serializer = serializers.DoctorLeaveSerializer(queryset, many=True)
        return Response(serializer.data)

    def create_leave_data(self, hospital_id,doctor_id, validated_data, start_time, end_time):
        return {
                    "doctor": doctor_id,
                    "hospital": hospital_id,
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_date": validated_data.get("start_date"),
                    "end_date": validated_data.get("end_date")
                }

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        doctor_leave_data = []
        serializer = serializers.DoctorBlockCalenderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data

        hospital_id = validated_data.get("hospital_id").id if validated_data.get("hospital_id") else None
        start_time = validated_data.get("start_time")
        end_time = validated_data.get("end_time")
        doctor_id = validated_data.get("doctor_id").id if validated_data.get("doctor_id") else None

        if not start_time:
            start_time = self.INTERVAL_MAPPING[validated_data.get("interval")][0]
        if not end_time:
            end_time = self.INTERVAL_MAPPING[validated_data.get("interval")][1]
        if not hospital_id:
            assoc_hospitals = validated_data.get('doctor_id').hospitals.all()
            for hospital in assoc_hospitals:
                doctor_leave_data.append(self.create_leave_data(hospital.id, doctor_id, validated_data, start_time, end_time))
        if not doctor_id and hospital_id:
            # For all the doctor leaves in a hospital
            doctor_clinics = DoctorClinic.objects.filter(hospital=hospital_id, hospital__is_live=True,doctor__is_live=True)
            for doctor_clinic in doctor_clinics:
                doctor_leave_data.append(self.create_leave_data(hospital_id,doctor_clinic.doctor.id, validated_data, start_time, end_time))
        else:
            doctor_leave_data.append(self.create_leave_data(hospital_id, doctor_id, validated_data, start_time, end_time))

        doctor_leave_serializer = serializers.DoctorLeaveSerializer(data=doctor_leave_data, many=True)
        doctor_leave_serializer.is_valid(raise_exception=True)
        # self.get_queryset().update(deleted_at=timezone.now())        Now user can apply more than one leave
        doctor_leave_serializer.save()
        return Response(doctor_leave_serializer.data)


class DoctorDataViewset(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, DoctorPermission,)

    def get_practice_specializations(self, request, *args, **kwargs):
        qs = doc_models.PracticeSpecialization.objects.all()
        serializer = serializers.PracticeSpecializationSerializer(qs, many=True)
        return Response(serializer.data)

    def get_doctor_qualifications(self, request, *args, **kwargs):
        qs = doc_models.Qualification.objects.all()
        serializer = serializers.QualificationSerializer(qs, many=True)
        return Response(serializer.data)

    def get_languages(self, request, *args, **kwargs):
        qs = doc_models.Language.objects.all()
        serializer = serializers.LanguageSerializer(qs, many=True)
        return Response(serializer.data)

    def get_doctor_medical_services(self, request, *args, **kwargs):
        qs = doc_models.MedicalService.objects.all()
        serializer = serializers.MedicalServiceSerializer(qs, many=True)
        return Response(serializer.data)

    def get_procedures(self, request, *args, **kwargs):
        qs = Procedure.objects.filter(is_enabled=True)
        serializer = serializers.ProcedureSerializer(qs, many=True)
        return Response(serializer.data)

    def get_specializations(self, request, *args, **kwargs):
        qs = doc_models.Specialization.objects.all()
        serializer = serializers.SpecializationSerializer(qs, many=True)
        return Response(serializer.data)


class ProviderSignupOtpViewset(viewsets.GenericViewSet):

    def otp_generate(self, request, *args, **kwargs):
        from ondoc.authentication.models import OtpVerifications
        serializer = serializers.GenerateOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        phone_number = valid_data.get('phone_number')
        retry_send = request.query_params.get('retry', False)
        via_sms = valid_data.get('via_sms', True)
        via_whatsapp = valid_data.get('via_whatsapp', False)
        call_source = valid_data.get('request_source')
        otp_message = OtpVerifications.get_otp_message(request.META.get('HTTP_PLATFORM'), None, True, version=request.META.get('HTTP_APP_VERSION'))
        send_otp(otp_message, phone_number, retry_send, via_sms=via_sms, via_whatsapp=via_whatsapp, call_source=call_source)
        response = {'otp_generated': True}
        return Response(response)

    def otp_verification(self, request, *args, **kwargs):
        serializer = serializers.OtpVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        phone_number = valid_data.get('phone_number')
        user = User.objects.filter(phone_number=phone_number, user_type=User.DOCTOR).first()

        if not user:
            user = User.objects.create(phone_number=phone_number, is_phone_number_verified=True, user_type=User.DOCTOR)

        token_object = JWTAuthentication.generate_token(user)
        auth_models.OtpVerifications.objects.filter(phone_number=phone_number).update(is_expired=True)

        response = {
            "login": 1,
            "token": token_object['token'],
            "expiration_time": token_object['payload']['exp']
        }
        return Response(response)


class ProviderSignupDataViewset(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, DoctorPermission,)

    def create(self, request, *args, **kwargs):
        serializer = serializers.ProviderSignupLeadDataSerializer(data=request.data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        valid_data['user'] = request.user
        try:
            doc_models.ProviderSignupLead.objects.create(**valid_data)
            return Response({"status": 1, "message": "signup lead data added"})
        except Exception as e:
            logger.error('Error creating signup lead: ' + str(e))
            return Response({"status": 0, "message": "Error creating signup lead: " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def consent_is_docprime(self, request, *args, **kwargs):
        serializer = serializers.ConsentIsDocprimeSerializer(data=request.data, context={'request':request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        user = request.user
        is_docprime = valid_data.get("is_docprime")
        try:
            provider_object = doc_models.ProviderSignupLead.objects.filter(user=user).first()
            provider_object.is_docprime = is_docprime
            provider_object.save()
            return Response({"status":1, "message":"consent updated"})
        except Exception as e:
            logger.error('Error updating consent: ' + str(e))
            return Response({"status": 0, "message": "Error updating consent - " + str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def encrypt_consent(self, request):
        serializer = serializers.ConsentIsEncryptSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        user = request.user
        objects_to_be_created = list()
        hospital_ids_to_be_created = list()
        hospitals = list()
        hospital_ids = list()
        for hospital in valid_data.get('hospitals'):
            hospitals.append(hospital['hospital_id'])
            hospital_ids.append(hospital['hospital_id'].id)
        for hospital in valid_data.get("hospitals"):
            if 'is_encrypted' in valid_data:
                if not valid_data.get('is_encrypted'):
                    exception = self.decrypt_and_save_provider_data(hospital['hospital_id'].id, valid_data['encryption_key'])
                    if exception:
                        return Response("Error while decrypting - " + str(exception), status=status.HTTP_400_BAD_REQUEST)
                else:
                    if hasattr(hospital['hospital_id'], 'encrypt_details'):
                        encrypt_object = hospital['hospital_id'].encrypt_details
                        encrypt_object.is_encrypted = True
                        encrypt_object.encrypted_by = user
                        encrypt_object.hint = valid_data.get('hint')
                        encrypt_object.encrypted_hospital_id = hospital['encrypted_hospital_id']
                        encrypt_object.email = valid_data.get("email")
                        encrypt_object.phone_numbers = valid_data.get("phone_numbers")
                        encrypt_object.google_drive = valid_data.get("google_drive")
                        encrypt_object.is_valid = True
                        encrypt_object.save()
                    else:
                        objects_to_be_created.append(doc_models.ProviderEncrypt(hospital=hospital['hospital_id'],
                                                                                is_encrypted=True,
                                                                                encrypted_by=user,
                                                                                hint=valid_data.get('hint'),
                                                                                encrypted_hospital_id=hospital['encrypted_hospital_id'],
                                                                                email=valid_data.get("email"),
                                                                                phone_numbers=valid_data.get("phone_numbers"),
                                                                                google_drive=valid_data.get("google_drive"),
                                                                                is_valid=True))
                        hospital_ids_to_be_created.append(hospital['hospital_id'].id)
            else:
                objects_to_be_created.append(doc_models.ProviderEncrypt(hospital=hospital['hospital_id'],
                                                                        is_valid=False))
                hospital_ids_to_be_created.append(hospital['hospital_id'].id)
        if 'is_encrypted' in valid_data and not valid_data.get('is_encrypted'):
            decrypted_invoice_pdfs.apply_async((hospital_ids,), countdown=5)
            decrypted_prescription_pdfs.apply_async((hospital_ids, valid_data['encryption_key']), countdown=5)
            doc_models.ProviderEncrypt.objects.filter(hospital__in=[hospital['hospital_id'] for hospital in valid_data.get("hospitals")])\
                                              .update(is_encrypted=False, encrypted_by=None, hint=None,
                                                      encrypted_hospital_id=None, email=None, phone_numbers=None,
                                                      google_drive=None, is_valid=False)
        try:
            if 'is_encrypted' in valid_data and valid_data.get('is_encrypted') and objects_to_be_created and not doc_models.ProviderEncrypt.objects.filter(hospital_id__in=hospital_ids_to_be_created):
                doc_models.ProviderEncrypt.objects.bulk_create(objects_to_be_created)
            hospitals_data = list()
            if hospitals and 'is_encrypted' in valid_data:
                prov_ecrypt_objects = doc_models.ProviderEncrypt.objects.filter(hospital__in=hospitals)
                for obj in prov_ecrypt_objects:
                    obj.send_sms(request.user)
                model_serializer = serializers.ProviderEncryptResponseModelSerializer(prov_ecrypt_objects, many=True)
                hospitals_data = model_serializer.data
            return Response({"status": 1, "message": "consent updated", "hospitals": hospitals_data})
        except Exception as e:
            logger.error('Error updating consent: ' + str(e))
            return Response({"status": 0, "message": "Error "
                                                     "doctor consent - " + str(e)}, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def bulk_create_doctors(self, doctor_details):
        doc_obj_list = list()
        for doctor in doctor_details:
            name = doctor.get('name')
            online_consultation_fees = doctor.get('online_consultation_fees')
            license = doctor.get('license', '')
            doc_obj_list.append(doc_models.Doctor(name=name, online_consultation_fees=online_consultation_fees,
                                                  enabled=False, source_type=doc_models.Hospital.PROVIDER,
                                                  license=license if license else ''))
        created_doctors = doc_models.Doctor.objects.bulk_create(doc_obj_list)
        return created_doctors

    def bulk_create_doctor_clinics(self, hospital, doctors):
        doctor_clinic_obj_list = list()
        for doctor in doctors:
            doctor_clinic_obj_list.append(doc_models.DoctorClinic(doctor=doctor, hospital=hospital,
                                                                  enabled=False))
        created_doctor_clinics = doc_models.DoctorClinic.objects.bulk_create(doctor_clinic_obj_list)
        return created_doctor_clinics

    def bulk_create_doctor_mobiles(self, doctors, doctor_details):
        doctor_mobile_obj_list = list()
        doctor_details_by_name = dict((d['name'], dict(d, index=index)) for (index, d) in enumerate(doctor_details))
        for doctor in doctors:
            phone_number = doctor_details_by_name.get(doctor.name).get('phone_number') if doctor_details_by_name.get(
                doctor.name) else None
            if phone_number:
                doctor_mobile_obj_list.append(doc_models.DoctorMobile(doctor=doctor, is_primary=True,
                                                                  number=phone_number))
        created_doctor_mobiles = doc_models.DoctorMobile.objects.bulk_create(doctor_mobile_obj_list)
        return created_doctor_mobiles

    def bulk_create_doctor_phone_number(self, hospital, doctors, doctor_details):
        doctor_number_obj_list = list()
        doctor_details_by_name = dict((d['name'], dict(d, index=index)) for (index, d) in enumerate(doctor_details))
        for doctor in doctors:
            phone_number = doctor_details_by_name.get(doctor.name).get('phone_number') if doctor_details_by_name.get(
                doctor.name) else None
            if phone_number:
                doctor_number_obj_list.append(auth_models.DoctorNumber(doctor=doctor, hospital=hospital,
                                                                       phone_number=phone_number))
        created_doctor_numbers = auth_models.DoctorNumber.objects.bulk_create(doctor_number_obj_list)
        return created_doctor_numbers

    def bulk_create_doctor_generic_admins(self, hospital, doctors, doctor_details):
        generic_admin_obj_list = list()
        doctor_details_by_name = dict((d['name'], dict(d, index=index)) for (index, d) in enumerate(doctor_details))
        for doctor in doctors:
            details = doctor_details_by_name.get(doctor.name)
            if details.get('phone_number'):
                phone_number = details.get('phone_number')
                if details.get('is_superuser'):
                    generic_admin_obj_list.append(auth_models.GenericAdmin(name=doctor.name,
                                                                           doctor=doctor, hospital=hospital,
                                                                           phone_number=phone_number,
                                                                           source_type=auth_models.GenericAdmin.APP,
                                                                           entity_type=auth_models.GenericAdmin.HOSPITAL,
                                                                           super_user_permission=True))
                    generic_admin_obj_list.append(auth_models.GenericAdmin(name=doctor.name,
                                                                           doctor=doctor, hospital=hospital,
                                                                           phone_number=phone_number,
                                                                           source_type=auth_models.GenericAdmin.APP,
                                                                           entity_type=auth_models.GenericAdmin.HOSPITAL,
                                                                           permission_type=auth_models.GenericAdmin.APPOINTMENT,
                                                                           write_permission=True))
                    continue
                if details.get('is_appointment'):
                    generic_admin_obj_list.append(auth_models.GenericAdmin(name=doctor.name,
                                                                           doctor=doctor, hospital=hospital,
                                                                           phone_number=phone_number,
                                                                           source_type=auth_models.GenericAdmin.APP,
                                                                           entity_type=auth_models.GenericAdmin.HOSPITAL,
                                                                           permission_type=auth_models.GenericAdmin.APPOINTMENT,
                                                                           write_permission=True))
                if details.get('is_billing'):
                    generic_admin_obj_list.append(auth_models.GenericAdmin(name=doctor.name,
                                                                           doctor=doctor, hospital=hospital,
                                                                           phone_number=phone_number,
                                                                           source_type=auth_models.GenericAdmin.APP,
                                                                           entity_type=auth_models.GenericAdmin.HOSPITAL,
                                                                           permission_type=auth_models.GenericAdmin.BILLINNG,
                                                                           write_permission=True))
        created_doctor_generic_admins = auth_models.GenericAdmin.objects.bulk_create(generic_admin_obj_list)
        return created_doctor_generic_admins

    def bulk_create_hospital_generic_admins(self, hospital, hospital_generic_admin_details):
        generic_admin_obj_list = list()
        for generic_admin in hospital_generic_admin_details:
            if generic_admin.get('is_superuser'):
                generic_admin_obj_list.append(
                    auth_models.GenericAdmin(name=generic_admin.get('name'), hospital=hospital,
                                             phone_number=generic_admin.get('phone_number'),
                                             source_type=auth_models.GenericAdmin.APP,
                                             entity_type=auth_models.GenericAdmin.HOSPITAL,
                                             super_user_permission=True))
                continue
            if generic_admin.get('is_appointment'):
                generic_admin_obj_list.append(
                    auth_models.GenericAdmin(name=generic_admin.get('name'), hospital=hospital,
                                             phone_number=generic_admin.get('phone_number'),
                                             source_type=auth_models.GenericAdmin.APP,
                                             entity_type=auth_models.GenericAdmin.HOSPITAL,
                                             permission_type=auth_models.GenericAdmin.APPOINTMENT,
                                             write_permission=True))
            if generic_admin.get('is_billing'):
                generic_admin_obj_list.append(
                    auth_models.GenericAdmin(name=generic_admin.get('name'), hospital=hospital,
                                             phone_number=generic_admin.get('phone_number'),
                                             source_type=auth_models.GenericAdmin.APP,
                                             entity_type=auth_models.GenericAdmin.HOSPITAL,
                                             permission_type=auth_models.GenericAdmin.BILLINNG,
                                             write_permission=True))
        generic_admin_objects = auth_models.GenericAdmin.objects.bulk_create(generic_admin_obj_list)
        generic_admin_model_serializer = serializers.GenericAdminModelSerializer(generic_admin_objects,
                                                                                 many=True)
        return generic_admin_model_serializer.data

    def doctor_creation_flow(self, hospital, doctor_details):
        created_doctors = self.bulk_create_doctors(doctor_details)
        created_doctor_clinics = self.bulk_create_doctor_clinics(hospital, created_doctors)
        created_doctor_mobiles = self.bulk_create_doctor_mobiles(created_doctors, doctor_details)
        created_doctor_numbers = self.bulk_create_doctor_phone_number(hospital, created_doctors, doctor_details)
        created_doctor_generic_admins = self.bulk_create_doctor_generic_admins(hospital, created_doctors,
                                                                               doctor_details)
        doctor_model_serializer = serializers.DoctorModelSerializer(created_doctors, many=True)
        # doctor_clinic_model_serializer = serializers.DoctorClinicModelSerializer(created_doctor_clinics,
        #                                                                          many=True)
        # doctor_mobile_model_serializer = serializers.DoctorMobileModelSerializer(created_doctor_mobiles,
        #                                                                          many=True)
        doctor_generic_admin_model_serializer = serializers.GenericAdminModelSerializer(created_doctor_generic_admins,
                                                                                        many=True)
        doctors_data = doctor_model_serializer.data
        # doctor_clinics_data = doctor_clinic_model_serializer.data
        # doctors_mobile_data = doctor_mobile_model_serializer.data
        doctors_generic_admin_data = doctor_generic_admin_model_serializer.data
        return doctors_data, doctors_generic_admin_data

    def create_hospital(self, request, *args, **kwargs):
        serializer = serializers.CreateHospitalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        valid_data['enabled'] = False
        valid_data['enabled_for_online_booking'] = False
        valid_data['is_mask_number_required'] = False
        valid_data['source_type'] = doc_models.Hospital.PROVIDER

        hosp_essential_dict = dict()
        hosp_essential_dict['name'] = valid_data.get('name')
        if valid_data.get('city'):
            hosp_essential_dict['city'] = valid_data.get('city')
        if valid_data.get('state'):
            hosp_essential_dict['state'] = valid_data.get('state')
        if valid_data.get('country'):
            hosp_essential_dict['country'] = valid_data.get('country')
        hosp_essential_dict['is_listed_on_docprime'] = valid_data.get('is_listed_on_docprime')

        contact_number = valid_data.get('contact_number')
        doctor_details = valid_data.get('doctors')
        hospital_generic_admin_details = valid_data.get('staffs')
        doctors_data = None
        doctors_generic_admin_data = None
        hospital_generic_admins_data = None
        try:
            hospital = doc_models.Hospital.objects.create(**hosp_essential_dict,
                                                          is_billing_enabled=True,
                                                          is_appointment_manager=True,
                                                          source_type=doc_models.Hospital.PROVIDER)
            hospital_model_serializer = serializers.HospitalModelSerializer(hospital, many=False)
            auth_models.GenericAdmin.objects.create(user=request.user, phone_number=request.user.phone_number,
                                                    hospital=hospital, super_user_permission=True,
                                                    entity_type=auth_models.GenericAdmin.HOSPITAL)
            auth_models.SPOCDetails.objects.create(name=valid_data.get('name'), number=request.user.phone_number,
                                                   email=valid_data.get('email'), content_object=hospital,
                                                   contact_type=auth_models.SPOCDetails.SPOC)
            if contact_number:
                auth_models.SPOCDetails.objects.create(name=valid_data.get('name'), number=contact_number,
                                                       contact_type=auth_models.SPOCDetails.OTHER,
                                                       content_object=hospital)
            if doctor_details:
                doctors_data, doctors_generic_admin_data = self.doctor_creation_flow(hospital, doctor_details)

            if hospital_generic_admin_details:
                hospital_generic_admins_data = self.bulk_create_hospital_generic_admins(hospital, hospital_generic_admin_details)

            return Response({"status": 1,
                             "hospital": hospital_model_serializer.data,
                             "doctors": doctors_data if doctors_data else None,
                             "doctors_generic_admins": doctors_generic_admin_data if doctors_generic_admin_data else None,
                             "hospital_generic_admins": hospital_generic_admins_data if hospital_generic_admins_data else None})
        except Exception as e:
            logger.error('Error creating Hospital: ' + str(e))
            return Response({"status": 0, "message": "Error creating Hospital - " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def create_doctor(self, request, *args, **kwargs):
        serializer = serializers.CreateDoctorSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        hospital = valid_data.get('hospital_id')
        doctor_details = valid_data.get("doctors", [])
        try:
            doctors_data, doctors_generic_admin_data = self.doctor_creation_flow(hospital, doctor_details)
            return Response({"status": 1,
                             "doctors": doctors_data if doctors_data else None,
                             "doctors_generic_admins": doctors_generic_admin_data if doctors_generic_admin_data else None
                            })
        except Exception as e:
            logger.error('Error adding Doctors ' + str(e))
            return Response({"status": 0, "message": "Error adding Doctors - " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def create_staffs(self, request, *args, **kwargs):
        serializer = serializers.CreateGenericAdminSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        hospital = valid_data.get('hospital_id')
        hospital_generic_admin_details = valid_data.get("staffs", [])
        try:
            hospital_generic_admins_data = self.bulk_create_hospital_generic_admins(hospital,
                                                                                      hospital_generic_admin_details)
            return Response({"status": 1, "staffs": hospital_generic_admins_data})
        except Exception as e:
            logger.error('Error adding Staffs ' + str(e))
            return Response({"status": 0, "message": "Error adding Staffs - " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def update_hospital_consent(self, request, *args, **kwargs):
        serializer = serializers.UpdateHospitalConsent(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        try:
            hospital = valid_data.get('hospital_id')
            if hospital.is_listed_on_docprime:
                return Response({"status": 1, "message": "already consent present for given hospital"}, status.HTTP_200_OK)
            hospital.is_listed_on_docprime = valid_data.get('is_listed_on_docprime')
            hospital.save()
            return Response({"status": 1, "message": "successfully updated"}, status.HTTP_200_OK)
        except Exception as e:
            logger.error('Error updating hospital consent ' + str(e))
            return Response({"status": 0, "message": "Error updating hospital consent - " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def decrypt_and_save_provider_data(self, hospital_id, key):
        passphrase = hashlib.md5(key.encode())
        passphrase = passphrase.hexdigest()[:16]
        patient_queryset = doc_models.OfflinePatients.objects.prefetch_related('patient_mobiles').filter(hospital_id=hospital_id)
        for patient in patient_queryset:
            if patient.encrypted_name:
                name, exception = v1_utils.AES_encryption.decrypt(patient.encrypted_name, passphrase)
                if exception:
                    return exception
                patient.name = ''.join(e for e in name if e.isalnum() or e==' ')
                patient.encrypted_name = None
                patient.save()
            for mobile in patient.patient_mobiles.all():
                if mobile.encrypted_number:
                    number, exception = v1_utils.AES_encryption.decrypt(mobile.encrypted_number, passphrase)
                    if exception:
                        return exception
                    mobile.phone_number = ''.join(e for e in number if e.isalnum())
                    mobile.encrypted_number = None
                    mobile.save()


class PartnersAppInvoice(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, DoctorPermission,)

    def add_or_edit_general_invoice_item(self, request):
        try:
            serializer = serializers.GeneralInvoiceItemsSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            valid_data = serializer.validated_data
            hospital_ids = valid_data.pop('hospital_ids')
            hospitals = valid_data.pop('hospitals')
            general_invoice_item = valid_data.pop('general_invoice_item') if valid_data.get('general_invoice_item') else None
            if not general_invoice_item:
                invoice_item_obj = doc_models.GeneralInvoiceItems.objects.create(**valid_data)
                invoice_item_obj.hospitals.add(*hospitals)
            else:
                invoice_items = doc_models.GeneralInvoiceItems.objects.filter(id=general_invoice_item.id)
                invoice_items.update(**valid_data)
                invoice_item_obj = invoice_items.first()
                invoice_item_obj.hospitals.set(hospitals, clear=True)
            model_serializer = serializers.GeneralInvoiceItemsModelSerializer(invoice_item_obj, many=False)
            return Response({"status": 1, "message": "Invoice Item added successfully",
                             "invoice_item": model_serializer.data}, status.HTTP_200_OK)
        except Exception as e:
            return Response({"status":0 , "message": "Error adding Invoice Item with exception -" + str(e)},
                            status.HTTP_400_BAD_REQUEST)

    def list_invoice_items(self, request):
        serializer = serializers.ListInvoiceItemsSerializer(data=request.query_params, context={'request':request})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        hospital = data.get('hospital_id')
        if hospital:
            items = doc_models.GeneralInvoiceItems.objects.filter(hospitals=hospital)
            model_serializer = serializers.GeneralInvoiceItemsModelSerializer(items, many=True)
        else:
            admin = auth_models.GenericAdmin.objects.filter(user=request.user)
            hospital_ids = admin.values_list('hospital', flat=True).distinct()
            items = doc_models.GeneralInvoiceItems.objects.filter(hospitals__in=hospital_ids)
            model_serializer = serializers.GeneralInvoiceItemsModelSerializer(items, many=True)
        return Response({"invoice_items": model_serializer.data}, status.HTTP_200_OK)

    @staticmethod
    def bulk_create_selected_invoice_items(selected_invoice_item, invoice):
        obj_list = list()
        for item in selected_invoice_item:
            obj_list.append(doc_models.SelectedInvoiceItems(invoice=invoice,
                                                            invoice_item=item['invoice_item'],
                                                            quantity=item['quantity'],
                                                            calculated_price=item['calculated_price']))
        created_objects = doc_models.SelectedInvoiceItems.objects.bulk_create(obj_list)
        return created_objects

    def create_or_update_invoice(self, invoice_data, version, user, id=None):
        invoice = selected_invoice_items_created = e = None

        task = invoice_data.pop('task')
        generate_invoice = invoice_data.pop("generate_invoice")

        appointment = invoice_data.get('appointment')
        selected_invoice_items = invoice_data.get('selected_invoice_items')
        invoice_data['selected_invoice_items'] = serializers.SelectedInvoiceItemsJSONSerializer(
            selected_invoice_items, many=True).data
        if task == doc_models.PartnersAppInvoice.CREATE:
            invoice_obj = doc_models.PartnersAppInvoice(**invoice_data)
            if not invoice_data.get('is_encrypted'):
                last_serial = doc_models.PartnersAppInvoice.last_serial(appointment)
                serial = last_serial + 1 if version == '01' else last_serial
                invoice_obj.invoice_serial_id = 'INV-' + str(appointment.hospital.id) + '-' + \
                                                str(appointment.doctor.id) + '-' + str(serial) + '-' + version
        else:
            if not id:
                raise Exception("invoice_id is required")
            invoice_queryset = doc_models.PartnersAppInvoice.objects.filter(id=id)
            if invoice_data.get('is_encrypted'):
                doc_models.EncryptedPartnersAppInvoiceLogs.objects.create(invoice=serializers.PartnersAppInvoiceModelSerialier(invoice_queryset.first()).data)
            invoice_queryset.update(**invoice_data)
            invoice_obj = invoice_queryset.first()

        if generate_invoice:
            invoice_obj.is_invoice_generated = True
            if not invoice_data.get('is_encrypted'):
                invoice_obj.generate_invoice(invoice_data['selected_invoice_items'], appointment)
        try:
            invoice_obj.edited_by = user
            invoice_obj.save()
            invoice = serializers.PartnersAppInvoiceModelSerialier(invoice_obj)

            if selected_invoice_items:
                if task == doc_models.PartnersAppInvoice.UPDATE:
                    doc_models.SelectedInvoiceItems.objects.filter(invoice=invoice_obj.id).delete()
                selected_invoice_items_objects = self.bulk_create_selected_invoice_items(selected_invoice_items,
                                                                                         invoice_obj)
                model_serializer = serializers.SelectedInvoiceItemsModelSerializer(selected_invoice_items_objects,
                                                                                   many=True)
            selected_invoice_items_created = model_serializer.data if selected_invoice_items else []
            return invoice, selected_invoice_items_created, e
        except Exception as e:
            logger.error(str(e))
            return invoice, selected_invoice_items_created, str(e)

    def create(self, request):

        serializer = serializers.PartnersAppInvoiceSerialier(data=request.data)
        serializer.is_valid(raise_exception=True)
        invoice_data = serializer.validated_data

        appointment = invoice_data.get("appointment")
        if doc_models.PartnersAppInvoice.objects.filter(appointment=appointment, is_valid=True).exists():
            logger.error('Invoice for this appointment already exists, please try updating it')
            return Response(
                {"status": 0, "message": "Invoice for this appointment already exists, please try updating it"},
                 status.HTTP_400_BAD_REQUEST)
        try:
            invoice_data['task'] = doc_models.PartnersAppInvoice.CREATE
            invoice, selected_invoice_items_created, exception = self.create_or_update_invoice(invoice_data, version='01', user=request.user, id=None)
            if not exception:
                return Response({"status": 1, "invoice": invoice.data,
                                 "selected_invoice_items_created": selected_invoice_items_created}, status.HTTP_200_OK)
            logger.error(str(exception))
            return Response({"status": 0, "message": "Error creating invoice - " + str(exception)}, status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(str(e))
            return Response({"status": 0, "message": "Error creating invoice - " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def update(self, request):
        try:
            serializer = serializers.UpdatePartnersAppInvoiceSerializer(data=request.data, context={"request": request})
            serializer.is_valid(raise_exception=True)
            invoice = serializer.validated_data['invoice_id']
            data = serializer.validated_data['data']
            if not invoice.is_invoice_generated:
                invoice.is_edited = True
                invoice.save()
                version = invoice.invoice_serial_id.split('-')[-1] if not data.get('is_encrypted') else None
                data['task'] = doc_models.PartnersAppInvoice.UPDATE
                invoice_data, selected_invoice_items_created, exception = self.create_or_update_invoice(data, version, request.user, invoice.id)

            else:
                invoice.is_valid = False
                invoice.save()
                version = str(int(invoice.invoice_serial_id.split('-')[-1]) + 1).zfill(2) if not invoice.is_encrypted else None
                data['task'] = doc_models.PartnersAppInvoice.CREATE
                invoice_data, selected_invoice_items_created, exception = self.create_or_update_invoice(data, version, request.user)
            if not exception:
                return Response({"status": 1, "invoice": invoice_data.data,
                                 "selected_invoice_items_created": selected_invoice_items_created}, status.HTTP_200_OK)
            logger.error(str(exception))
            return Response({"status": 0, "message": "Error creating invoice - " + str(exception)},
                            status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(str(e))
            return Response({"status": 0, "message": "Error updating invoice - " + str(e)}, status.HTTP_400_BAD_REQUEST)


class PartnersAppInvoicePDF(viewsets.GenericViewSet):

    def download_pdf(self, request, encoded_filename=None):
        if not encoded_filename:
            return Response({"status": 0, "message": "encoded filename is required"},
                            status=status.HTTP_400_BAD_REQUEST)
        encoded_filename = jwt.decode(encoded_filename, settings.PARTNERS_INVOICE_ENCODE_KEY)
        filename = encoded_filename.get('filename')
        invoice_serial_id = filename[filename.find('INV-'):].replace('.pdf', '')
        invoice = doc_models.PartnersAppInvoice.objects.filter(invoice_serial_id=invoice_serial_id).order_by('-updated_at').first()
        if not invoice:
            return Response({"status": 0, "message": "File not found"}, status=status.HTTP_404_NOT_FOUND)
        response = HttpResponse(invoice.file, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=%s' % filename
        return response


class PartnerEConsultationViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

    def get_queryset(self):
        return None

    def create(self, request):
        serializer = serializers.EConsultCreateBodySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        e_obj = valid_data.get('e_consultation')
        if e_obj:
            return Response(
                {"already_exists": True,
                 "data": serializers.EConsultListSerializer(e_obj, context={'request': request}).data})
        e_obj = prov_models.EConsultation(doctor=valid_data['doctor_obj'], created_by=request.user,
                                          fees=valid_data['fees'], validity=valid_data.get('validity', None),
                                          status=prov_models.EConsultation.CREATED)
        patient = valid_data['patient_obj']
        if valid_data.get('offline_p') and valid_data['offline_p']:
            e_obj.offline_patient = patient
            patient_number = patient.get_patient_mobile()
            if patient_number:
                patient_number = str(patient_number)

        else:
            e_obj.online_patient = patient
            patient_number = patient.phone_number

        rc_super_user_obj = prov_models.RocketChatSuperUser.objects.filter(token__isnull=False).order_by('-updated_at').first()
        if not rc_super_user_obj:
            rc_super_user_obj = v1_utils.rc_superuser_login()
        if not rc_super_user_obj:
            return Response("Error in RocketChat SuperUser Login API", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        auth_token = rc_super_user_obj.token
        auth_user_id = rc_super_user_obj.user_id
        executed_fully = v1_utils.rc_users(e_obj, patient, auth_token, auth_user_id)
        if not executed_fully:
            logger.error('Error in e-consultation create - check logs related to RocketChat APIs')
            return Response('Error in e-consultation create - check logs related to RocketChat APIs',
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        e_obj.save()

        if patient_number:
            e_obj.send_sms_link(valid_data['patient_obj'], patient_number)

        resp_data = serializers.EConsultListSerializer(e_obj, context={'request': request})

        return Response({"already_exists": False, "data": resp_data.data})

    def list(self, request):
        filter_kwargs = dict()
        id = request.query_params.get('id')
        if id:
            filter_kwargs['id'] = id
        queryset = prov_models.EConsultation.objects.select_related('doctor', 'offline_patient', 'online_patient')\
                                                    .filter(**filter_kwargs, created_by=request.user)
        serializer = serializers.EConsultListSerializer(queryset, context={'request': request}, many=True)
        return Response(serializer.data)

    def share(self, request):
        serializer = serializers.EConsultSerializer(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        e_consultation = valid_data['e_consultation']
        if not e_consultation.link:
            return Response({"status": 0, "error": "Consultation Link not Found"}, status=status.HTTP_404_NOT_FOUND)
        patient, patient_number = e_consultation.get_patient_and_number()
        result = e_consultation.send_sms_link(patient, patient_number)
        if result.get('error'):
            return Response({"status": 0, "message": "Error updating invoice - " + str(result.get('error'))}, status.HTTP_400_BAD_REQUEST)
        return Response({"status": 1, "message": "e-consultation link shared"})

    def complete(self, request):
        serializer = serializers.EConsultSerializer(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        e_consultation = valid_data['e_consultation']
        e_consultation.status = prov_models.EConsultation.COMPLETED
        try:
            e_consultation.save()
        except Exception as e:
            logger.error(str(e))
            return Response({'status': 0,
                             'message': 'Error changing the status of EConsultation to completed - ' + str(e)},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        resp_data = serializers.EConsultListSerializer(e_consultation, context={'request': request})
        return Response({'status': 1, 'message': 'EConsultation completed successfully', 'data': resp_data.data})

    def video_link_share(self, request):
        serializer = serializers.EConsultSerializer(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        e_consultation = valid_data.get('e_consultation')
        user_token = e_consultation.doctor.rc_user.login_token
        user_id = e_consultation.doctor.rc_user.response_data['user']['_id']
        msg_txt = "This is the video link: {}".format(e_consultation.get_video_chat_url())
        request_data = {
            "roomId": e_consultation.rc_group.group_id,
            "text": msg_txt,
        }
        response, error_message = e_consultation.post_chat_message(user_id, user_token, request_data)
        if error_message:
            return Response({"status": 0, "message": error_message})
        else:
            e_consultation_notification = comm_models.EConsultationComm(e_consultation=e_consultation,
                                                                        notification_type=notif_models.NotificationAction.E_CONSULT_VIDEO_LINK_SHARE)
            e_consultation_notification.send()
            return Response({"status": 1, "message": "Notifications sent"})

    def prescription_upload(self, request):
        from ondoc.api.v1.prescription.serializers import AppointmentPrescriptionUploadSerializer
        from ondoc.prescription.models import AppointmentPrescription
        from ondoc.api.v1.utils import util_absolute_url
        user = request.user
        request.data['user'] = user.id
        pres_serializer = AppointmentPrescriptionUploadSerializer(data=request.data, context={'request': request})
        pres_serializer.is_valid(raise_exception=True)
        pres_data = pres_serializer.validated_data
        e_consult_id = request.data.get('id')
        if not e_consult_id:
            return Response({"status": 0, "message": "e_consult id is required"}, status=status.HTTP_400_BAD_REQUEST)
        e_consultation = prov_models.EConsultation.objects.filter(id=e_consult_id, created_by=user)\
                                                          .exclude(status__in=[prov_models.EConsultation.COMPLETED,
                                                                               prov_models.EConsultation.CANCELLED,
                                                                               prov_models.EConsultation.EXPIRED]).first()
        if not e_consultation:
            return Response({"status": 0, "message": "e_consultation not found"}, status=status.HTTP_404_NOT_FOUND)
        prescription_obj = AppointmentPrescription.objects.create(**pres_data, content_object=e_consultation)

        user_token = e_consultation.doctor.rc_user.login_token
        user_id = e_consultation.doctor.rc_user.response_data['user']['_id']
        request_data = {
            "roomId": e_consultation.rc_group.group_id,
            "text": "Link to Prescription: {}".format(util_absolute_url(prescription_obj.prescription_file.url)),
        }
        response, error_message = e_consultation.post_chat_message(user_id, user_token, request_data)
        if error_message:
            return Response({"status": 0, "message": error_message})
        else:
            model_serializer = AppointmentPrescriptionUploadSerializer(prescription_obj)
            return Response({"status": 1, "message": "Prescription uploaded successfully", "data": model_serializer.data})


class ConsumerEConsultationViewSet(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated,)

    def get_queryset(self):
        return None

    def list(self, request):
        filter_kwargs = dict()
        id = request.query_params.get('id')
        if id:
            filter_kwargs['id'] = id
        queryset = prov_models.EConsultation.objects.select_related('doctor', 'offline_patient', 'online_patient', 'rc_group')\
                                                    .prefetch_related('offline_patient__patient_mobiles',
                                                                      'doctor__qualifications',
                                                                      'doctor__qualifications__qualification',
                                                                      'doctor__qualifications__specialization',
                                                                      'doctor__qualifications__college',
                                                                      )\
                                                    .filter(Q(**filter_kwargs),
                                                            Q(online_patient__isnull=True,
                                                              offline_patient__user=request.user)
                                                            |
                                                            Q(online_patient__isnull=False,
                                                              online_patient__user=request.user)
                                                            ).all()
        serializer = serializers.ConsumerEConsultListSerializer(queryset, context={'request': request}, many=True)
        return Response(serializer.data)

    @transaction.atomic()
    def create_order(self, request):
        from ondoc.notification.tasks import save_pg_response
        from ondoc.account.mongo_models import PgLogs
        from ondoc.account.models import ConsumerAccount, Order
        user = request.user
        data = request.data

        consult_id = data.get('consult_id')
        if not consult_id:
            return Response({"error": "Consultation ID not provided"}, status=status.HTTP_400_BAD_REQUEST)
        consultation = prov_models.EConsultation.objects.select_related('offline_patient', 'online_patient').filter(id=consult_id).first()
        if not consultation:
            return Response({"error": "Consultation not Found"}, status=status.HTTP_404_NOT_FOUND)

        if user and user.is_anonymous:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        if settings.SAVE_LOGS:
            save_pg_response.apply_async((PgLogs.ECONSULT_ORDER_REQUEST, None, None, None, data, user.id),
                                         eta=timezone.localtime(), queue=settings.RABBITMQ_LOGS_QUEUE)

        doc = consultation.doctor
        use_wallet = data.get('use_wallet', True)
        amount = consultation.fees
        # promotional_amount = data.get('promotional_amount', 0)
        error = False
        resp = {}
        details = {}
        process_immediately = False
        product_id = Order.PROVIDER_ECONSULT_PRODUCT_ID

        consumer_account = ConsumerAccount.objects.get_or_create(user=user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=user)

        wallet_balance = consumer_account.balance
        cashback_balance = consumer_account.cashback
        total_balance = wallet_balance + cashback_balance

        amount_to_paid = amount

        if use_wallet and total_balance >= amount:
            cashback_amount = min(cashback_balance, amount_to_paid)
            wallet_amount = max(0, amount_to_paid - cashback_amount)
            amount_to_paid = max(0, amount_to_paid - total_balance)
            process_immediately = True
        elif use_wallet and total_balance < amount:
            cashback_amount = min(amount_to_paid, cashback_balance)
            wallet_amount = 0
            if cashback_amount < amount_to_paid:
                wallet_amount = min(wallet_balance, amount_to_paid - cashback_amount)
            amount_to_paid = max(0, amount_to_paid - total_balance)
            process_immediately = False
        else:
            cashback_amount = 0
            wallet_amount = 0
            process_immediately = False

        action = Order.PROVIDER_ECONSULT_PAY
        profile = consultation.online_patient if consultation.online_patient else consultation.offline_patient
        action_data = {"id": consultation.id, "user": user.id, "extra_details": details, "doc_id": consultation.doctor.id, "coupon": data.get('coupon'),
                       "effective_price": float(amount_to_paid), "profile": str(profile.id), "validity": consultation.validity.strftime("%Y-%m-%d"),
                       "price": float(amount), "cashback": float(cashback_amount), "consultation_id": consultation.id}

        pg_order = Order.objects.create(
            amount=float(amount_to_paid),
            action=action,
            action_data=action_data,
            wallet_amount=wallet_amount,
            cashback_amount=cashback_amount,
            payment_status=Order.PAYMENT_PENDING,
            user=user,
            product_id=product_id
        )
        if process_immediately:
            consultation_ids = pg_order.process_pg_order()
            resp["status"] = 1
            resp["payment_required"] = False
            resp["data"] = {
                "orderId": pg_order.id,
                "type": consultation_ids.get("type", "econsult"),
                "id": consultation_ids.get("id", None)
            }
        else:
            resp["status"] = 1
            resp['data'], resp["payment_required"] = v1_utils.payment_details(request, pg_order)
        return Response(resp, status=status.HTTP_200_OK)

    def get_order_consult_id(self, request):
        from ondoc.account.models import Order
        order_id = request.query_params.get('order_id', None)
        order_obj = None
        econsult_id = None
        order_obj = Order.objects.filter(id=order_id).first()
        if not order_id or not order_obj:
            return Response({"error": "Order Id not Found"}, status=status.HTTP_404_NOT_FOUND)

        action_data = order_obj.action_data
        if action_data:
            econsult_id = action_data.get('consultation_id')
        return Response({"econsult_id": econsult_id})


class EConsultationCommViewSet(viewsets.GenericViewSet):

    def communicate(self, request):
        if not request.query_params.get('api_key') or request.query_params['api_key'] != settings.ECS_COMM_API_KEY:
            return Response({"status": 0, "error": "Unauthorized"}, status=status.HTTP_400_BAD_REQUEST)
        serializer = serializers.EConsultCommunicationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        e_consultation = valid_data.get('e_consultation')
        notification_types = valid_data.get('notification_types')
        patient = valid_data.get('patient')
        receiver_rc_users = valid_data.get('receiver_rc_users')
        sender_rc_user = valid_data.get('sender_rc_user')
        patient_rc_user = valid_data.get('patient_rc_user')
        doctor_rc_user = valid_data.get('doctor_rc_user')
        comm_types = valid_data.get('comm_types')

        if NotificationAction.E_CONSULT_NEW_MESSAGE_RECEIVED in notification_types:
            receivers = list()
            if doctor_rc_user in receiver_rc_users:
                receivers.append(e_consultation.created_by)
            elif patient_rc_user in receiver_rc_users:
                receivers.append(patient.user)
            try:
                e_consultation_notification = comm_models.EConsultationComm(e_consultation,
                                                                            notification_type=NotificationAction.E_CONSULT_NEW_MESSAGE_RECEIVED,
                                                                            receivers=receivers, comm_types=comm_types)
                e_consultation_notification.send()
            except Exception as e:
                logger.error('Error in send new message notification - ' + str(e))
                return Response({"status": 0, "error": 'Error in send new message notification - ' + str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({"status": 1, "message": "success"})


class PartnerLabTestSamplesCollectViewset(viewsets.GenericViewSet):

    authentication_classes = (JWTAuthentication,)
    permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

    # def get_queryset(self):
    #     request = self.request
    #     return prov_models.PartnerLabSamplesCollectOrder.objects.prefetch_related('lab_alerts', 'reports') \
    #                                                             .filter(hospital__manageable_hospitals__phone_number=request.user.phone_number).distinct()

    def tests_list(self, request):
        serializer = serializers.PartnerLabTestsListSerializer(data=request.query_params, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        hosp_lab_list = valid_data['hosp_lab_list']
        response_list = list()
        for hosp_lab_dict in hosp_lab_list:
            hospital = hosp_lab_dict['hospital']
            lab = hosp_lab_dict['lab']
            available_lab_tests = lab.lab_pricing_group.available_lab_tests.all()
            for obj in available_lab_tests:
                ret_obj = dict()
                sample_objs = obj.sample_details.all() if hasattr(obj, 'sample_details') else None
                if not sample_objs or not obj.enabled:
                    continue
                ret_obj['hospital_id'] = hospital.id
                ret_obj['lab_id'] = lab.id
                ret_obj['lab_name'] = lab.name
                test_data = serializers.SelectedTestsDetailsSerializer(obj).data
                ret_obj.update(test_data)
                sample_data = serializers.PartnerLabTestSampleDetailsModelSerializer(sample_objs, many=True).data
                ret_obj['sample_data'] = sample_data
                # if sample_obj:
                #     sample_data = serializers.PartnerLabTestSampleDetailsModelSerializer(sample_obj).data
                #     ret_obj.update(sample_data)
                # else:
                #     ret_obj['sample_details_id'] = None
                #     ret_obj['created_at'] = None
                #     ret_obj['updated_at'] = None
                #     ret_obj['sample_name'] = None
                #     ret_obj['material_required'] = None
                #     ret_obj['sample_volume'] = None
                #     ret_obj['sample_volume_unit'] = None
                #     ret_obj['is_fasting_required'] = None
                #     ret_obj['report_tat'] = None
                #     ret_obj['reference_value'] = None
                #     ret_obj['instructions'] = None
                response_list.append(ret_obj)
        return Response(response_list)

    def order_create_or_update(self, request):
        serializer = serializers.SampleCollectOrderCreateOrUpdateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        order_obj = valid_data.get('order_obj')
        offline_patient = valid_data.get('offline_patient')
        hospital = valid_data.get('hospital')
        doctor = valid_data.get('doctor')
        lab = valid_data.get('lab')
        available_lab_tests = valid_data.get('available_lab_tests')
        lab_alerts = valid_data.get('lab_alerts')
        barcode_details = valid_data.get('barcode_details')
        status = valid_data.get('status')
        only_status_update = valid_data.get('only_status_update')
        if only_status_update:
            order_obj.status = status
            order_obj.save()
        else:
            sample_collection_objs = prov_models.PartnerLabTestSampleDetails.get_sample_collection_details(available_lab_tests)
            samples_data = serializers.LabTestSamplesCollectionBarCodeModelSerializer(sample_collection_objs, many=True,
                                                                                      context={"barcode_details": barcode_details}).data
            patient_details = v1_doc_serializers.OfflinePatientSerializer(offline_patient).data
            patient_details.update({'patient_mobile': str(offline_patient.get_patient_mobile())})
            selected_tests_details = serializers.SelectedTestsDetailsSerializer(available_lab_tests, many=True).data
            extras = {
                'test_count': len(available_lab_tests),
                'mrp_total': sum(test_detail["mrp"] for test_detail in selected_tests_details),
                'hospital_price_total': sum(test_detail["hospital_price"] for test_detail in selected_tests_details),
                'b2b_price_total': sum(test_detail["b2b_price"] for test_detail in selected_tests_details),
            }
            if not order_obj:
                order_obj = prov_models.PartnerLabSamplesCollectOrder(offline_patient=offline_patient,
                                                                      patient_details=patient_details,
                                                                      hospital=hospital, doctor=doctor, lab=lab,
                                                                      samples=samples_data, created_by=request.user,
                                                                      collection_datetime=valid_data.get("collection_datetime"),
                                                                      selected_tests_details=selected_tests_details,
                                                                      status=status,
                                                                      extras=extras)
            else:
                order_obj.status = status
                order_obj.samples = samples_data
                order_obj.collection_datetime = valid_data.get("collection_datetime")
                order_obj.selected_tests_details = selected_tests_details
                order_obj.extras = extras
            order_obj.save()
            if lab_alerts:
                order_obj.lab_alerts.set(lab_alerts, clear=True)
            order_obj.available_lab_tests.set(available_lab_tests, clear=True)
        order_model_serializer = serializers.PartnerLabSamplesCollectOrderModelSerializer(order_obj, context={'request': request})
        return Response({"status": 1, "message": "Sample Collection Order created successfully",
                         "data": order_model_serializer.data})

    def lab_alerts(self, request):
        lab_alerts_queryset = prov_models.TestSamplesLabAlerts.objects.all()
        data = serializers.TestSamplesLabAlertsModelSerializer(lab_alerts_queryset, many=True).data
        return Response(data)

    def orders_list(self, request):
        filter_kwargs = dict()
        if request.query_params.get('id'):
            filter_kwargs['id'] = request.query_params.get('id')
        queryset = prov_models.PartnerLabSamplesCollectOrder.objects.prefetch_related('lab_alerts', 'reports') \
                                                                    .filter(**filter_kwargs,
                                                                            hospital__manageable_hospitals__phone_number=request.user.phone_number).distinct()
        data = serializers.PartnerLabSamplesCollectOrderModelSerializer(queryset, context={'request': request}, many=True).data
        return Response(data)
