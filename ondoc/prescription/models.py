from django.db import models
from ondoc.authentication.models import User
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from ondoc.authentication import models as auth_models
from ondoc.prescription import models as pres_models
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
    name = models.CharField(db_index=True, max_length=128)
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
    MORNING = 1
    AFTERNOON = 2
    NIGHT = 3
    TIME_CHOICES = [(MORNING, "MORNING"), (AFTERNOON, "AFTERNOON"), (NIGHT, "NIGHT")]

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_medicine'


class PrescriptionTests(PrescriptionEntity):
    # instructions = models.CharField(max_length=256, null=True, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = 'eprescription_tests'


class PresccriptionPdf(auth_models.TimeStampedModel):

    SERIAL_ID_START = 600000

    CREATE = 1
    UPDATE = 2

    DOCPRIME_OPD = 1
    # DOCPRIME_LAB = 2
    OFFLINE = 3

    PRESCRIPTION_STORAGE_FOLDER = 'prescription/pdf'
    APPOINTMENT_TYPE_CHOICES = [(DOCPRIME_OPD, "Docprime_Opd"),
                                # (DOCPRIME_LAB, "Docprime_Lab"),
                                (OFFLINE, "OFFline")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    symptoms_complaints = JSONField(blank=True, null=True)
    diagnoses = JSONField(blank=True, null=True)
    special_instructions = JSONField(blank=True, null=True)
    medicines = JSONField(blank=True, null=True)
    lab_tests = JSONField(blank=True, null=True)
    followup_instructions_date = models.DateTimeField(null=True)
    followup_instructions_reason = models.CharField(max_length=256, null=True)
    patient_details = JSONField(blank=True, null=True)
    opd_appointment = models.ForeignKey(doc_models.OpdAppointment, on_delete=models.CASCADE, related_name="eprescription", null=True, blank=True)
    offline_opd_appointment = models.ForeignKey(doc_models.OfflineOPDAppointments, on_delete=models.CASCADE, related_name="eprescription", null=True, blank=True)
    appointment_type = models.PositiveSmallIntegerField(choices=APPOINTMENT_TYPE_CHOICES)
    prescription_file = models.FileField(upload_to=PRESCRIPTION_STORAGE_FOLDER, validators=[FileExtensionValidator(allowed_extensions=['pdf'])], null=True)
    serial_id = models.CharField(max_length=100)
    is_encrypted = models.BooleanField(default=False)

    def get_medicines(self):
        if not self.medicines:
            return []
        for medicine in self.medicines:

            if medicine.get("custom_time"):
                medicine['pres_time'] = medicine.get("custom_time")
            elif medicine.get("time"):
                time = medicine.get("time")
                pres_time = ''
                pres_time = pres_time + '1' if PrescriptionMedicine.MORNING in time else pres_time + '0'
                pres_time = pres_time + '-1' if PrescriptionMedicine.AFTERNOON in time else pres_time + '-0'
                pres_time = pres_time + '-1' if PrescriptionMedicine.NIGHT in time else pres_time + '-0'
                medicine['pres_time'] = pres_time
            else:
                medicine['pres_time'] = ''

            if "is_before_meal" not in medicine.keys():
                medicine['meal'] = None
            elif medicine.get("is_before_meal"):
                medicine['meal'] = "Before meal"
            else:
                medicine['meal'] = "After meal"

        return self.medicines

    def get_pdf(self, appointment):

        doctor_number = ''
        if appointment.doctor.doctor_number:
            doctor_numbers = appointment.doctor.doctor_number.all()
            hospital = appointment.hospital
            for number in doctor_numbers:
                if number.hospital == hospital:
                    doctor_number = number.phone_number
                    break

        pdf_dict = {'medicines': self.get_medicines(),
                    # 'medicines': self.medicines if self.medicines else [],
                    'special_instructions': self.special_instructions if self.special_instructions else [],
                    'pres_id': self.id,
                    'serial_id': self.serial_id,
                    'symptoms_complaints': self.symptoms_complaints if self.symptoms_complaints else [],
                    'diagnoses': self.diagnoses if self.diagnoses else [],
                    'doc_name': appointment.doctor.name if appointment.doctor.name else '',
                    'doctor_number': doctor_number,
                    'hosp_name':  appointment.hospital.name if appointment.hospital.name else '',
                    'tests': self.lab_tests if self.lab_tests else [],
                    'patient': self.patient_details,
                    'is_docprime': True if self.opd_appointment else False,
                    'hosp_address': appointment.hospital.get_hos_address() if appointment.hospital.get_hos_address() else '',
                    'doc_qualification': ','.join([str(h.qualification) for h in appointment.doctor.qualifications.all()]),
                    'doc_reg': appointment.doctor.license,
                    'date': self.created_at.strftime('%d %B %Y'),
                    'followup_date': self.followup_instructions_date.strftime('%d %B %Y %H:%I') if self.followup_instructions_date else '',
                    'followup_reason': self.followup_instructions_reason if self.followup_instructions_reason else '',
                    'updated_at': self.updated_at
                    }
        html_body = render_to_string("e-prescription/med-invoice.html", context=pdf_dict)
        filename = "{}_{}_{}_{}.pdf".format(self.patient_details['name'].split(' ')[0], self.serial_id,
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
            # serial = obj.serial_id[-12:]
            serial = '-'.join(obj.serial_id.split('-')[-3:])
            return serial
        else:
            return str(cls.SERIAL_ID_START) + '-01-01'

    @classmethod
    def compute_serial_id(cls, id, appointment, req_serial_id):
        serial_id = None
        task = None
        prescription_pdf = None
        if not req_serial_id:
            serial_id = cls.get_serial(appointment)
        exists = False
        i = 0
        for pres in appointment.eprescription.all():
            if not pres.is_encrypted:
                i += 1
            if str(pres.id) == id:
                task = cls.UPDATE
                prescription_pdf = pres
                if not req_serial_id:
                    serial_id_elements = pres.serial_id.split('-')
                    serial_id_elements[-1] = str(int(serial_id_elements[-1]) + 1).zfill(2)      # version incremented
                    serial_id = '-'.join(serial_id_elements)
                exists = True
                break
        if not exists:
            if i != 0:
                task = cls.CREATE
                if not req_serial_id:
                    serial_id_elements = serial_id.split('-')
                    serial_id_elements[-2] = str(int(serial_id_elements[-2]) + 1).zfill(2)      # file no incremented
                    serial_id = '-'.join(serial_id_elements)
            else:
                task = cls.CREATE
                if not req_serial_id:
                    serial_id = str(int(serial_id.split('-')[-3]) + 1) + '-01-01'
        return serial_id, task, prescription_pdf

    def decrypt_prescription_history(self, appointment, passphrase):
        pres_histories = self.history.filter(data__is_encrypted=True).order_by('created_at')
        version = None
        latest_decrypted_pres_history = self.history.filter(data__is_encrypted=False).order_by('-updated_at').first()
        for index, pres_history_obj in enumerate(pres_histories):

            utils.patient_details_name_phone_number_decrypt(pres_history_obj.data['patient_details'], passphrase)

            pres_history_obj.data['is_encrypted'] = False
            if index == 0:
                if latest_decrypted_pres_history:
                    serial_id_elements = latest_decrypted_pres_history.data['serial_id'].split('-')
                    serial_id_elements[-1] = str(int(serial_id_elements[-1]) + 1).zfill(2)
                    serial_id = '-'.join(serial_id_elements)
                else:
                    serial_id, task, pres_pdf = pres_models.PresccriptionPdf.compute_serial_id(self.id, appointment, None)
            else:
                serial_id_elements = serial_id.split('-')
                serial_id_elements[-1] = str(int(serial_id_elements[-1]) + 1)
                serial_id = '-'.join(serial_id_elements).zfill(2)
            pres_history_obj.data['serial_id'] = str(appointment.hospital.id) + '-' + str(appointment.doctor.id) + '-' + serial_id
            version = pres_history_obj.data['serial_id'].split('-')[-1]
            pres_history_obj.save()

        return version

    def __str__(self):
        return self.id

    class Meta:
        db_table = 'eprescription_pdf'


class PrescriptionHistory(auth_models.TimeStampedModel):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(PresccriptionPdf, on_delete=models.SET_NULL, related_name="history", null=True)
    data = JSONField()

    def __str__(self):
        return str(self.id) + '-' + str(self.prescription.id)

    class Meta:
        db_table = 'eprescription_history'


class OfflinePrescription(auth_models.TimeStampedModel, auth_models.Document):
    appointment = models.ForeignKey(doc_models.OfflineOPDAppointments, related_name='offline_prescription', on_delete=models.CASCADE)
    name = models.FileField(upload_to='prescriptions', blank=False, null=False)
    prescription_details = models.TextField(max_length=300, blank=True, null=True)

    def __str__(self):
        return self.id

    class Meta:
        db_table = 'offline_prescription'


class AppointmentPrescription(auth_models.TimeStampedModel):

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey()
    user = models.ForeignKey(User, null=True, default=None, on_delete=models.CASCADE)
    prescription_file = models.FileField(null=False, upload_to='user_prescriptions', validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])])

    @classmethod
    def prescription_exist_for_date(cls, user, date):
        return cls.objects.filter(created_at__date=date, user=user, object_id__isnull=False).exists()

    @classmethod
    def update_with_appointment(cls, app_obj, ids):
        content_type = ContentType.objects.get_for_model(app_obj)
        cls.objects.filter(id__in=ids).update(content_type_id=content_type.id, object_id=app_obj.id)

    class Meta:
        db_table = 'appointment_prescription'
