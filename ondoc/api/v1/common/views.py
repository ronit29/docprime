from rest_framework import mixins, viewsets, status
from rest_framework.response import Response
from django.contrib.gis.geos import Point, GEOSGeometry
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from weasyprint import HTML
from django.http import HttpResponse
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import (Doctor, DoctorPracticeSpecialization, PracticeSpecialization, DoctorMobile, Qualification,
                                 Specialization, College, DoctorQualification, DoctorExperience, DoctorAward,
                                 DoctorClinicTiming, DoctorClinic, Hospital, SourceIdentifier)

from ondoc.chat.models import ChatPrescription
from ondoc.notification.rabbitmq_client import publish_message
from django.template.loader import render_to_string
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
import datetime
import re
from django.db.models import Count
from io import BytesIO
import requests
from PIL import Image as Img
import os
import math

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

    def generate_pdf_template(self, request):
        from ondoc.api.v1.utils import generate_short_url
        context = {key: value for key, value in request.data.items()}
        if context.get('_updatedAt'):
            context['updated_at'] = parse_datetime(context.get('_updatedAt'))
        content = render_to_string("email/chat_prescription/body.html", context=context)
        pdf_file = HTML(string=content).write_pdf()
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        patient_profile = context.get('profile')
        patient_name = ''
        if patient_profile:
            patient_name = patient_profile.get('name', '')
        name = 'dp_{}_{}_{}.pdf'.format('_'.join(patient_name.lower().split()), datetime.datetime.now().date(), random_string)
        # name = random_string + '.pdf'
        file = SimpleUploadedFile(name, pdf_file, content_type='application/pdf')
        chat = ChatPrescription.objects.create(name=name, file=file)
        prescription_url = "{}{}{}".format(settings.BASE_URL,
                                           "/api/v1/common/chat_prescription/",
                                           chat.name)
        short_url = generate_short_url(prescription_url)
        return Response({"url": short_url})

    def send_email(self, request):
        context = {key: value for key, value in request.data.items()}
        if context.get('_updatedAt'):
            context['updated_at'] = parse_datetime(context.get('_updatedAt'))
        serializer = serializers.EmailServiceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to = serializer.validated_data.get('to')
        cc = serializer.validated_data.get('cc')
        to = list(set(to)) if isinstance(to, list) else []
        cc = list(set(cc)) if isinstance(cc, list) else []
        content = render_to_string("email/chat_prescription/body.html", context=context)
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


