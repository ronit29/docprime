from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from django.conf import settings
from rest_framework import status
import json
import requests
from ondoc.common.models import Cities
from ondoc.location.models import EntityUrls
from ondoc.doctor.models import SourceIdentifier

def push_doctors():
    doctors = Doctor.objects.filter(source='pr', matrix_lead_id__isnull=True)
    url = settings.MATRIX_API_URL
    matrix_api_token = settings.MATRIX_API_TOKEN

    for doctor in doctors:
        doctor_hospitals = doctor.hospitals.all()
        hospital_list = list(filter(lambda hospital: Cities.objects.filter(name__iexact=hospital.city.lower()).exists(),
                                    doctor_hospitals))

        doctor_mobiles_list = doctor.mobiles.all()
        doctor_mobiles = list(filter(lambda mobile: mobile.is_primary, doctor_mobiles_list))

        mobile = None
        if len(doctor_mobiles) > 0:
            mobile = doctor_mobiles[0].number
        elif len(doctor_mobiles_list) > 0:
            mobile = doctor_mobiles_list[0].number
            if doctor_mobiles_list[0].std_code:
                mobile = str(doctor_mobiles_list[0].std_code)+str(mobile)

            #mobile = "%s-%s" % (doctor_mobiles_list[0].std_code, doctor_mobiles_list[0].number)


        si = SourceIdentifier.objects.filter(reference_id = doctor.id, type=1).first()
        unique_id = None
        if si:
            unique_id = si.unique_identifier


        if len(hospital_list) > 0 and mobile:
            request_data = {
                "ExitPointUrl": '%s/admin/doctor/doctor/%s/change' % (settings.ADMIN_BASE_URL, doctor.id),
                "PrimaryNo": mobile,
                "DocPrimeUniqueId": unique_id,
                "ProductId": 1,
                "Name": doctor.name,
                "DocPrimeUserId ": 0,
                "EmployeeId": "",
                "CityId": Cities.objects.filter(name__iexact=hospital_list[0].city.lower()).first().id,
                "Gender": 1 if doctor.gender == 'm' else 2 if doctor.gender == 'f' else 0,
                "LeadID": 0
            }

            try:
                response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                                      'Content-Type': 'application/json'})

                if response.status_code != status.HTTP_200_OK or not response.ok:
                    print('Could not push doctor with id ', doctor.id)

                resp_data = response.json()

                # save the appointment with the matrix lead id.
                doctor.matrix_lead_id = resp_data.get('Id', None)
                doctor.matrix_lead_id = int(doctor.matrix_lead_id)

                doctor.save()
                print('Successfully pushed for doctor', doctor.id)
            except Exception as e:
                print(str(e))

class Command(BaseCommand):
    def handle(self, **options):
        push_doctors()
