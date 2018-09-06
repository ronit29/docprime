from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from django.utils import timezone
from weasyprint import HTML
from django.http import HttpResponse

from ondoc.notification.rabbitmq_client import publish_message
from . import serializers
from ondoc.common.models import Cities
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
        response = HttpResponse(pdf_file, content_type='application/pdf')
        response['Content-Disposition'] = 'filename="home_page.pdf"'
        return response

    def send_email(self, request):
        serializer = serializers.EmailServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        message = {
            "data": dict(validated_data),
            "type": "email"
        }
        message = json.dumps(message)
        publish_message(message)
        return Response(validated_data)

    def send_sms(self, request):
        