class UpdateXlsViewSet():
    fields = ['longitude', 'latitude', 'radius', 'specialty_id', 'lab_id', 'type', 'test_id']
    required_headers = fields+['result_count', 'url']

    def update(self, request):

        search_count_column = None
        serializer = serializers.XlsSerializer(data=request.FILES)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active

        rows = [row for row in sheet.rows]
        #columns = {i+1: column.value.strip().lower() for i, column in enumerate(rows[0]) if column.value}
        self.header = {column.value.strip().lower(): i + 1  for i, column in enumerate(rows[0]) if column.value}
        search_count_column = self.header.get('result_count')
        url_column = self.header.get('url')
        validation_url_column = self.header.get('validation_url')

        for i in range(2, len(rows)+1):
            data = self.get_data(i,sheet)
            output = self.get_result_count(data)
            sheet.cell(row=i, column=search_count_column).value = output[0]
            sheet.cell(row=i, column=url_column).value = output[1]
            sheet.cell(row=i, column=validation_url_column).value = output[2]

        response = HttpResponse(content=save_virtual_workbook(wb),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=myexport.xlsx'
        return response

    def get_data(self,row,sheet):
        data={}
        for key in self.fields:
            value = sheet.cell(row=row, column=self.header.get(key)).value
            if isinstance(value, str):
                value = value.strip().lower()
            if key in ['specialty_id','test_id']:
                value = [int(x) for x in str(value).split(',')] if value else []

            data[key] = value
        return data

    def get_result_count(self, data):
        if data['type']=='doctor' :
            return self.get_doctor_count(data);
        elif data['type']=='lab' :
            return self.get_lab_count(data);
        else :
            return 0

    def get_doctor_count(self, data):
        specialty_id = data['specialty_id']
        latitude = data['latitude']
        longitude = data['longitude']
        max_distance = 1000*data['radius']

        results = Doctor.objects.all()
        results = (Doctor.objects.filter(
            doctorpracticespecializations__specialization__in=specialty_id
            ) if len(specialty_id)>0 else Doctor.objects.all())

        search_count = results.filter(
            hospitals__location__distance_lte=(Point(longitude, latitude), max_distance),
            is_live=True,
            is_test_doctor=False,
            is_internal=False,
            hospitals__is_live=True).distinct().count()
        url = "{domain}/opd/searchresults?min_fees=0&max_fees=1500&sort_on=distance&is_available=false&is_female=false&doctor_name=&hospital_name=&conditions=&specializations={specialty_id}&lat={latitude}&long={longitude}&force_location=true".format(domain=settings.CONSUMER_APP_DOMAIN, specialty_id=','.join([str(x) for x in specialty_id]),latitude=str(latitude), longitude=str(longitude))
        validation_url = url+"&max_distance={max_distance}".format(max_distance=max_distance/1000)
        url = url + "&max_distance=20"
        return (search_count, url, validation_url)

    def get_lab_count(self, data):
        test_id = data['test_id']
        #lab_id = data['lab_id']
        latitude = data['latitude']
        longitude = data['longitude']
        max_distance = 1000*data['radius']

        filter = {'location__distance_lte': (Point(longitude, latitude), max_distance)}
        if len(test_id)>0:
            filter.update({
                'lab_pricing_group__available_lab_tests__test_id__in': test_id,
                'lab_pricing_group__available_lab_tests__enabled': True
            })
        count = 0

        search = Lab.objects.filter(is_test_lab=False, is_live=True,
                                          lab_pricing_group__isnull=False).filter(**filter)

        if len(test_id)>0:
            count = search.annotate(count=Count('id')).filter(count__gte=len(test_id)).count()
        else :
            count = search.count()

        url = "{domain}/lab/searchresults?min_distance=0&min_price=0&max_price=20000&sort_on=distancel&lab_name=&test_ids={test_id}&lat={latitude}&long={longitude}&force_location=true".format(domain=settings.CONSUMER_APP_DOMAIN, test_id=','.join([str(x) for x in test_id]),latitude=str(latitude), longitude=str(longitude))
        validation_url = url+"&max_distance={max_distance}".format(max_distance=max_distance/1000)
        url = url + "&max_distance=20"
        return (count, url, validation_url)

class UpdateXlsViewSet1():

    def update(self, request):
        search_count_column = None
        serializer = serializers.XlsSerializer(data=request.FILES)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active
        rows = [row for row in sheet.rows]
        columns = {i+1: column.value.strip().lower() for i, column in enumerate(rows[0]) if column.value}
        for key in columns.keys():
            if columns.get(key) == 'number_of_results_on_search_page':
                search_count_column = key
        if search_count_column:
            for i in range(2, len(rows)+1):
                sheet.cell(row=i, column=search_count_column).value = self.get_result_count(i, columns, sheet)
            response = HttpResponse(content=save_virtual_workbook(wb),
                                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            response['Content-Disposition'] = 'attachment; filename=myexport.xlsx'
            return response
        return None

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
                doctorpracticespecializations__specialization__in=specialization_ids
            ) if specialization_ids else Doctor.objects.all())
            search_count = results.filter(
                hospitals__location__distance_lte=(Point(longitude, latitude), max_distance),
                is_live=True,
                is_test_doctor=False,
                is_internal=False,
                hospitals__is_live=True).distinct().count()
        else:
            query.update({
                'location__distance_lte': (Point(longitude, latitude), max_distance)
            })
            search_count = Lab.objects.filter(is_test_lab=False, is_live=True,
                                              lab_pricing_group__isnull=False).filter(**query).distinct().count()
        return search_count


