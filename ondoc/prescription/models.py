from django.db import models
from ondoc.authentication import models as auth_models
from ondoc.doctor import models as doc_models
from django.contrib.postgres.fields import JSONField
from django.template.loader import render_to_string
from ondoc.api.v1 import utils
from django.utils import timezone
import random, logging
logger = logging.getLogger(__name__)

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
    DAY = 1
    WEEK = 2
    MONTH = 3
    YEAR = 4
    DURATION_TYPE_CHOICES = [(DAY, "Day"), (WEEK, "Week"), (MONTH, "Month"), (YEAR, "Year")]
    appointment = models.ForeignKey(doc_models.Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=64)
    quantity = models.PositiveIntegerField(null=True, blank=True)
    time = models.CharField(max_length=64, null=True)
    duration_type = models.PositiveSmallIntegerField(choices=DURATION_TYPE_CHOICES, null=True, blank=True)
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
    DOCPRIME_OPD = 1
    DOCPRIME_LAB = 2
    OFFLINE = 3

    APPOINTMENT_TYPE_CHOICES = [(DOCPRIME_OPD, "Docprime_Opd"), (DOCPRIME_LAB, "Docprime_Lab"), (OFFLINE, "OFfline")]
    symptoms = JSONField(blank=True, null=True)
    observations = JSONField(blank=True, null=True)
    medicines = JSONField(blank=True, null=True)
    lab_tests = JSONField(blank=True, null=True)
    diagnosis = JSONField(blank=True, null=True)
    followup_instructions_date = models.DateTimeField(null=True)
    followup_instructions_reason = models.CharField(max_length=256, null=True)
    appointment_id = models.CharField(max_length=64)
    appointment_type = models.PositiveSmallIntegerField(choices=APPOINTMENT_TYPE_CHOICES)

    def get_pdf(self):
        html_body = render_to_string("e-prescription/pdf_template.html", context=self)
        filename = "prescription_{}_{}.pdf".format(str(timezone.now().strftime("%I%M_%d%m%Y")),
                                              random.randint(1111111111, 9999999999))
        file = utils.html_to_pdf(html_body, filename)
        if not file:
            logger.error("Got error while creating pdf for lab invoice.")
            return []
        return file

    class Meta:
        db_table = 'prescription_pdf'


