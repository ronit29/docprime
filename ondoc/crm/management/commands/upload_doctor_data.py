from django.core.management.base import BaseCommand
from django.conf import settings
from io import BytesIO
from openpyxl import load_workbook
import requests
import re
from PIL import Image as Img
import os
import math
from django.core.files.storage import default_storage
from ondoc.doctor.models import (Doctor, DoctorPracticeSpecialization, PracticeSpecialization, DoctorMobile, Qualification,
                                 Specialization, College, DoctorQualification, DoctorExperience, DoctorAward,
                                 DoctorClinicTiming, DoctorClinic, Hospital, SourceIdentifier, DoctorAssociation)
from django.contrib.gis.geos import Point, GEOSGeometry


class Command(BaseCommand):
    help = 'Upload doctors via Excel'

    def add_arguments(self, parser):
        parser.add_argument('source', type=str, help='data source')
        parser.add_argument('batch', type=int, help='data batch')
        parser.add_argument('url', type=str, help='data url')

    def handle(self, *args, **options):

        print(options)
        source = options['source']
        batch = options['batch']
        url = options['url']

        r = requests.get(url)
        content = BytesIO(r.content)
        wb = load_workbook(content)
        sheets = wb.worksheets
        doctor = UploadDoctor()
        qualification = UploadQualification()
        experience = UploadExperience()
        membership = UploadMembership()
        award = UploadAward()
        hospital = UploadHospital()

        doctor.upload(sheets[0], source, batch)
        qualification.upload(sheets[1])
        experience.upload(sheets[2])
        membership.upload(sheets[3])
        award.upload(sheets[4])
        hospital.upload(sheets[5], source, batch)


class Doc():

    def get_doctor(self, doctor_identifier):
        si_obj = SourceIdentifier.objects.filter(type=SourceIdentifier.DOCTOR, unique_identifier=doctor_identifier).first()
        doctor_obj = None
        if si_obj:
            doctor_obj = Doctor.objects.get(pk=si_obj.reference_id)
        return doctor_obj

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value


