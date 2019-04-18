from django.db import models
from ondoc.authentication import models as auth_models
from ondoc.doctor import models as doc_models
from django.contrib.postgres.fields import JSONField
# Create your models here.


class PrescriptionSymptoms(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    symptoms = models.CharField(max_length=64)
    moderated = models.NullBooleanField(blank=True, null=True)

    class Meta:
        db_table = 'prescription_symptoms'


class PrescriptionObservations(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    observation = models.CharField(max_length=64)
    moderated = models.NullBooleanField(blank=True, null=True)

    class Meta:
        db_table = 'prescription_observations'


class PrescriptionMedicine(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    time = models.CharField(max_length=64)
    duration_type = models.PositiveSmallIntegerField(null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)
    instruction = models.CharField(max_length=256, null=True, blank=True)
    additional_notes = models.CharField(max_length=256, null=True, blank=True)
    moderated = models.NullBooleanField(blank=True, null=True)

    class Meta:
        db_table = 'prescription_medicine'


class PrescriptionTests(auth_models.TimeStampedModel):
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    test = models.CharField(max_length=64)
    instruction = models.CharField(max_length=256, null=True, blank=True)
    moderated = models.NullBooleanField(blank=True, null=True)

    class Meta:
        db_table = 'prescription_tests'


class PresccriptionPdf(auth_models.TimeStampedModel):
    symptoms = JSONField(blank=True, null=True)
    observations = JSONField(blank=True, null=True)
    medicines = JSONField(blank=True, null=True)
    lab_tests = JSONField(blank=True, null=True)
    diagnosis = JSONField(blank=True, null=True)
    followup_instructions_date = models.DateTimeField()
    followup_instructions_reason = models.CharField(max_length=256)
    appointment = models.ForeignKey(doc_models.OpdAppointment, on_delete=models.CASCADE)

    class Meta:
        db_table = 'prescription_pdf'


