from django.core.management.base import BaseCommand
from ondoc.doctor import models as doctor_models
from django.db import transaction
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'migrate doctor hospital data to doctor clinic'

    @transaction.atomic
    def update_doctor_clinic(self, doctor_hospitals):
        for doctor_hospital in doctor_hospitals:
            doctor_models.DoctorClinic.objects.get_or_create(
                doctor=doctor_hospital.doctor,
                hospital=doctor_hospital.hospital
            )

    @transaction.atomic
    def update_doctor_clinic_timing(self, doctor_clinics):
        current_time = timezone.now()
        for doctor_clinic in doctor_clinics:
            query_string = 'insert into doctor_clinic_timing("day","start", "end", "fees", ' \
                           '"deal_price", "mrp", "followup_duration", "followup_charges", "doctor_clinic_id", ' \
                           '"created_at","updated_at") ' \
                           'select "day", "start", "end", "fees", "deal_price", "mrp", ' \
                           '"followup_duration", "followup_charges", %s, "created_at", \'%s\' ' \
                           'from doctor_hospital where doctor_id = %s and hospital_id=%s ' \
                           '' % (doctor_clinic.id, current_time, doctor_clinic.doctor_id, doctor_clinic.hospital_id)
            with connection.cursor() as cursor:
                cursor.execute(query_string)

    def handle(self, *args, **options):
        doctor_hospitals = doctor_models.DoctorHospital.objects.select_related(
            'doctor', 'hospital').distinct('doctor', 'hospital')
        self.update_doctor_clinic(doctor_hospitals)
        doctor_clinics = doctor_models.DoctorClinic.objects.all()
        self.update_doctor_clinic_timing(doctor_clinics)
