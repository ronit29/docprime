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
            doctor_models.DoctorClinic.objects.create(
                doctor=doctor_hospital.doctor,
                hospital=doctor_hospital.hospital
            )

    def handle(self, *args, **options):
        doctor_hospitals = doctor_models.DoctorHospital.objects.distinct('doctor', 'hospital')
        self.update_doctor_clinic(doctor_hospitals)
