from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from weasyprint import HTML
from django.http import HttpResponse

from ondoc.chat.models import ChatPrescription
from ondoc.notification.rabbitmq_client import publish_message
from . import serializers
from ondoc.common.models import Cities
from ondoc.common.utils import send_email, send_sms
from ondoc.authentication.backends import JWTAuthentication
from django.core.files.uploadedfile import SimpleUploadedFile
import random
import string
import base64
import logging

logger = logging.getLogger(__name__)

class CitiesViewSet(viewsets.GenericViewSet):

    def get_queryset(self):
        return Cities.objects.all().order_by('name')

    def list(self, request):
        filter_text = request.GET.get('filter', None)
        if not filter_text:
            response = [{'value': city.id, 'name': city.name} for city in self.get_queryset()]
        else:
            response = [{'value': city.id, 'name': city.name} for city in self.get_queryset().filter(name__istartswith=filter_text)]
        return Response(response)


class ServicesViewSet(viewsets.GenericViewSet):

    def generatepdf(self, request):
        content = None
        try:
            coded_data = request.data.get('content')
            if isinstance(coded_data, list):
                coded_data = coded_data[0]
            coded_data += "=="
            content = base64.b64decode(coded_data).decode()
        except Exception as e:
            logger.error("Error in decoding base64 content with exception - " + str(e))

        if not content:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Content is required.'})
        pdf_file = HTML(string=content).write_pdf()
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        name = random_string + '.pdf'
        file = SimpleUploadedFile(name, pdf_file, content_type='application/pdf')
        chat = ChatPrescription.objects.create(name=name, file=file)
        return Response({"name": chat.name})

    def send_email(self, request):
        serializer = serializers.EmailServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to = serializer.validated_data.get('to')
        cc = serializer.validated_data.get('cc')
        to = list(set(to)) if isinstance(to, list) else []
        cc = list(set(cc)) if isinstance(cc, list) else []
        content = serializer.validated_data.get('content')
        subject = serializer.validated_data.get('subject')
        send_email(to, cc, subject, content)
        return Response({"status": "success"})

    def send_sms(self, request):
        serializer = serializers.SMSServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data.get('text')
        phone_number = serializer.validated_data.get('phone_number')
        phone_number = list(set(phone_number))
        send_sms(text, phone_number)
        return Response({"status": "success"})

    def download_pdf(self, request, name=None):
        chat_prescription = ChatPrescription.objects.filter(name=name).first()
        response = HttpResponse(chat_prescription.file, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename=%s' % chat_prescription.name
        return response


class SmsServiceViewSet(viewsets.GenericViewSet):
    authentication_classes = (JWTAuthentication, )

    def send_sms(self, request):
        serializer = serializers.SMSServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        text = serializer.validated_data.get('text')
        phone_number = [request.user.phone_number] if request.user else []
        phone_number = list(set(phone_number))
        send_sms(text, phone_number)
        return Response({"status": "success"})






