from django.db import models
from django.contrib.postgres.fields import JSONField
from django.contrib.gis.geos import Point
from ondoc.doctor.models import Hospital,  Doctor, DoctorHospital


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

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "doctor_lead"

    def convert_lead(self, user):
        doctor_id = self.create_doctor(user)
        for hospital in self.json.get("LinkedClinics").values():
            clinic_url = hospital[2].get("Clinic URL")
            visiting_days = hospital[0]
            fees = hospital[1].get("Fee").split()[-1]
            hospital_lead = HospitalLead.objects.filter(json__URL=clinic_url).first()
            hospital_id = self.create_hospital(hospital_lead)
            self.create_doctor_hospital(doctor_id, hospital_id, visiting_days, fees)
            print(hospital_id)


    def create_doctor(self, user):
        name = self.json.get("Name")
        created_by = user
        gender = ""
        doctor = Doctor.objects.create(name=name,
                                       created_by=created_by,
                                       gender=gender)
        if not doctor:
            return
        return doctor.id

    def create_hospital(self, hospital_lead):
        if not hospital_lead:
            return
        HOSPITAL_TYPE_MAPPING = {hospital_type[1]: hospital_type[0]
                                 for hospital_type in Hospital.HOSPITAL_TYPE_CHOICES}
        hospital_name = hospital_lead.json.get("Name")
        hospital_type = hospital_lead.json.get("ClinicOrHospital")
        hospital_type = HOSPITAL_TYPE_MAPPING.get(hospital_type)
        location = (hospital_lead.json.get("GoogleAddress")
                    .split("/")[-1].split(",") if self.json.get("GoogleAddress").split("/") else None)
        location_point = Point(float(location[1]), float(location[0]), srid=4326) if len(location) == 2 else None
        hospital = Hospital.objects.create(
            name=hospital_name,
            hospital_type=hospital_type,
            location=location_point
        )
        return hospital.id

    def create_doctor_hospital(self, doctor_id, hospital_id, visiting_days, fees):
        print("here")
        pass
