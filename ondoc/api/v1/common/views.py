from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from django.contrib.gis.geos import Point
from django.conf import settings
from django.utils import timezone
from weasyprint import HTML
from django.http import HttpResponse
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor
from ondoc.chat.models import ChatPrescription
from ondoc.notification.rabbitmq_client import publish_message
from . import serializers
from ondoc.common.models import Cities
from ondoc.common.utils import send_email, send_sms
from ondoc.authentication.backends import JWTAuthentication
from django.core.files.uploadedfile import SimpleUploadedFile
from openpyxl import load_workbook
from openpyxl.writer.excel import save_virtual_workbook
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
        from ondoc.api.v1.utils import generate_short_url
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
        prescription_url = "{}{}{}".format(settings.BASE_URL,
                                           "/api/v1/common/chat_prescription/",
                                           chat.name)
        short_url = generate_short_url(prescription_url)
        return Response({"url": short_url})

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


class UpdateXlsViewSet(viewsets.GenericViewSet):

    def update(self, request):
        serializer = serializers.XlsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.get_active_sheet()
        rows = [row for row in sheet.rows]
        columns = {i+1: column.value.strip().lower() for i, column in enumerate(rows[0])}
        for key in columns.keys():
            if columns.get(key) == 'number_of_results_on_search_page':
                search_count_column = key
        for i in range(2, len(rows)+1):
            sheet.cell(row=i, column=search_count_column).value = self.get_result_count(i, columns, sheet)
        response = HttpResponse(content=save_virtual_workbook(wb),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=myexport.xlsx'
        return response

    def prepare_query(self, column, value, query):
        if column == 'test_id' and value is not None and value != '':
            query.update({
                'lab_pricing_group__available_lab_tests__test_id__in': [int(value.strip()) for value in
                                                                        str(value).split(",")],
                'lab_pricing_group__available_lab_tests__enabled': True
            })
        elif column == 'lab_id' and value is not None and value != '':
            query.update({
                'id': int(value)
            })
        return query

    def get_result_count(self, row, columns, sheet):
        longitude, latitude, max_distance, search_count_column, report_type = None, None, None, None, None
        query = {}
        for key in columns.keys():
            cell_value = str(sheet.cell(row=row, column=key).value).strip() if sheet.cell(row=row,
                                                                                          column=key).value else None
            if columns.get(key) == 'longitude':
                longitude = float(cell_value) if cell_value else None
            elif columns.get(key) == 'latitude':
                latitude = float(cell_value) if cell_value else None
            elif columns.get(key) == 'radius_in_km':
                max_distance = int(cell_value) * 1000 if cell_value else None
            elif columns.get(key) == 'specialization_ids':
                specialization_ids = [int(value.strip()) for value in cell_value.split(",")] if cell_value else []
            elif columns.get(key) == 'type':
                report_type = cell_value
            self.prepare_query(columns.get(key), sheet.cell(row=row, column=key).value, query)

        if report_type == 'doctor':
            results = (Doctor.objects.filter(
                doctorspecializations__specialization__in=specialization_ids
            ) if specialization_ids else Doctor.objects.all())
            search_count = results.filter(
                hospitals__location__distance_lte=(Point(longitude, latitude), max_distance),
                is_live=True,
                is_test_doctor=False,
                is_internal=False,
                hospitals__is_live=True).count()
        else:
            query.update({
                'location__distance_lte': (Point(longitude, latitude), max_distance)
            })
            search_count = Lab.objects.filter(is_test_lab=False, is_live=True,
                                              lab_pricing_group__isnull=False).filter(**query).count()
        return search_count
