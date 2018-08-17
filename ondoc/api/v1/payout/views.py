from ondoc.payout.models import Outstanding
from ondoc.authentication import models as auth_model
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
from ondoc.api.v1.payout.serializers import BillingSummarySerializer, BillingSerializer
from ondoc.api.v1.doctor.serializers import OpdAppointmentBillingSerializer
from ondoc.api.v1.diagnostic.serializers import LabAppointmentBillingSerializer
from ondoc.api.v1.utils import get_previous_month_year
from ondoc.api.pagination import paginate_queryset
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import viewsets
from django.utils import timezone
from django.db.models import Q
from . import serializers


class BillingViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.OutstandingModelSerializer
    queryset = Outstanding.objects.all()
    permission_classes = (IsAuthenticated, )

    def list(self, request):
        params = request.query_params
        serializer = BillingSerializer(data=params)
        serializer.is_valid(raise_exception=True)
        billing_admin_id = serializer.validated_data.get("admin_id")
        level = serializer.validated_data.get("level")
        user = request.user
        if level in [Outstanding.HOSPITAL_NETWORK_LEVEL, Outstanding.HOSPITAL_LEVEL, Outstanding.DOCTOR_LEVEL]:
            user_admin_list = auth_model.GenericAdmin.get_user_admin_obj(user)
        elif level in [Outstanding.LAB_LEVEL, Outstanding.LAB_NETWORK_LEVEL]:
            user_admin_list = auth_model.GenericLabAdmin.get_user_admin_obj(user)
        resp_data = list()
        for user_admin in user_admin_list:
            admin_obj = user_admin['admin_obj']
            out_level = user_admin['admin_level']
            if billing_admin_id == admin_obj.id and level == out_level:
                self.form_billing_data(admin_obj, out_level, resp_data)

        return Response(resp_data)

    def form_billing_data(self, admin_obj, out_level, resp_data):
        out_obj = Outstanding.objects.filter(net_hos_doc_id=admin_obj.id, outstanding_level=out_level).order_by(
            'outstanding_year', 'outstanding_month')
        prev = None
        for obj in out_obj:
            temp_data = Outstanding.get_month_billing(prev, obj)
            resp_data.append(temp_data)
            prev = obj

    def current_billing(self, request):
        params = request.query_params
        user = request.user
        serializer = BillingSerializer(data=params)
        serializer.is_valid(raise_exception=True)
        billing_admin_id = serializer.validated_data.get("admin_id")
        level = serializer.validated_data.get("level")
        # user_admin_list = auth_model.GenericAdmin.get_user_admin_obj(user)
        user_admin_list = None
        if level in [Outstanding.HOSPITAL_NETWORK_LEVEL, Outstanding.HOSPITAL_LEVEL, Outstanding.DOCTOR_LEVEL]:
            user_admin_list = auth_model.GenericAdmin.get_user_admin_obj(user)
        elif level in [Outstanding.LAB_LEVEL, Outstanding.LAB_NETWORK_LEVEL]:
            user_admin_list = auth_model.GenericLabAdmin.get_user_admin_obj(user)
        resp_data = list()
        for user_admin in user_admin_list:
            admin_obj = user_admin['admin_obj']
            out_level = user_admin['admin_level']
            if billing_admin_id and level and billing_admin_id == admin_obj.id and level == out_level:
                self.form_cb_data(admin_obj, out_level, resp_data)
        return Response(resp_data)

    def form_cb_data(self, admin_obj, out_level, resp_data):
        now = timezone.now()
        present_month, present_year = now.month, now.year
        prev_month, prev_year = get_previous_month_year(present_month, present_year)

        out_obj = (Outstanding.objects.filter(net_hos_doc_id=admin_obj.id, outstanding_level=out_level).order_by(
            '-outstanding_year', '-outstanding_month'))[:2]

        if out_obj:
            prev_obj = None
            present_obj = None
            if out_obj.count() == 2 and out_obj[0].outstanding_year == present_year and out_obj[0].outstanding_month == present_month:
                present_obj = out_obj[0]
                prev_obj = out_obj[1]
            elif out_obj[0].outstanding_month == present_month and out_obj[0].outstanding_year == present_year:
                present_obj = out_obj[0]
            resp_data.append(Outstanding.get_month_billing(prev_obj, present_obj))

    def billing_summary(self, request):
        query_param = request.query_params
        serializer = BillingSummarySerializer(data=query_param)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        resp_data = []
        if valid_data.get('level') in [Outstanding.DOCTOR_LEVEL, Outstanding.HOSPITAL_LEVEL,
                                                   Outstanding.HOSPITAL_NETWORK_LEVEL]:
            resp_data = OpdAppointment.get_billing_summary(request.user, valid_data)
        elif valid_data.get('level') in [Outstanding.LAB_NETWORK_LEVEL, Outstanding.LAB_LEVEL]:
            resp_data = LabAppointment.get_billing_summary(request.user, valid_data)
        return Response(resp_data)

    def billing_appointments(self, request):
        query_param = request.query_params
        serializer = BillingSummarySerializer(data=query_param)
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        if valid_data.get('level') in [Outstanding.DOCTOR_LEVEL, Outstanding.HOSPITAL_LEVEL,
                                       Outstanding.HOSPITAL_NETWORK_LEVEL]:
            resp_queryset = OpdAppointment.get_billing_appointment(request.user, valid_data)
            resp_queryset = paginate_queryset(resp_queryset, request)
            serializer = OpdAppointmentBillingSerializer(resp_queryset, many=True, context={"request": request})
        elif valid_data.get('level') in [Outstanding.LAB_NETWORK_LEVEL, Outstanding.LAB_LEVEL]:
            resp_queryset = LabAppointment.get_billing_appointment(request.user, valid_data)
            resp_queryset = paginate_queryset(request, resp_queryset)
            serializer = LabAppointmentBillingSerializer(resp_queryset, many=True)
        # return Response([])
        return Response(serializer.data)