class UploadDoctor(Doc):

    def upload(self, sheet, source, batch):
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}

        for i in range(2, len(rows) + 1):
            data = self.get_data(row=i, sheet=sheet, headers=headers)
            doctor = self.create_doctor(data, source, batch)
            self.map_doctor_specialization(doctor, data.get('practice_specialization'))
            try:
                self.add_doctor_phone_numbers(doctor, data.get('numbers'))
            except:
                print('error in saving phone number')

    def get_data(self, row, sheet, headers):
        gender_mapping = {value[1]: value[0] for value in Doctor.GENDER_CHOICES}

        gender = gender_mapping.get(self.clean_data(sheet.cell(row=row, column=headers.get('gender')).value))
        identifier = self.clean_data(sheet.cell(row=row, column=headers.get('identifier')).value)
        name = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_name')).value)
        license = self.clean_data(sheet.cell(row=row, column=headers.get('license')).value)
        city = self.clean_data(sheet.cell(row=row, column=headers.get('city')).value)
        practicing_since = self.clean_data(sheet.cell(row=row, column=headers.get('practicing_since')).value)

        if practicing_since:
            try:
                practicing_since = int(practicing_since)
            except:
                print('Invalid Practicing since='+str(practicing_since))
                practicing_since = None



        practice_specialization_id = self.clean_data(sheet.cell(row=row, column=headers.get('practice_specialization_id')).value)
        practice_specialization = None
        if practice_specialization_id:
            practice_specialization = PracticeSpecialization.objects.filter(pk=practice_specialization_id).first()

        number_entry = []
        primary_number = self.clean_data(sheet.cell(row=row, column=headers.get('primary_number')).value)
        alternate_number_1 = self.clean_data(sheet.cell(row=row, column=headers.get('alternate_number_1')).value)
        alternate_number_2 = self.clean_data(sheet.cell(row=row, column=headers.get('alternate_number_2')).value)

        num = self.get_number(primary_number, True, city)
        if num:
            number_entry.append(num)

        num = self.get_number(alternate_number_1, False, city)
        if num:
            number_entry.append(num)

        num = self.get_number(alternate_number_2, False, city)
        if num:
            number_entry.append(num)

        image_url = self.clean_data(sheet.cell(row=row, column=headers.get('image_url')).value)

        data = {}
        if not license:
            license=''

        data['gender'] = gender
        data['identifier'] = identifier
        data['name'] = name
        data['practicing_since'] = practicing_since
        data['practice_specialization'] = practice_specialization
        data['numbers'] = number_entry
        data['image_url'] = image_url
        data['license'] = license
        return data


    def get_number(self, number, is_primary, city):
        code=[11,44,22,129,40,120,33,215,124]
        data = {}
        std_code = None
        phone = None
        number = str(number).lstrip('0').strip()
        number = re.sub('[^0-9]+', ' ', number).strip()
        comps = number.split(' ')
        #print(number)
        if not number:
            return None

        if len(comps)==3 and comps[0] and comps[1] and comps[2]:
            return {'std_code':comps[0],'number':comps[1]+comps[2],'is_primary':False}
        elif len(comps)==2 and comps[0] and comps[1]:
            return {'std_code':comps[0],'number':comps[1],'is_primary':False}
        elif len(comps)>3:
            print('invalid number' + str(number))

        for cd in code:
            if number.startswith(str(cd)):
                data['std_code'] = cd
                data['number'] = number.replace(str(cd), '', 1)
                data['is_primary'] = False
                return data
        #print(number)
        try:
            number = int(number)
            if number < 5000000000 or number > 9999999999:
                print('invalid number' + str(number))
                return None
        except Exception as e:
            print(e)
            print('invalid number while parsing '+str(number))
            return None

        return {'number': number, 'is_primary': is_primary}

    def create_doctor(self, data, source, batch):

        doctor = self.get_doctor(data.get('identifier'))
        if doctor:
            return doctor

        doctor = Doctor.objects.create(name=data['name'], license=data.get('license',''), gender=data['gender'],
                                                       practicing_since=data['practicing_since'], source=source, batch=batch, enabled=False)
        SourceIdentifier.objects.create(type=SourceIdentifier.DOCTOR, unique_identifier=data.get('identifier'), reference_id=doctor.id)
        self.save_image(batch,data.get('image_url'),data.get('identifier'))
        return doctor

    def save_image(self, batch, url, identifier):
        if url and identifier:
            #path = settings.MEDIA_ROOT+'/temp/image/'+identifier + '.jpg'
            #final_path = settings.MEDIA_ROOT+'/temp/final/'+identifier + '.jpg'
            path = 'temp/image/'+identifier + '.jpg'
            final_path = 'temp/final/'+identifier + '.jpg'

            if default_storage.exists(path):
                return None
            # if os.path.exists(path):
            #     return None

            # file = default_storage.open('storage_test', 'w')
            # file.write('storage contents')
            # file.close()


            r = requests.get(url)
            content = BytesIO(r.content)

            # if os.path.exists(path):
            #     os.remove(path)
            # if os.path.exists(final_path):
            #     os.remove(final_path)

            # of = open(path, 'xb')
            # of.write(content.read())
            # of.close()

            file = default_storage.open(path, 'wb')
            file.write(content.read())
            file.close()

            # r = requests.get(url)
            # content = BytesIO(r.content)
            ff = default_storage.open(path, 'rb')
            img = Img.open(ff)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            size = img.size
            bottom = math.floor(size[1]*.8)
            img = img.crop((0,0,size[0],bottom))

            buffer = BytesIO()
            img.save(buffer, format='JPEG')
            buffer.seek(0)
            #print(len(buffer))
            #buffer.tell()

            cropped_file = default_storage.open(final_path, 'wb')
            cropped_file.write(buffer.read())
            cropped_file.close()
            #file.close()

            # new_image_io.tell()
            # ff = open(final_path, 'xb')
            # ff.write(new_image_io.read())
            # ff.close()

    def map_doctor_specialization(self, doctor, practice_specialization):
        if practice_specialization and doctor:
            DoctorPracticeSpecialization.objects.get_or_create(doctor=doctor, specialization=practice_specialization)

    def add_doctor_phone_numbers(self, doctor, numbers):
        for num in numbers:
            #print(num)
            DoctorMobile.objects.get_or_create(doctor=doctor, std_code=num.get('std_code'),number=num.get('number'), is_primary=num.get('is_primary'))

    def clean_data(self, value):
        if value and isinstance(value, str):
            return value.strip()
        return value


