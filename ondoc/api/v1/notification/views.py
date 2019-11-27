from itertools import groupby

from ondoc.communications.models import EMAILNotification
from ondoc.doctor.models import Hospital
from ondoc.notification import models
from ondoc.api.v1.utils import IsNotAgent
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ondoc.api.pagination import paginate_queryset
from rest_framework import viewsets
from django.utils import timezone
from django.db import transaction
from . import serializers
from rest_framework import status

from django.shortcuts import HttpResponse
from django.views import View
from django.template import Context, Template
from ondoc.notification.models import DynamicTemplates, RecipientEmail, NotificationAction, IPDIntimateEmailNotification
from datetime import date


class AppNotificationViewSet(viewsets.GenericViewSet):
    serializer_class = serializers.AppNotificationSerializer
    permission_classes = (IsAuthenticated, IsNotAgent)

    @staticmethod
    def get_notification_ids_list(ids):
        ids = ids.split(',')
        if not isinstance(ids, list):
            ids = [ids]
        ids = [int(id_) for id_ in ids]
        return ids

    @staticmethod
    def append_unviewed_unread_count(data, queryset):
        result = dict()
        result["data"] = data
        result["unread_count"] = queryset.filter(read_at__isnull=True).count()
        result["unviewed_count"] = queryset.filter(viewed_at__isnull=True).count()
        return Response(result)

    def get_queryset(self):
        request = self.request
        return models.AppNotification.objects.filter(user=request.user)

    @transaction.non_atomic_requests
    def list(self, request):
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)

    def mark_notifications_as_viewed(self, request):
        viewed_time = timezone.now()
        required_notifications_ids = request.data.get("notificationids", None)
        if required_notifications_ids:
            required_notifications_ids = AppNotificationViewSet.get_notification_ids_list(required_notifications_ids)
            self.get_queryset().filter(pk__in=required_notifications_ids, viewed_at__isnull=True).update(
                viewed_at=viewed_time)
        else:
            self.get_queryset().filter(viewed_at__isnull=True).update(viewed_at=viewed_time)
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)

    def mark_notifications_as_read(self, request):
        read_at = timezone.now()
        viewed_at = read_at
        required_notifications_ids = request.data.get("notificationids", None)
        if required_notifications_ids:
            required_notifications_ids = AppNotificationViewSet.get_notification_ids_list(required_notifications_ids)
            self.get_queryset().filter(pk__in=required_notifications_ids, viewed_at__isnull=True).update(viewed_at=viewed_at)
            self.get_queryset().filter(pk__in=required_notifications_ids, read_at__isnull=True).update(read_at=read_at)
        else:
            self.get_queryset().filter(viewed_at__isnull=True).update(viewed_at=viewed_at)
            self.get_queryset().filter(read_at__isnull=True).update(read_at=read_at)
        queryset = self.get_queryset().order_by("-created_at")
        paginated_queryset = paginate_queryset(queryset, request)
        serializer = serializers.AppNotificationSerializer(paginated_queryset, many=True)
        return AppNotificationViewSet.append_unviewed_unread_count(serializer.data, queryset)


class ChatNotificationViewSet(viewsets.GenericViewSet):

    def chat_send(self, request):
        from ondoc.authentication.models import NotificationEndpoint
        from ondoc.communications.models import PUSHNotification, NotificationAction

        data = request.data

        if not data or not data.get('title') or not data.get('body') or not data.get('room_id') or not data.get('device_id'):
            return Response({"message":"Insufficient Data"}, status=status.HTTP_400_BAD_REQUEST)

        user_and_tokens = []
        user_and_token = [{'user': token.user, 'token': token.token, 'app_name': token.app_name} for token in
                          NotificationEndpoint.objects.filter(device_id__icontains=str(data.get('device_id')).lower()).order_by('user')]
        for user, user_token_group in groupby(user_and_token, key=lambda x: x['user']):
            user_and_tokens.append(
                {'user': user, 'tokens': [{"token": t['token'], "app_name": t["app_name"]} for t in user_token_group]})

        context = {
            "title" : data.get('title'),
            "body" : data.get('body'),
            "screen": data.get('screen', "chat"),
            "room_id": data.get('room_id'),
            "data_only": True
        }
        noti = PUSHNotification(NotificationAction.CHAT_NOTIFICATION, context)
        noti.send(user_and_tokens)
        return Response({"message": "Notification Sent"})


class DynamicTemplate(View):

    def get_invalid_content(self):
        content = '<p>Invalid Template</p>'
        t = Template(content)
        c = Context({})
        html = t.render(c)
        return html

    def get(self, request, template_name, *args, **kwargs):
        obj = DynamicTemplates.objects.filter(template_name=template_name).first()

        if not obj:
            return HttpResponse(self.get_invalid_content())

        if request.GET.get('send') == 'True':

            if obj.recipient:

                if obj.template_type == DynamicTemplates.TemplateType.EMAIL:
                    recipient_obj = RecipientEmail(obj.recipient)
                else:
                    recipient_obj = obj.recipient

                obj.send_notification(obj.get_parameter_json(), recipient_obj,
                                      NotificationAction.SAMPLE_DYNAMIC_TEMPLATE_PREVIEW, is_preview=True)

                html = "Notification send successfully."
            else:
                html = "Recipient Number or address found to send notification."

        else:

            html = obj.render_template(obj.get_parameter_json())

        return HttpResponse(html)


class IPDIntimateEmailNotificationViewSet(viewsets.GenericViewSet):

    def send_email_notification(self, request):
        parameters = request.data
        user_id = parameters.get('user')
        doctor_id = parameters.get('doctor')
        hospital_id = parameters.get('hospital')
        phone_number = parameters.get('phone_number')
        preferred_date = parameters.get('preferred_date', None)
        time_slot = parameters.get('time_slot', None)
        gender = parameters.get('gender', None)
        dob = parameters.get('dob', None)

        hosp_obj = Hospital.objects.filter(id=hospital_id)
        if hosp_obj:
            hosp_obj = hosp_obj[0]
        else:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'error': 'Hospital not found.'})

        ipd_email_obj = IPDIntimateEmailNotification.objects.filter(phone_number=phone_number, hospital_id=hospital_id, created_at__date=date.today())
        if ipd_email_obj:
            return Response({})

        spoc_details = hosp_obj.spoc_details.all()
        receivers = [{'user': user_id, 'email': spoc.email} for spoc in spoc_details]
        emails = list(map(lambda x: x.get('email'), receivers))

        ipd_email_obj = IPDIntimateEmailNotification.objects.create(user_id=user_id, doctor_id=doctor_id, hospital_id=hospital_id,
                                                    phone_number=phone_number,
                                                    preferred_date=preferred_date, time_slot=time_slot, gender=gender,
                                                    dob=dob, email_notifications=emails)

        email_notification = EMAILNotification(notification_type=NotificationAction.IPDIntimateEmailNotification,
                                               context={'instance': ipd_email_obj})
        email_notification.send(receivers)

        return Response({})