from django.db import models
from ondoc.authentication import models as auth_models
from ondoc.doctor import models as doc_models
from django.contrib.postgres.fields import JSONField, ArrayField
from django.template.loader import render_to_string
from ondoc.api.v1 import utils
from django.utils import timezone
from django.core.validators import FileExtensionValidator
import random, logging, uuid
logger = logging.getLogger(__name__)


class PrescriptionEntity(auth_models.TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospitals = ArrayField(models.IntegerField(), blank=True, null=True)
    name = models.CharField(db_index=True, max_length=64)
    moderated = models.NullBooleanField(blank=True, null=True)

    @classmethod
    def create_or_update(cls, name, hospital_id):
        obj = cls.objects.filter(name__iexact=name).first()
        if obj:
            if hospital_id in obj.hospitals:
                return obj
            obj.hospitals.append(hospital_id)
            obj.save()
        else:
            obj = cls.objects.create(name=name, hospitals=[hospital_id])
        return obj

    class Meta:
        abstract = True


class PrescriptionSymptomsComplaints(PrescriptionEntity):

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_symptoms_complaints'


class PrescriptionDiagnoses(PrescriptionEntity):

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_diagnoses'


class PrescriptionSpecialInstructions(PrescriptionEntity):

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_special_instructions'


class PrescriptionMedicine(PrescriptionEntity):
    DAY = 1
    WEEK = 2
    MONTH = 3
    YEAR = 4
    DURATION_TYPE_CHOICES = [(DAY, "Day"), (WEEK, "Week"), (MONTH, "Month"), (YEAR, "Year")]
    quantity = models.PositiveIntegerField(null=True, blank=True)
    time = models.CharField(max_length=64, null=True)
    duration_type = models.PositiveSmallIntegerField(choices=DURATION_TYPE_CHOICES, null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)
    instruction = models.CharField(max_length=256, null=True, blank=True)
    additional_notes = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_medicine'


class PrescriptionTests(PrescriptionEntity):
    instruction = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_tests'


class PresccriptionPdf(auth_models.TimeStampedModel):
    DOCPRIME_OPD = 1
    DOCPRIME_LAB = 2
    OFFLINE = 3

    APPOINTMENT_TYPE_CHOICES = [(DOCPRIME_OPD, "Docprime_Opd"), (DOCPRIME_LAB, "Docprime_Lab"), (OFFLINE, "OFFline")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symptoms_complaints = JSONField(blank=True, null=True)
    diagnoses = JSONField(blank=True, null=True)
    special_instructions = JSONField(blank=True, null=True)
    medicines = JSONField(blank=True, null=True)
    lab_tests = JSONField(blank=True, null=True)
    followup_instructions_date = models.DateTimeField(null=True)
    followup_instructions_reason = models.CharField(max_length=256, null=True)
    patient_details = JSONField(blank=True, null=True)
    appointment_id = models.CharField(max_length=64)
    appointment_type = models.PositiveSmallIntegerField(choices=APPOINTMENT_TYPE_CHOICES)
    prescription_file = models.FileField(upload_to='prescription/pdf', validators=[FileExtensionValidator(allowed_extensions=['pdf'])], null=True)

    def get_pdf(self, appointment):


        pdf_dict = {'medicines': self.medicines,
                    'special_instructions': self.special_instructions,
                    'pres_id': self.id,
                    'symptoms_complaints': self.symptoms_complaints,
                    'diagnoses': self.diagnoses,
                    'doc_name': appointment.doctor.name,
                    'hosp_name':  appointment.hospital.name,
                    'tests': self.lab_tests,
                    'patient': self.patient_details,
                    'hosp_address': appointment.hospital.get_hos_address(),
                    'doc_qualification': ','.join([str(h.qualification) for h in appointment.doctor.qualifications.all()]),
                    'doc_reg': appointment.doctor.license,
                    'date': self.created_at.strftime('%d %B %Y'),
                    'followup_date': self.followup_instructions_date.strftime('%d %B %Y %H %i'),
                    'followup_reason': self.followup_instructions_reason
                    }
        html_body = render_to_string("e-prescription/med-invoice.html", context=pdf_dict)
        filename = "prescription_{}_{}.pdf".format(str(timezone.now().strftime("%I%M_%d%m%Y")),
                                              random.randint(1111111111, 9999999999))
        file = utils.html_to_pdf(html_body, filename)
        if not file:
            logger.error("Got error while creating pdf for lab invoice.")
            return []
        return file

    def __str__(self):
        return self.appointment_id

    class Meta:
        db_table = 'eprescription_pdf'