class UploadDoctorViewSet(viewsets.GenericViewSet):

    def upload(self, request):
        serializer = serializers.XlsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            doctor = self.create_doctor(row=i, sheet=sheet, headers=headers)
            self.map_doctor_specialization(row=i, sheet=sheet, headers=headers, doctor=doctor)
            self.add_doctor_phone_numbers(row=i, sheet=sheet, headers=headers, doctor=doctor)
            sheet.cell(row=i, column=headers.get('doctor_id')).value = doctor.id
        response = HttpResponse(content=save_virtual_workbook(wb),
                                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename=myexport.xlsx'
        return response

    def create_doctor(self, row, sheet, headers):
        gender_mapping = {value[1]: value[0] for value in Doctor.GENDER_CHOICES}
        doctor_name = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_name')).value)
        gender = gender_mapping.get(
            self.clean_data(sheet.cell(row=row, column=headers.get('gender')).value))
        practicing_since = self.clean_data(sheet.cell(row=row, column=headers.get('practicing_since')).value)
        city = self.clean_data(sheet.cell(row=row, column=headers.get('city')).value)
        doctor, created = Doctor.objects.get_or_create(name=doctor_name, gender=gender,
                                                       practicing_since=practicing_since, source='pr')
        self.save_image(row, sheet, headers, doctor.id)
        return doctor

    def save_image(self, row, sheet, headers, doctor_id):
        url = self.clean_data(sheet.cell(row=row, column=headers.get('image_url')).value)
        if url:
            r = requests.get(url)
            content = BytesIO(r.content)
            path = settings.MEDIA_ROOT+'/temp/image/'+str(doctor_id)+'.jpg'
            final_path = settings.MEDIA_ROOT+'/temp/final/'+str(doctor_id)+'.jpg'
            if os.path.exists(path):
                os.remove(path)
            if os.path.exists(final_path):
                os.remove(final_path)

            of = open(path, 'xb')
            of.write(content.read())
            of.close()
            img = Img.open(path)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            size = img.size
            bottom = math.floor(size[1]*.8)
            img = img.crop((0,0,size[0],bottom))

            img.save(final_path, format='JPEG')
            # new_image_io.tell()
            # ff = open(final_path, 'xb')
            # ff.write(new_image_io.read())
            # ff.close()

    def map_doctor_specialization(self, row, sheet, headers, doctor):
        practice_specialization_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('practice_specialization_id')).value)
        practice_specialization = PracticeSpecialization.objects.filter(pk=practice_specialization_id).first()
        if practice_specialization and doctor:
            DoctorPracticeSpecialization.objects.get_or_create(doctor=doctor, specialization=practice_specialization)

    def add_doctor_phone_numbers(self, row, sheet, headers, doctor):
        primary_number = self.clean_data(sheet.cell(row=row, column=headers.get('primary_number')).value)
        alternate_number_1 = self.clean_data(sheet.cell(row=row, column=headers.get('alternate_number_1')).value)
        alternate_number_2 = self.clean_data(sheet.cell(row=row, column=headers.get('alternate_number_2')).value)
        primary_number = re.sub(r'[\s-]+', '', primary_number) if primary_number and isinstance(primary_number,
                                                                                                str) else primary_number
        alternate_number_1 = re.sub(r'[\s-]+', '', alternate_number_1) if alternate_number_1 and isinstance(
            alternate_number_1,
            str) else alternate_number_1
        alternate_number_2 = re.sub(r'[\s-]+', '', alternate_number_2) if alternate_number_1 and isinstance(
            alternate_number_2,
            str) else alternate_number_2
        if primary_number:
            DoctorMobile.objects.get_or_create(doctor=doctor, number=int(primary_number), is_primary=True)
        if alternate_number_1:
            DoctorMobile.objects.get_or_create(doctor=doctor, number=int(alternate_number_1))
        if alternate_number_2:
            DoctorMobile.objects.get_or_create(doctor=doctor, number=int(alternate_number_2))

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value


