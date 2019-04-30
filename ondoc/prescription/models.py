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
    INHOUSE_CHAT = 1
    MESH = 2
    PARTNERS_APP = 3
    SOURCE_TYPE_CHOICES = (("", "Select"), (INHOUSE_CHAT, 'Inhouse Chat'), (MESH, 'Mesh'), (PARTNERS_APP, 'Partners App'))
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospitals = ArrayField(models.IntegerField(), blank=True, null=True)
    name = models.CharField(db_index=True, max_length=64)
    moderated = models.NullBooleanField(blank=True, null=True)
    source_type = models.IntegerField(choices=SOURCE_TYPE_CHOICES, null=True, blank=True, default=None, editable=False)

    @classmethod
    def create_or_update(cls, name, hospital_id, source_type, **kwargs):
        obj = cls.objects.filter(name__iexact=name).first()
        if obj:
            if hospital_id in obj.hospitals:
                return obj
            obj.hospitals.append(hospital_id)
            obj.save()
        else:
            obj = cls.objects.create(name=name, hospitals=[hospital_id], source_type=source_type)
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
    TABLET = 1
    SYRUP = 2
    CAPSULE = 3
    CREAM = 4
    DROP = 5
    FOAM = 6
    GEL = 7
    INHALER = 8
    INJECTION = 9
    LOTION = 10
    OINTMENT = 11
    POWDER = 12
    SPRAY = 13
    SYRINGE = 14
    SUSPENSION = 15
    SOLUTION = 16
    DOSAGE_TYPE_CHOICES = [(TABLET, "Tablet"), (SYRUP, "Syrup"), (CAPSULE, "CAPSULE"), (CREAM, "Cream"),
                           (DROP, "Drop"), (FOAM, "Foam"), (GEL, "Gel"), (INHALER, "Inhaler"),
                           (INJECTION, "Injection"), (LOTION, "Lotion"), (OINTMENT, "Ointment"), (POWDER, "Powder"),
                           (SPRAY, "Spray"), (SYRINGE, "Syringe"), (SUSPENSION, "Suspension"), (SOLUTION, "Solution")]
    quantity = models.PositiveIntegerField(null=True, blank=True)
    dosage_type = models.PositiveIntegerField(choices=DOSAGE_TYPE_CHOICES, null=True, blank=True)
    # time = models.CharField(max_length=64, null=True)
    time = ArrayField(models.CharField(max_length=64), blank=True, null=True)
    duration_type = models.PositiveSmallIntegerField(choices=DURATION_TYPE_CHOICES, null=True, blank=True)
    duration = models.PositiveIntegerField(null=True, blank=True)
    # instruction = models.CharField(max_length=256, null=True, blank=True)
    is_before_meal = models.NullBooleanField(default=None, blank=True)
    additional_notes = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return self.name

    @classmethod
    def create_or_update(cls, **kwargs):
        name = kwargs.pop("name")
        hospital_id = kwargs.pop("hospital_id")
        source_type = kwargs.pop("source_type")
        time = kwargs.get("time")
        obj = super(PrescriptionMedicine, cls).create_or_update(name=name,
                                                                hospital_id=hospital_id,
                                                                source_type=source_type)
        # obj = cls.objects.filter(name__iexact=name).first()
        if obj and kwargs:
            obj.quantity = kwargs.get("quantity")
            obj.type = kwargs.get("type")
            obj.duration_type = kwargs.get('duration_type')
            obj.duration = kwargs.get("duration")
            obj.is_before_meal = kwargs.get("is_before_meal")
            obj.additional_notes = kwargs.get("additional_notes")
            obj.dosage_type = kwargs.get('dosage_type')

            obj_times = obj.time if obj.time else []
            if time:
                if set(time) < set(obj_times):
                    obj.save()
                    return obj
                else:
                    time_to_be_appended = set(time) - (set(time) & set(obj_times))
                    if not obj.time:
                        obj.time = list()
                    obj.time.extend(time_to_be_appended)
            obj.save()
        return obj

    class Meta:
        db_table = 'eprescription_medicine'


class PrescriptionTests(PrescriptionEntity):
    instruction = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_tests'


class PresccriptionPdf(auth_models.TimeStampedModel):

    SERIAL_ID_START = 600000

    CREATE = 1
    UPDATE = 2

    DOCPRIME_OPD = 1
    DOCPRIME_LAB = 2
    OFFLINE = 3

    PRESCRIPTION_STORAGE_FOLDER = 'prescription/pdf'
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
    prescription_file = models.FileField(upload_to=PRESCRIPTION_STORAGE_FOLDER, validators=[FileExtensionValidator(allowed_extensions=['pdf'])], null=True)
    serial_id = models.CharField(max_length=100)

    def get_pdf(self, appointment):


        pdf_dict = {'medicines': self.medicines if self.medicines else [],
                    'special_instructions': self.special_instructions if self.special_instructions else [],
                    'pres_id': self.id,
                    'symptoms_complaints': self.symptoms_complaints if self.symptoms_complaints else [],
                    'diagnoses': self.diagnoses if self.diagnoses else [],
                    'doc_name': appointment.doctor.name,
                    'hosp_name':  appointment.hospital.name,
                    'tests': self.lab_tests if self.lab_tests else [],
                    'patient': self.patient_details,
                    'hosp_address': appointment.hospital.get_hos_address(),
                    'doc_qualification': ','.join([str(h.qualification) for h in appointment.doctor.qualifications.all()]),
                    'doc_reg': appointment.doctor.license,
                    'date': self.created_at.strftime('%d %B %Y'),
                    'followup_date': self.followup_instructions_date.strftime('%d %B %Y %H %i') if self.followup_instructions_date else '',
                    'followup_reason': self.followup_instructions_reason if self.followup_instructions_reason else '',
                    'updated_at': self.updated_at
                    }
        html_body = render_to_string("e-prescription/med-invoice.html", context=pdf_dict)
        filename = "{}_{}_{}_{}.pdf".format(self.patient_details['name'].partition(' ')[0], self.serial_id,
                                            str(timezone.now().strftime("%H%M%S")), random.randint(11111, 99999))
        file = utils.html_to_pdf(html_body, filename)
        if not file:
            logger.error("Got error while creating pdf for lab invoice.")
            return []
        return file

    @classmethod
    def get_serial(cls, appointment):
        doctor_id = appointment.doctor.id
        hospital_id = appointment.hospital.id
        obj = cls.objects.filter(serial_id__contains=str(hospital_id)+'-'+str(doctor_id)).order_by('-serial_id').first()
        if obj:
            serial = obj.serial_id[-12:]
            return serial
        else:
            return str(cls.SERIAL_ID_START) + '-01-01'

    def __str__(self):
        return self.appointment_id

    class Meta:
        db_table = 'eprescription_pdf'


class PrescriptionHistory(auth_models.TimeStampedModel):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(PresccriptionPdf, on_delete=models.SET_NULL, related_name="history", null=True)
    data = JSONField()

    def __str__(self):
        return self.id

    class Meta:
        db_table = 'eprescription_history'