class UploadQualification(Doc):

    def upload(self, sheet):
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            data = self.get_data(i, sheet, headers)
            #doctor = self.get_doctor(i, sheet, headers)
            # qualification = self.get_qualification(i, sheet, headers)
            # specialization = self.get_specialization(i, sheet, headers)
            # college = self.get_college(i, sheet, headers)
            # passing_year = self.clean_data(sheet.cell(row=i, column=headers.get('passing_year')).value)
            DoctorQualification.objects.get_or_create(doctor=data.get('doctor'),
                                                      qualification=data.get('qualification'),
                                                      college=data.get('college'),
                                                      specialization=data.get('specialization'),
                                                      passing_year=data.get('passing_year'))


    def get_data(self, row, sheet, headers):
        identifier = self.clean_data(sheet.cell(row=row, column=headers.get('identifier')).value)
        doctor = self.get_doctor(identifier)

        qualification_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('qualification_id')).value)
        qualification_name = self.clean_data(sheet.cell(row=row, column=headers.get('qualification')).value)
        qualification = self.get_qualification(qualification_id, qualification_name)

        specialization_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('specialization_id')).value)
        specialization_name = self.clean_data(sheet.cell(row=row, column=headers.get('specialization')).value)
        specialization = self.get_specialization(specialization_id, specialization_name)

        college_id = self.clean_data(
            sheet.cell(row=row, column=headers.get('college_id')).value)
        college_name = self.clean_data(sheet.cell(row=row, column=headers.get('college')).value)
        college = self.get_college(college_id, college_name)

        passing_year = self.clean_data(sheet.cell(row=row, column=headers.get('passing_year')).value)

        data = {}
        data['doctor'] = doctor
        data['qualification'] = qualification
        data['specialization'] = specialization
        data['college'] = college
        data['passing_year'] = passing_year

        return data;


    def get_qualification(self, qualification_id, qualification_name):

        qualification = None
        if qualification_id:
            qualification = Qualification.objects.filter(pk=qualification_id).first()
        if not qualification:
            qualification = Qualification.objects.filter(name__iexact=qualification_name).first()
        if not qualification:
            qualification, create = Qualification.objects.get_or_create(name=qualification_name)

        return qualification


    def get_specialization(self, specialization_id, specialization_name):

        specialization = None
        if specialization_id:
            specialization = Specialization.objects.filter(pk=specialization_id).first()
        if not specialization:
            specialization = Specialization.objects.filter(name__iexact=specialization_name).first()
        if not specialization:
            specialization, create = Specialization.objects.get_or_create(name=specialization_name)

        return specialization

    def get_college(self, college_id, college_name):

        college = None
        if college_id:
            college = College.objects.filter(pk=college_id).first()
        if not college:
            college = College.objects.filter(name__iexact=college_name).first()
        if not college:
            college, create = College.objects.get_or_create(name=college_name)
        return college

class UploadExperience(Doc):

    def upload(self, sheet):
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            identifier = self.clean_data(sheet.cell(row=i, column=headers.get('identifier')).value)
            doctor = self.get_doctor(identifier)
            hospital = self.clean_data(sheet.cell(row=i, column=headers.get('hospital')).value)
            if hospital:
                start_year = self.clean_data(sheet.cell(row=i, column=headers.get('start_year')).value)
                end_year = self.clean_data(sheet.cell(row=i, column=headers.get('end_year')).value)
                DoctorExperience.objects.get_or_create(doctor=doctor, start_year=start_year, end_year=end_year,
                                                   hospital=hospital)


class UploadMembership(Doc):

    def upload(self, sheet):
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            identifier = self.clean_data(sheet.cell(row=i, column=headers.get('identifier')).value)
            doctor = self.get_doctor(identifier)
            member = self.clean_data(sheet.cell(row=i, column=headers.get('memberships')).value)

            if doctor and member:
                DoctorAssociation.objects.get_or_create(doctor=doctor, name=member)

class UploadAward(Doc):

    def upload(self, sheet):
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        for i in range(2, len(rows) + 1):
            identifier = self.clean_data(sheet.cell(row=i, column=headers.get('identifier')).value)
            doctor = self.get_doctor(identifier)
            award = self.clean_data(sheet.cell(row=i, column=headers.get('award')).value)
            year = self.clean_data(sheet.cell(row=i, column=headers.get('year')).value)
            if award and year:
                DoctorAward.objects.get_or_create(doctor=doctor, name=award, year=year)


