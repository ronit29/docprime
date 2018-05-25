from django.db import models
from django.contrib.postgres.fields import JSONField
from ondoc.doctor.models import Hospital,  Doctor, DoctorHospital


class HospitalLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    hospital = models.OneToOneField(Hospital, on_delete=models.SET_NULL, null=True)
    json = JSONField()

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "hospital_lead"


class DoctorLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    doctor = models.OneToOneField(Doctor, on_delete=models.SET_NULL, null=True)
    json = JSONField()

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "doctor_lead"

    def convert_lead(self):
        pass

    def create_doctor(self, user):

        pass



