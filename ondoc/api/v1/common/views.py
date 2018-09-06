from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from weasyprint import HTML
from django.http import HttpResponse

from ondoc.chat.models import ChatPrescription
from ondoc.notification.rabbitmq_client import publish_message
from . import serializers
from ondoc.common.models import Cities
from ondoc.common.utils import send_email
from django.core.files.uploadedfile import SimpleUploadedFile
import random
import string
import json


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
        content = request.data.get('content')
        if not content:
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'Content is required.'})
        pdf_file = HTML(string=content).write_pdf()
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        name = random_string + '.pdf'
        file = SimpleUploadedFile(name, pdf_file, content_type='application/pdf')
        chat = ChatPrescription.objects.create(name=name, file=file)
        return Response({"name": chat.name})

    def send_email(self, request):
        resp = {}
        serializer = serializers.EmailServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to = serializer.validated_data.get('to')
        cc = serializer.validated_data.get('cc')
        content = serializer.validated_data.get('content')
        subject = serializer.validated_data.get('subject')
        send_email(to, cc, subject, content)
        resp['status'] = 'success'
        return Response(resp)

    # def send_sms(self, request):
    #     resp = {}
    #     serializer = serializers.SMSServiceSerializer(data=request.data)
    #     serializer.is_valid(raise_exception=True)
    #     name = serializer.validated_data.get('name')
    #     mobile = serializer.validated_data.get('mobile')
    #     send_sms(name, mobile)
    #     resp['status'] = 'success'