class UploadHospital(Doc):

    def upload(self, sheet, source, batch):
        rows = [row for row in sheet.rows]
        headers = {column.value.strip().lower(): i + 1 for i, column in enumerate(rows[0]) if column.value}
        reverse_day_map = {value[1]: value[0] for value in DoctorClinicTiming.SHORT_DAY_CHOICES}

        doctor_obj_dict = dict()
        hospital_obj_dict = dict()
        doc_clinic_obj_dict = dict()
        for i in range(2, len(rows) + 1):
            identifier = self.clean_data(sheet.cell(row=i, column=headers.get('identifier')).value)
            doctor_obj = self.get_doctor(identifier)
            if not doctor_obj:
                print('Doctor not found for identifier: '+identifier)
                continue

            hospital_obj = self.get_hospital(i, sheet, headers, hospital_obj_dict, source, batch)
            doc_clinic_obj = self.get_doc_clinic(doctor_obj, hospital_obj, doc_clinic_obj_dict)
            day_list = self.parse_day_range(sheet.cell(row=i, column=headers.get('day_range')).value, reverse_day_map)
            start, end = self.parse_timing(sheet.cell(row=i, column=headers.get('timing')).value)
            clinic_time_data = list()
            fees = self.clean_data(sheet.cell(row=i, column=headers.get('fee')).value)
            try:
                fees = int(fees)
            except Exception as e:
                print('invalid fees' + str(fees))
                fees = None

            for day in day_list:
                if fees:
                    temp_data = {
                        "doctor_clinic": doc_clinic_obj,
                        "day": day,
                        "start": start,
                        "end": end,
                        "fees": fees
                    }
                    clinic_time_data.append(DoctorClinicTiming(**temp_data))
            if clinic_time_data:
                DoctorClinicTiming.objects.bulk_create(clinic_time_data)


    def get_hospital(self, row, sheet, headers, hospital_obj_dict):
        hospital_identifier = self.clean_data(sheet.cell(row=row, column=headers.get('hospital_url')).value)
        hospital_id = self.clean_data(sheet.cell(row=row, column=headers.get('hospital_id')).value)

        hospital = None
        if hospital_id:
            hospital = Hospital.objects.filter(pk=hospital_id).first()
        if not hospital:
            si_obj = SourceIdentifier.objects.filter(type=SourceIdentifier.HOSPITAL,
                                                     unique_identifier=hospital_identifier).first()
            if si_obj:
                hospital = Hospital.objects.filter(pk=si_obj.reference_id).first()

        if not hospital:
            hospital_name = self.clean_data(sheet.cell(row=row, column=headers.get('hospital_name')).value)
            address = self.clean_data(sheet.cell(row=row, column=headers.get('address')).value)
            location = self.parse_gaddress(self.clean_data(sheet.cell(row=row, column=headers.get('gaddress')).value))
            hospital = Hospital.objects.create(name=hospital_name, building=address, location=location, source=source, batch=batch)
            SourceIdentifier.objects.create(reference_id=hospital.id, unique_identifier=hospital_identifier,
                                                type=SourceIdentifier.HOSPITAL)

        return hospital

    def get_doc_clinic(self, doctor_obj, hospital_obj, doc_clinic_obj_dict):
        # print(doctor_obj, hospital_obj, "hello")
        # if doc_clinic_obj_dict.get((doctor_obj, hospital_obj)):
        #     doc_clinic_obj = doc_clinic_obj_dict.get((doctor_obj, hospital_obj))
        # else:
        doc_clinic_obj, is_field_created = DoctorClinic.objects.get_or_create(doctor=doctor_obj, hospital=hospital_obj)
        # doc_clinic_obj_dict[(doctor_obj, hospital_obj)] = doc_clinic_obj

        return doc_clinic_obj

    def parse_gaddress(self, address):
        pnt = None

        if address:
            address = address.strip().split("/")
            lat_long = address[-1]
            lat_long_list = lat_long.strip().split(",")
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
                day = rng_str[0].strip()
                if reverse_day_map.get(day) is None:
                    print('invalid day ' + str(day))
                else:
                    days_list.append(reverse_day_map[day])
            elif len(rng_str) == 2:
                s = rng_str[0].strip()
                e = rng_str[1].strip()
                if reverse_day_map.get(s) is None or reverse_day_map.get(e) is None:
                    print('invalid day range ' + str(day_range))
                else:
                    start = reverse_day_map[s]
                    end = reverse_day_map[e]
                    counter = start

                    while True:
                        val = counter % 7
                        days_list.append(val)
                        if val == end:
                            break
                        counter += 1

            else:
                print('invalid day string ' + day_range)
        return days_list

    def parse_timing(self, timing):
        tlist = timing.strip().split("-")
        start = None
        end = None
        if len(tlist) == 2:
            start = self.time_to_float(tlist[0])
            end = self.time_to_float(tlist[1])
        if start >= end:
            print('Invalid time string ' + timing)

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

    # def get_doctor(self, doctor_identifier):
    #     si_obj = SourceIdentifier.objects.filter(type=SourceIdentifier.DOCTOR, unique_identifier=doctor_identifier).first()
    #     doctor_obj = None
    #     if si_obj:
    #         doctor_obj = Doctor.objects.get(pk=si_obj.reference_id)
    #     return doctor_obj

    # def get_doctor(self, row, sheet, headers, doctor_obj_dict):
    #     doctor_identifier = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_identifier')).value)
    #     if doctor_obj_dict.get(doctor_identifier):
    #         doctor_obj = doctor_obj_dict.get(doctor_identifier)
    #     else:
    #         # doctor_id = self.clean_data(sheet.cell(row=row, column=headers.get('doctor_id')).value)
    #         si_obj = SourceIdentifier.objects.filter(type=SourceIdentifier.DOCTOR, unique_identifier=doctor_identifier).first()
    #         doctor_obj = None
    #         if si_obj:
    #             doctor_obj = Doctor.objects.get(pk=si_obj.reference_id)
    #         doctor_obj_dict[doctor_identifier] = doctor_obj
    #     return doctor_obj

    # def clean_data(self, value):
    #     if value and isinstance(value, str):
    #         return value.strip()
    #     return value
