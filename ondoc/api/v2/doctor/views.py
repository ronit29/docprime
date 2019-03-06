from uuid import UUID
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as lab_models
from ondoc.authentication import models as auth_models
from django.utils.safestring import mark_safe
from . import serializers
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
from django.contrib.contenttypes.models import ContentType
from ondoc.procedure.models import Procedure
from django.contrib.auth import get_user_model
from django.conf import settings
import datetime, logging, re, random
from django.utils import timezone

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

    def list(self, request):
        user = request.user
        queryset = auth_models.GenericAdmin.objects.select_related('doctor', 'hospital')\
                                                   .prefetch_related('hospital__hospital_doctors', 'hospital__hospital_doctors__doctor',
                                                                     'hospital__merchant', 'hospital__merchant__merchant',
                                                                     'doctor__merchant', 'doctor__merchant__merchant',
                                                                     'doctor__doctor_clinics', 'doctor__doctor_clinics__hospital')\
                                                   .filter(user=user, is_disabled=False)
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
        return Response(entities)


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

    def create_leave_data(self, hospital_id, validated_data, start_time, end_time):
        return {
                    "doctor": validated_data.get('doctor_id').id,
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

        if not start_time:
            start_time = self.INTERVAL_MAPPING[validated_data.get("interval")][0]
        if not end_time:
            end_time = self.INTERVAL_MAPPING[validated_data.get("interval")][1]
        if not hospital_id:
            assoc_hospitals = validated_data.get('doctor_id').hospitals.all()
            for hospital in assoc_hospitals:
                doctor_leave_data.append(self.create_leave_data(hospital.id, validated_data, start_time, end_time))
        else:
            doctor_leave_data.append(self.create_leave_data(hospital_id, validated_data, start_time, end_time))

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
        serializer = serializers.GenerateOtpSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        phone_number = valid_data.get('phone_number')
        retry_send = request.query_params.get('retry', False)
        send_otp("OTP for login is {}", phone_number, retry_send)
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

        # auth_models.GenericAdmin.update_user_admin(phone_number)
        # auth_models.GenericLabAdmin.update_user_lab_admin(phone_number)
        # self.update_live_status(phone_number)

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
            doc_models.ProviderSignupLead.objects.filter(user=user).update(is_docprime=is_docprime)
            return Response({"status":1, "message":"consent updated"})
        except Exception as e:
            logger.error('Error updating consent: ' + str(e))
            return Response({"status": 0, "message": "Error updating consent - " + str(e)}, status.HTTP_400_BAD_REQUEST)

    def bulk_create_doctors(self, doctor_details):
        doc_obj_list = list()
        for doctor in doctor_details:
            name = doctor.get('name')
            online_consultation_fees = doctor.get('online_consultation_fees')
            doc_obj_list.append(doc_models.Doctor(name=name, online_consultation_fees=online_consultation_fees,
                                                  enabled=False, source_type=doc_models.Hospital.PROVIDER))
        created_doctors = doc_models.Doctor.objects.bulk_create(doc_obj_list)
        return created_doctors

    def bulk_create_doctor_clinics(self, hospital, doctors):
        doctor_clinic_obj_list = list()
        for doctor in doctors:
            doctor_clinic_obj_list.append(doc_models.DoctorClinic(doctor=doctor, hospital=hospital,
                                                                  enabled=False))
        created_doctor_clinics = doc_models.DoctorClinic.objects.bulk_create(doctor_clinic_obj_list)
        return created_doctor_clinics

    # def build_dict(seq, key):
    #     return dict((d[key], dict(d, index=index)) for (index, d) in enumerate(seq))

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

    # def bulk_create_doctors_and_doctor_clinics(self, hospital, doctors, *args, **kwargs):
    #     doc_obj_list = list()
    #     doctor_clinic_obj_list = list()
    #     doctor_mobile_obj_list = list()
    #     generic_admin_obj_list = list()
    #     for doctor in doctors:
    #         doc_obj_list.append(doc_models.Doctor(name=doctor.get('name'), enabled=False,
    #                                               source_type=doc_models.Hospital.PROVIDER))
    #     doctor_objects = doc_models.Doctor.objects.bulk_create(doc_obj_list)
    #     doctor_model_serializer = serializers.DoctorModelSerializer(doctor_objects, many=True)
    #     for counter, doctor in enumerate(doctor_objects):
    #         doctor_clinic_obj_list.append(doc_models.DoctorClinic(doctor=doctor, hospital=hospital,
    #                                                               enabled=False))
    #         doctor_mobile_obj_list.append(doc_models.DoctorMobile(doctor=doctor, is_primary=True,
    #                                                               number=doctors[counter].get('phone_number')))
    #         generic_admin_obj_list.append(auth_models.GenericAdmin(doctor=doctor, hospital=hospital,
    #                                                                number=doctors[counter].get('phone_number'),
    #                                                                source_type=auth_models.GenericAdmin.APP,
    #                                                                entity_type=auth_models.GenericAdmin.DOCTOR,
    #                                                                write_permission=True))
    #     doctor_clinic_objects = doc_models.DoctorClinic.objects.bulk_create(doctor_clinic_obj_list)
    #     doctor_clinic_model_serializer = serializers.DoctorClinicModelSerializer(doctor_clinic_objects,
    #                                                                              many=True)
    #     doctor_mobile_objects = doc_models.DoctorMobile.objects.bulk_create(doctor_mobile_obj_list)
    #     doctor_mobile_model_serializer = serializers.DoctorMobileModelSerializer(doctor_mobile_objects,
    #                                                                              many=True)
    #
    #     return (doctor_model_serializer.data, doctor_clinic_model_serializer.data, doctor_mobile_model_serializer.data)

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

    # def hospital_generic_admins_creation_flow(self, hospital, hospital_generic_admin_details):
    #     created_hospital_generic_admins = self.bulk_create_hospital_generic_admins(hospital,
    #                                                                                hospital_generic_admin_details)
    #     hospital_generic_admin_model_serializer = serializers.GenericAdminModelSerializer(
    #         created_hospital_generic_admins,
    #         many=True)
    #     hospital_generic_admins_data = hospital_generic_admin_model_serializer.data
    #     return hospital_generic_admins_data

    def create_hospital(self, request, *args, **kwargs):
        serializer = serializers.CreateHospitalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        valid_data['enabled'] = False
        valid_data['enabled_for_online_booking'] = False
        valid_data['is_mask_number_required'] = False
        valid_data['source_type'] = doc_models.Hospital.PROVIDER
        contact_number = valid_data.get('contact_number')
        doctor_details = valid_data.get('doctors')
        hospital_generic_admin_details = valid_data.get('staffs')
        doctors_data = None
        # doctor_clinics_data = None
        # doctors_mobile_data = None
        doctors_generic_admin_data = None
        hospital_generic_admins_data = None
        try:
            hospital = doc_models.Hospital.objects.create(name=valid_data.get('name'),
                                                          # city=valid_data.get('city'),
                                                          # state=valid_data.get('state'),
                                                          country=valid_data.get('country'),
                                                          source_type=doc_models.Hospital.PROVIDER)
            hospital_model_serializer = serializers.HospitalModelSerializer(hospital, many=False)
            auth_models.GenericAdmin.objects.create(user=request.user, phone_number=request.user.phone_number,
                                                    hospital=hospital, super_user_permission=True,
                                                    entity_type=auth_models.GenericAdmin.HOSPITAL)
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
                             # "doctor_clinics": doctor_clinics_data if doctor_clinics_data else None,
                             "doctors_generic_admins": doctors_generic_admin_data if doctors_generic_admin_data else None,
                             # "doctors_mobile": doctors_mobile_data if doctors_mobile_data else None,
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
                             # "doctor_clinics": doctor_clinics_data if doctor_clinics_data else None,
                             "doctors_generic_admins": doctors_generic_admin_data if doctors_generic_admin_data else None,
                             # "doctors_mobile": doctors_mobile_data if doctors_mobile_data else None,
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