class UploadQualificationViewSet(viewsets.GenericViewSet):

    def upload(self, request):
        serializer = serializers.XlsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            doctor = self.get_doctor(i, sheet, headers)
            qualification = self.get_qualification(i, sheet, headers)
            specialization = self.get_specialization(i, sheet, headers)
            college = self.get_college(i, sheet, headers)
            passing_year = self.clean_data(sheet.cell(row=i, column=headers.get('passing_year')).value)
            DoctorQualification.objects.get_or_create(doctor=doctor,
                                                      qualification=qualification,
                                                      college=college,
                                                      specialization=specialization,
                                                      passing_year=passing_year)
        return Response(data={'message': 'success'})

    def get_doctor(self, row, sheet, headers):
        doctor_id = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_id')).value)
        return Doctor.objects.filter(pk=doctor_id).first()

    def get_qualification(self, row, sheet, headers):
        dp_qualification_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('dp_qualification_id')).value)
        qualification_name = self.clean_data(sheet.cell(row=row, column=headers.get('qualification')).value)
        if dp_qualification_id and Qualification.objects.filter(pk=dp_qualification_id).exists():
            return Qualification.objects.filter(pk=dp_qualification_id).first()
        else:
            obj, create = Qualification.objects.get_or_create(name=qualification_name)
            return obj

    def get_specialization(self, row, sheet, headers):
        dp_specialization_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('dp_specialization_id')).value)
        specialization_name = self.clean_data(sheet.cell(row=row, column=headers.get('specialization')).value)
        if dp_specialization_id and Specialization.objects.filter(pk=dp_specialization_id).exists():
            return Specialization.objects.filter(pk=dp_specialization_id).first()
        else:
            obj, create = Specialization.objects.get_or_create(name=specialization_name)
            return obj

    def get_college(self, row, sheet, headers):
        dp_college_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('dp_college_id')).value)
        college_name = self.clean_data(sheet.cell(row=row, column=headers.get('college')).value)
        if dp_college_id and College.objects.filter(pk=dp_college_id).exists():
            return College.objects.filter(pk=dp_college_id).first()
        else:
            obj, create = College.objects.get_or_create(name=college_name)
            return obj

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value


class UploadExperienceViewSet(viewsets.GenericViewSet):

    def upload(self, request):
        serializer = serializers.XlsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            doctor = self.get_doctor(i, sheet, headers)
            hospital = self.clean_data(sheet.cell(row=i, column=headers.get('hospital')).value)
            start_year = self.clean_data(sheet.cell(row=i, column=headers.get('start_year')).value)
            end_year = self.clean_data(sheet.cell(row=i, column=headers.get('end_year')).value)
            DoctorExperience.objects.get_or_create(doctor=doctor, start_year=start_year, end_year=end_year,
                                                   hospital=hospital)
        return Response(data={'message': 'success'})

    def get_doctor(self, row, sheet, headers):
        doctor_id = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_id')).value)
        return Doctor.objects.filter(pk=doctor_id).first()

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value


class UploadAwardViewSet(viewsets.GenericViewSet):

    def upload(self, request):
        serializer = serializers.XlsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            doctor = self.get_doctor(i, sheet, headers)
            award = self.clean_data(sheet.cell(row=i, column=headers.get('award')).value)
            year = self.clean_data(sheet.cell(row=i, column=headers.get('year')).value)
            if award and year:
                DoctorAward.objects.get_or_create(doctor=doctor, year=year)
        return Response(data={'message': 'success'})

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value

    def get_doctor(self, row, sheet, headers):
        doctor_id = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_id')).value)
        return Doctor.objects.filter(pk=doctor_id).first()


