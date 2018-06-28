from ondoc.payout import models as payout_model
from ondoc.authentication import models as auth_model
from ondoc.api.v1.utils import get_previous_month_year
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ondoc.api.pagination import paginate_queryset
from rest_framework import viewsets
from django.utils import timezone
from django.db.models import Q
from . import serializers


class BillingViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.OutstandingModelSerializer
    permission_classes = (IsAuthenticated, )

    def list(self, request):
        user = request.user
        admin_obj, out_level = auth_model.UserPermission.get_user_admin_obj(user)
        resp_data = list()

        self.form_billing_data(admin_obj, out_level, resp_data)

        return Response(resp_data)

    def form_billing_data(self, admin_obj, out_level, resp_data):
        out_obj = payout_model.Outstanding.objects.filter(net_hos_doc_id=admin_obj.id, outstanding_level=out_level)

        prev = None
        for obj in out_obj:
            resp_data.append(payout_model.Outstanding.get_month_billing(prev, obj))
            prev = obj

    def current_billing(self, request):
        user = request.user

        admin_obj, out_level = auth_model.UserPermission.get_user_admin_obj(user)
        resp_data = list()
        self.form_cb_data(admin_obj, out_level, resp_data)

        return Response(resp_data)

    def form_cb_data(self, admin_obj, out_level, resp_data):
        now = timezone.now()
        present_month, present_year = now.month, now.year
        prev_month, prev_year = get_previous_month_year(present_month, present_year)

        out_obj = (payout_model.Outstanding.objects.filter(net_hos_doc_id=admin_obj.id, outstanding_level=out_level).
                   filter(Q(outstanding_month=present_month, outstanding_year=present_year) |
                          Q(outstanding_month=prev_month, outstanding_year=prev_year)).
                   order_by('outstanding_year', 'outstanding_month'))
        if out_obj.exists():
            prev_obj = None
            present_obj = out_obj[0]
            if out_obj.count() == 2:
                prev_obj = out_obj[0]
                present_obj = out_obj[1]
            resp_data.append(payout_model.Outstanding.get_month_billing(prev_obj, present_obj))
