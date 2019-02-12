from uuid import UUID
from ondoc.doctor import models as doc_models
from ondoc.authentication import models as auth_models
from django.utils.safestring import mark_safe
from . import serializers
from ondoc.api.v1 import utils as v1_utils
from django.shortcuts import get_object_or_404
from rest_framework import viewsets
from rest_framework import mixins
from rest_framework.response import Response
from rest_framework import status, permissions
from rest_framework.permissions import IsAuthenticated
from ondoc.authentication.backends import JWTAuthentication
from django.db import transaction
from django.db.models import Q, Value, Case, When, F
from django.contrib.auth import get_user_model
from django.conf import settings
import datetime, logging, re, random
from ondoc.doctor import models
from ondoc.api.v2.doctor import serializers as v2_serializers
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)


class DoctorBillingViewSet(viewsets.GenericViewSet):
    #
    # authentication_classes = (JWTAuthentication,)
    # permission_classes = (IsAuthenticated, v1_utils.IsDoctor)

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


class OndocViewSet(mixins.CreateModelMixin,
                   mixins.RetrieveModelMixin,
                   mixins.UpdateModelMixin,
                   mixins.ListModelMixin,
                   viewsets.GenericViewSet):
    pass


class DoctorPermission(permissions.BasePermission):
    message = 'Doctor is allowed to perform action only.'

    def has_permission(self, request, view):
        if request.user.user_type == User.DOCTOR:
            return True
        return False


class DoctorBlockCalendarViewSet(OndocViewSet):

    serializer_class = serializers.DoctorLeaveSerializer
    authentication_classes = (JWTAuthentication, )
    permission_classes = (IsAuthenticated, DoctorPermission,)
    INTERVAL_MAPPING = {models.DoctorLeave.INTERVAL_MAPPING.get(key): key for key in
                        models.DoctorLeave.INTERVAL_MAPPING.keys()}

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        if not hasattr(request.user, 'doctor') or not request.user.doctor:
            return Response([])
        serializer = serializers.DoctorBlockCalenderSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        doctor = validated_data.get("doctor_id").id
        if not doctor:
            doctor = request.user.doctor.id
        start_time = validated_data.get("start_time")
        if not start_time:
            start_time = self.INTERVAL_MAPPING[validated_data.get("interval")][0]
        end_time = validated_data.get("end_time")
        if not end_time:
            end_time = self.INTERVAL_MAPPING[validated_data.get("interval")][1]
        doctor_leave_data = {
            "doctor": doctor,
            "hospital": validated_data.get("hospital_id"),
            "start_time": start_time,
            "end_time": end_time,
            "start_date": validated_data.get("start_date"),
            "end_date": validated_data.get("end_date")
        }
        doctor_leave_serializer = v2_serializers.DoctorLeaveSerializer(data=doctor_leave_data)
        doctor_leave_serializer.is_valid(raise_exception=True)
        # self.get_queryset().update(deleted_at=timezone.now())        Now user can apply more than one leave
        doctor_leave_serializer.save()
        return Response(doctor_leave_serializer.data)