class UploadHospitalViewSet(viewsets.GenericViewSet):

    def upload(self, request):
        serializer = serializers.XlsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated_data = serializer.validated_data
        reverse_day_map = {value[1]: value[0] for value in DoctorClinicTiming.SHORT_DAY_CHOICES}

        file = validated_data.get('file')
        wb = load_workbook(file)
        sheet = wb.active
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}

        doctor_obj_dict = dict()
        hospital_obj_dict = dict()
        doc_clinic_obj_dict = dict()
        for i in range(2, len(rows) + 1):
            doctor_obj = self.get_doctor(i, sheet, headers, doctor_obj_dict)
            if not doctor_obj:
                continue
            hospital_obj = self.get_hospital(i, sheet, headers, hospital_obj_dict)
            doc_clinic_obj = self.get_doc_clinic(doctor_obj, hospital_obj, doc_clinic_obj_dict)
            day_list = self.parse_day_range(sheet.cell(row=i, column=headers.get('day_range')).value, reverse_day_map)
            start, end = self.parse_timing(sheet.cell(row=i, column=headers.get('timing')).value)
            clinic_time_data = list()
            for day in day_list:
                temp_data = {
                    "doctor_clinic": doc_clinic_obj,
                    "day": day,
                    "start": start,
                    "end": end,
                    "fees": sheet.cell(row=i, column=headers.get('fee')).value
                }
                clinic_time_data.append(DoctorClinicTiming(**temp_data))
            if clinic_time_data:
                DoctorClinicTiming.objects.bulk_create(clinic_time_data)

        return Response(data={'message': 'success'})

    def get_hospital(self, row, sheet, headers, hospital_obj_dict):
        hospital_identifier = sheet.cell(row=row, column=headers.get('hospital_url')).value
        if hospital_obj_dict.get(hospital_identifier):
            hospital_obj = hospital_obj_dict.get(hospital_identifier)
        else:
            si_obj = SourceIdentifier.objects.filter(type=SourceIdentifier.HOSPITAL,
                                                     unique_identifier=hospital_identifier).first()
            if si_obj:
                hospital_obj = Hospital.objects.filter(pk=si_obj.reference_id).first()
            else:
                hospital_name = sheet.cell(row=row, column=headers.get('hospital_name')).value
                address = sheet.cell(row=row, column=headers.get('address')).value
                location = self.parse_gaddress(sheet.cell(row=row, column=headers.get('gaddress')).value)
                hospital_obj = Hospital.objects.create(name=hospital_name, building=address, location=location)
                SourceIdentifier.objects.create(reference_id=hospital_obj.id, unique_identifier=hospital_identifier,
                                                type=SourceIdentifier.HOSPITAL)
            hospital_obj_dict[hospital_identifier] = hospital_obj
        return hospital_obj

    def get_doc_clinic(self, doctor_obj, hospital_obj, doc_clinic_obj_dict):
        print(doctor_obj, hospital_obj, "hello")
        if doc_clinic_obj_dict.get((doctor_obj, hospital_obj)):
            doc_clinic_obj = doc_clinic_obj_dict.get((doctor_obj, hospital_obj))
        else:
            doc_clinic_obj, is_field_created = DoctorClinic.objects.get_or_create(doctor=doctor_obj, hospital=hospital_obj)
            doc_clinic_obj_dict[(doctor_obj, hospital_obj)] = doc_clinic_obj

        return doc_clinic_obj

    def parse_gaddress(self, address):
        print("\n",address, "HELLO")
        address = address.strip().split("/")
        lat_long = address[-1]
        lat_long_list = lat_long.strip().split(",")
        pnt = None
        if len(lat_long_list) == 2 and "null" not in lat_long_list:
            point_string = 'POINT(' + str(lat_long_list[1].strip()) + ' ' + str(lat_long_list[0].strip()) + ')'
            pnt = GEOSGeometry(point_string, srid=4326)
        return pnt

    def parse_day_range(self, day_range, reverse_day_map):
        temp_list = day_range.split(',')
        days_list = list()
        for dr in temp_list:
            dr = dr.strip()
            rng_str = dr.split("-")
            if len(rng_str) == 1:
                days_list.append(reverse_day_map[rng_str[0].strip()])
            elif len(rng_str) == 2:
                s = reverse_day_map[rng_str[0].strip()]
                e = reverse_day_map[rng_str[1].strip()]
                for i in range(s, e + 1):
                    days_list.append(i)
        return days_list

    def parse_timing(self, timing):
        tlist = timing.strip().split("-")
        start = None
        end = None
        if len(tlist) == 2:
            start = self.time_to_float(tlist[0])
            end = self.time_to_float(tlist[1])
        return start, end

    def time_to_float(self, time):
        hour_min, am_pm = time.strip().split(" ")
        hour, minute = hour_min.strip().split(":")
        hour = self.hour_to_int(int(hour.strip()), am_pm)
        minute = self.min_to_float(int(minute.strip()))
        return hour + minute

    def hour_to_int(self, hour, am_pm):
        if am_pm == "PM":
            if hour < 12:
                hour += 12
        elif am_pm == "AM":
            if hour >= 12:
                hour = 0
        return hour

    def min_to_float(self, minute):
        NUM_SLOTS_MIN = 2
        # print(float(minute)/60, "HI", minute, "HELLO", round(minute/60,2))
        minute = round(round(float(minute) / 60, 2) * NUM_SLOTS_MIN) / NUM_SLOTS_MIN
        return minute

    def get_doctor(self, row, sheet, headers, doctor_obj_dict):
        doctor_identifier = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_identifier')).value)
        if doctor_obj_dict.get(doctor_identifier):
            doctor_obj = doctor_obj_dict.get(doctor_identifier)
        else:
            # doctor_id = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_id')).value)
            si_obj = SourceIdentifier.objects.filter(type=SourceIdentifier.DOCTOR, unique_identifier=doctor_identifier).first()
            doctor_obj = None
            if si_obj:
                doctor_obj = Doctor.objects.get(pk=si_obj.reference_id)
            doctor_obj_dict[doctor_identifier] = doctor_obj
        return doctor_obj

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value
