from django.db import models, transaction
from django.contrib.postgres.fields import JSONField
from django.contrib.gis.geos import Point
from django.utils.safestring import mark_safe

from ondoc.doctor.models import (Hospital, Doctor, DoctorClinic,
                                 DoctorAward, DoctorQualification, DoctorExperience, DoctorMedicalService,
                                 MedicalService, Qualification, College)
from ondoc.authentication.models import TimeStampedModel
from ondoc.notification.models import EmailNotification
import logging

logger = logging.getLogger(__name__)


class HospitalLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    hospital = models.OneToOneField(Hospital, on_delete=models.SET_NULL, null=True, blank=True)
    json = JSONField()

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "hospital_lead"


class DoctorLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    doctor = models.OneToOneField(Doctor, on_delete=models.SET_NULL, null=True, blank=True)
    json = JSONField()
    hospital_leads = models.ManyToManyField(
        HospitalLead,
        through='DoctorHospitalLead',
        through_fields=('doctor_lead', 'hospital_lead'),
    )

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "doctor_lead"

    def convert_lead(self, user):
        doctor = self.create_doctor(user)
        self.create_services(doctor)
        self.create_experiences(doctor)
        self.create_qualifications(doctor)
        self.doctor = doctor
        for hospital in self.json.get("LinkedClinics").values():
            clinic_url = hospital[2].get("Clinic URL")
            visiting_days = hospital[0].get("Visiting Days")
            fees = hospital[1].get("Fee").split()[-1]
            hospital_lead = self.hospital_leads.filter(json__URL=clinic_url).first()
            if not hospital_lead:
                continue
            hospital = self.create_hospital(hospital_lead, user)
            hospital_lead.hospital = hospital
            self.create_doctor_hospital(doctor, hospital, visiting_days, fees)
            hospital_lead.save()
        self.save()

    def create_doctor(self, user):
        name = self.json.get("Name")
        created_by = user
        gender = ""
        doctor = Doctor.objects.create(name=name,
                                       created_by=created_by,
                                       gender=gender)
        if not doctor:
            return
        return doctor

    def create_hospital(self, hospital_lead, created_by):
        if not hospital_lead:
            return
        HOSPITAL_TYPE_MAPPING = {hospital_type[1]: hospital_type[0]
                                 for hospital_type in Hospital.HOSPITAL_TYPE_CHOICES}
        hospital_name = hospital_lead.json.get("Name")
        hospital_type = hospital_lead.json.get("ClinicOrHospital")
        city = hospital_lead.json.get("Address").split(",")[-1]
        hospital_type = HOSPITAL_TYPE_MAPPING.get(hospital_type)
        location = (hospital_lead.json.get("GoogleAddress")
                    .split("/")[-1].split(",") if self.json.get("GoogleAddress").split("/") else None)
        location_point = Point(float(location[1]), float(location[0]), srid=4326) if len(location) == 2 else None
        hospital = Hospital.objects.create(
            name=hospital_name,
            hospital_type=hospital_type,
            location=location_point,
            created_by=created_by,
            city=city
        )
        return hospital

    def create_doctor_hospital(self, doctor, hospital, visiting_days, fees):
        DAYS_MAPPING = {
            "Mon": 0,
            "Tue": 1,
            "Wed": 2,
            "Thu": 3,
            "Fri": 4,
            "Sat": 5,
            "Sun": 6,
        }
        TIME_SLOT_MAPPING = {time_slot_choice[1]: time_slot_choice[0] for time_slot_choice in
                             DoctorClinic.TIME_CHOICES}

        doctor_hospital_values = []
        for key, value in visiting_days.items():
            for day_range_str in key.split(","):
                day_range = range(DAYS_MAPPING.get(day_range_str.strip().split("-")[0].strip()),
                                  DAYS_MAPPING.get(day_range_str.strip().split("-")[-1].strip()) + 1)
                for day in day_range:
                    for timing in value:
                        start_time = timing.split("-")[0].strip()
                        end_time = timing.split("-")[-1].strip()
                        start_time_db_value = (
                            TIME_SLOT_MAPPING.get(start_time)
                        )
                        end_time_db_value = (
                            TIME_SLOT_MAPPING.get(end_time)
                        )
                        if (not start_time_db_value) or (not end_time_db_value):
                            continue
                        doctor_hospital_values.append(
                            DoctorClinic(
                                doctor=doctor,
                                hospital=hospital,
                                day=day,
                                start=start_time_db_value,
                                end=end_time_db_value,
                                fees=fees
                            )
                        )

        if doctor_hospital_values:
            DoctorClinic.objects.bulk_create(doctor_hospital_values)

    def create_services(self, doctor):
        doctor_services = []
        for service in self.json.get("Services").values():
            medical_service = MedicalService.objects.filter(name=service).first()
            if medical_service:
                doctor_services.append(DoctorMedicalService(
                    doctor=doctor,
                    service=medical_service
                ))
        if doctor_services:
            DoctorMedicalService.objects.bulk_create(doctor_services)
            return True
        return False

    def create_experiences(self, doctor):
        doctor_experiences = []
        for experience in self.json.get("Experience").values():
            start_year = experience.get("Year").split("-")[0].strip()
            end_year = experience.get("Year").split("-")[-1].strip()
            doctor_experiences.append(DoctorExperience(
                doctor=doctor,
                hospital=experience.get("Location") if experience.get("Location") else "NA",
                start_year=start_year,
                end_year=None if end_year == "Present" else end_year
            ))
        if doctor_experiences:
            DoctorExperience.objects.bulk_create(doctor_experiences)
            return True
        return False

    def create_qualifications(self, doctor):
        doctor_qualifications = []
        for qualification in self.json.get("Education").values():
            qualification_name = qualification.get("Qualification", "").strip()
            passing_year = qualification.get("Year", None)
            college = qualification.get("Institute", "").strip()
            qualification_obj = Qualification.objects.filter(name=qualification_name).first()
            college_obj = College.objects.filter(name=college).first()
            if qualification_obj and college_obj:
                doctor_qualifications.append(DoctorQualification(
                    doctor=doctor,
                    qualification=qualification_obj,
                    college=college_obj,
                    passing_year=passing_year
                ))
        if doctor_qualifications:
            DoctorQualification.objects.bulk_create(doctor_qualifications)
            return True
        return False


