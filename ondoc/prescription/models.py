from django.db import models
from ondoc.authentication import models as auth_models
from ondoc.doctor import models as doc_models
# Create your models here.


class PrescriptionComplaints(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    complaint = models.CharField(max_length=64)

    class Meta:
        db_table = 'prescription_complaints'


class PrescriptionObservations(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    observation = models.CharField(max_length=64)

    class Meta:
        db_table = 'prescription_observations'


class PrescriptionMedicine(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    time = models.CharField(max_length=64)
    duration_type = models.PositiveSmallIntegerField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)
    instruction = models.CharField(null=True, blank=True)
    additional_notes = models.CharField(null=True, blank=True)

    class Meta:
        db_table = 'prescription_medicine'


class PrescriptionTests(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    test = models.CharField(max_length=64)
    instruction = models.CharField(null=True, blank=True)

    class Meta:
        db_table = 'prescription_tests'

class PresccriptionPdf(auth_models.TimeStampedModel):
    pass