class DoctorHospitalLead(models.Model):
    doctor_lead = models.ForeignKey(DoctorLead, on_delete=models.SET_NULL, null=True, blank=True)
    hospital_lead = models.ForeignKey(HospitalLead, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "doctor_hospital_lead"

    def __str__(self):
        return "doctor-lead-{} hospital-lead-{}".format(self.doctor_lead.id,
                                                        self.hospital_lead.id)


class SearchLead(TimeStampedModel):

    phone_number = models.CharField(max_length=15)
    location = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return '{0} {1}'.format(self.phone_number, self.location)

    class Meta:
        db_table = "search_lead"


class UserLead(TimeStampedModel):

    gender_choice = [("", "Select"), ("m", "Male"), ("f", "Female"), ("o", "Other")]
    name = models.CharField(max_length=50, blank=True, default="")
    phone_number = models.CharField(max_length=15)
    message = models.TextField(blank=True, default="")
    gender = models.CharField(choices=gender_choice, blank=True, max_length=2, default='')

    def __str__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        super().save(force_insert, force_update, using, update_fields)
        transaction.on_commit(lambda: self.after_commit())

    def after_commit(self):
        from django.forms.models import model_to_dict
        from django.conf import settings
        try:
            email = settings.PROVIDER_EMAIL
            html_body = model_to_dict(self)
            html_body.pop('id', None)
            final_html_body = ''
            for k, v in html_body.items():
                final_html_body += '{} : {}<br>'.format(k, v)
            email_subject = 'Lead from Ads' + str(self.created_at)
            EmailNotification.publish_ops_email(email, mark_safe(final_html_body), email_subject)
        except Exception as e:
            logger.error(str(e))

    class Meta:
        db_table = "user_lead"
