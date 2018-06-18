from django.contrib.gis.db import models
from django.db import migrations
from django.db.models import Count
from django.contrib.postgres.operations import CreateExtension
from django.contrib.postgres.fields import JSONField
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.core.exceptions import NON_FIELD_ERRORS
from django.conf import settings
from datetime import datetime, timedelta
from django.utils import timezone
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, Image, QCModel, UserProfile, User
from ondoc.account.models import ConsumerAccount, ConsumerTransaction, PgTransaction
from ondoc.notification import models as notification_models
import random
from django.db import transaction
import os


class Migration(migrations.Migration):

    operations = [
        CreateExtension('postgis')
    ]

class UniqueNameModel(models.Model):

    def validate_unique(self, *args, **kwargs):
        super().validate_unique(*args, **kwargs)

        if self.__class__.objects.filter(name__iexact=self.name.lower()).exists():
            raise ValidationError(
                {
                    NON_FIELD_ERRORS: [
                        self.__class__.__name__+' with same name already exists',
                    ],
                }
            )

    class Meta:
        abstract = True


class MedicalService(TimeStampedModel,UniqueNameModel):
    name = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "medical_service"


class Hospital(TimeStampedModel, CreatedByModel, QCModel):
    PRIVATE = 1
    CLINIC = 2
    HOSPITAL = 3
    HOSPITAL_TYPE_CHOICES = (("", "Select"), (PRIVATE, 'Private'), (CLINIC, "Clinic"), (HOSPITAL, "Hospital"), )
    name = models.CharField(max_length=200)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True,  validators=[MinValueValidator(1800)])
    parking = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Easy"), (2,"Difficult")])
    registration_number = models.CharField(max_length=500, blank=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    hospital_type = models.PositiveSmallIntegerField(blank = True, null = True, choices=HOSPITAL_TYPE_CHOICES)
    network_type = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Non Network Hospital"), (2,"Network Hospital")])
    network = models.ForeignKey('HospitalNetwork', null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "hospital"


class HospitalAward(TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_award"


class HospitalAccreditation(TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_accreditation"

class HospitalCertification(TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_certification"

class HospitalSpeciality(TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_speciality"


# class ClinicalSpeciality(TimeStampedModel):
#     name = models.CharField(max_length=1000)

#     def __str__(self):
#         return self.name

#     class Meta:
#         db_table = "clinical_speciality"


# class HospitalClinicalSpeciality(TimeStampedModel):
#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
#     speciality = models.ForeignKey(ClinicalSpeciality, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.hospital.name + " (" + self.clinical_speciality.name + ")"

#     class Meta:
#         db_table = "hospital_clinical_speciality"
#         unique_together = (("hospital", "speciality"))


class College(TimeStampedModel):

    name = models.CharField(max_length=200, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "college"


class Doctor(TimeStampedModel, QCModel):
    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"), (ONBOARDED, "Onboarded")]

    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=2, default=None, blank=True, choices=[("","Select"), ("m","Male"), ("f","Female"), ("o","Other")])
    practicing_since = models.PositiveSmallIntegerField(blank=True, null=True,validators=[MinValueValidator(1900)])
    about = models.CharField(max_length=2000, blank=True)
    # primary_mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    license = models.CharField(max_length=200, blank=True)
    onboarding_status = models.PositiveSmallIntegerField(default=NOT_ONBOARDED, choices=ONBOARDING_STATUS)
    additional_details = models.CharField(max_length=2000, blank=True)
    # email = models.EmailField(max_length=100, blank=True)
    is_email_verified = models.BooleanField(verbose_name= 'Email Verified', default=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="doctor", on_delete=models.CASCADE, default=None, blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_doctors", null=True, editable=False, on_delete=models.SET_NULL)

    is_insurance_enabled = models.BooleanField(verbose_name= 'Enabled for Insurance Customer',default=False)
    is_retail_enabled = models.BooleanField(verbose_name= 'Enabled for Retail Customer', default=False)
    is_online_consultation_enabled = models.BooleanField(verbose_name='Available for Online Consultation', default=False)
    online_consultation_fees = models.PositiveSmallIntegerField(blank=True, null=True)
    hospitals = models.ManyToManyField(
        Hospital,
        through='DoctorHospital',
        through_fields=('doctor', 'hospital'),
    )

    def __str__(self):
        return self.name

    def experience_years(self):
        if not self.practicing_since:
            return None
        current_year = timezone.now().year
        return int(current_year - self.practicing_since)

    def experiences(self):
        return self.experiences.all()

    def hospital_count(self):
        return self.availability.all().values("hospital").distinct().count()

    def get_hospitals(self):
        return self.availability.all()

    class Meta:
        db_table = "doctor"


class Specialization(TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=200)
    human_readable_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "specialization"


class Qualification(TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "qualification"


class Symptoms(TimeStampedModel, CreatedByModel, UniqueNameModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "symptoms"


class DoctorQualification(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="qualifications", on_delete=models.CASCADE)
    qualification = models.ForeignKey(Qualification, on_delete=models.CASCADE)
    specialization = models.ForeignKey(Specialization, on_delete=models.CASCADE, blank=True, null=True)
    college = models.ForeignKey(College, on_delete=models.CASCADE, blank=True, null=True);
    passing_year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])

    def __str__(self):
        if self.specialization_id:
            return self.qualification.name + " (" + self.specialization.name + ")"
        return self.qualification.name

    class Meta:
        db_table = "doctor_qualification"
        unique_together = (("doctor", "qualification", "specialization", "college"))


class DoctorHospital(TimeStampedModel):
    DAY_CHOICES = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    doctor = models.ForeignKey(Doctor, related_name="availability", on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=DAY_CHOICES)

    TIME_CHOICES = [(7.0, "7:00 AM"), (7.5, "7:30 AM"),
    (8.0, "8:00 AM"), (8.5, "8:30 AM"),
    (9.0, "9:00 AM"), (9.5, "9:30 AM"),
    (10.0, "10:00 AM"), (10.5, "10:30 AM"),
    (11.0, "11:00 AM"), (11.5, "11:30 AM"),
    (12.0, "12:00 PM"), (12.5, "12:30 PM"),
    (13.0, "1:00 PM"), (13.5, "1:30 PM"),
    (14.0, "2:00 PM"), (14.5, "2:30 PM"),
    (15.0, "3:00 PM"), (15.5, "3:30 PM"),
    (16.0, "4:00 PM"), (16.5, "4:30 PM"),
    (17.0, "5:00 PM"), (17.5, "5:30 PM"),
    (18.0, "6:00 PM"), (18.5, "6:30 PM"),
    (19.0, "7:00 PM"), (19.5, "7:30 PM"),
    (20.0, "8:00 PM"), (20.5, "8:30 PM"),
    (21.0, "9:00 PM"), (21.5, "9:30 PM"),
    (22.0, "10:00 PM"), (22.5, "10:30 PM")]

    start = models.DecimalField(max_digits=3,decimal_places=1, choices = TIME_CHOICES)
    end = models.DecimalField(max_digits=3,decimal_places=1, choices = TIME_CHOICES)
    fees = models.FloatField(blank=False, null=False)
    mrp = models.FloatField(blank=False, null=False, default=0)
    discounted_price = models.FloatField(blank=False, default=0, null=False)

    def __str__(self):
        return self.doctor.name + " " + self.hospital.name + " ," + str(self.start)+ " " + str(self.end) + " " + str(self.day)

    def discounted_fees(self):
        return self.fees

    class Meta:
        db_table = "doctor_hospital"
        unique_together = (("start", "end", "day", "hospital", "doctor"))


class DoctorImage(TimeStampedModel, Image):
    doctor = models.ForeignKey(Doctor, related_name="images", on_delete=models.CASCADE)
    name = models.ImageField(upload_to='doctor/images',height_field='height', width_field='width')

    class Meta:
        db_table = "doctor_image"


class DoctorDocument(TimeStampedModel):
    PAN = 1
    ADDRESS = 2
    GST = 3
    REGISTRATION = 4
    CHEQUE = 5
    AADHAR = 7
    CHOICES = [(PAN,"PAN Card"), (ADDRESS,"Address Proof"), (GST,"GST Certificate"), (REGISTRATION,"MCI Registration Number"),(CHEQUE,"Cancel Cheque Copy"),(AADHAR,"Aadhar Card")]

    doctor = models.ForeignKey(Doctor, related_name="documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='doctor/documents', validators=[FileExtensionValidator(allowed_extensions=['pdf','jfif','jpg','jpeg','png'])])

    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')

    class Meta:
        db_table = "doctor_document"


class HospitalImage(TimeStampedModel, Image):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='hospital/images',height_field='height', width_field='width')

    class Meta:
        db_table = "hospital_image"


class HospitalDocument(TimeStampedModel, Image):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='hospital/documents',height_field='height', width_field='width')
    class Meta:
        db_table = "hospital_document"


class Language(TimeStampedModel, UniqueNameModel):

    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "language"


class DoctorLanguage(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="languages", on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)

    def __str__(self):
        return self.doctor.name + " (" + self.language.name + ")"

    class Meta:
        db_table = "doctor_language"
        unique_together = (("doctor", "language"))


class DoctorAward(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="awards", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_awards"


class DoctorAssociation(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="associations", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_association"


class DoctorExperience(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="experiences", on_delete=models.CASCADE)
    hospital = models.CharField(max_length=200)
    start_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,validators=[MinValueValidator(1950)])
    end_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,validators=[MinValueValidator(1950)])

    class Meta:
        db_table = "doctor_experience"


class DoctorMedicalService(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="medical_services", on_delete=models.CASCADE)
    service = models.ForeignKey(MedicalService, on_delete=models.CASCADE)

    class Meta:
        db_table = "doctor_medical_service"
        unique_together = (("doctor", "service"))


class DoctorMobile(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="mobiles", on_delete=models.CASCADE)
    country_code = models.PositiveSmallIntegerField(default=91, blank=True, null=True)
    number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(7000000000)])
    is_primary = models.BooleanField(verbose_name= 'Primary Number?', default=False)
    is_phone_number_verified = models.BooleanField(verbose_name= 'Phone Number Verified?', default=False)

    class Meta:
        db_table = "doctor_mobile"
        unique_together = (("doctor", "number"))


class DoctorEmail(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="emails", on_delete=models.CASCADE)
    email = models.EmailField(max_length=100, blank=True)
    is_primary = models.BooleanField(verbose_name= 'Primary Email?', default=False)
    is_email_verified = models.BooleanField(verbose_name= 'Phone Number Verified?', default=False)

    class Meta:
        db_table = "doctor_email"
        unique_together = (("doctor", "email"))


class HospitalNetwork(TimeStampedModel, CreatedByModel, QCModel):
    name = models.CharField(max_length=100)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])
    about = models.CharField(max_length=2000, blank=True)
    network_size = models.PositiveSmallIntegerField(blank=True, null=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return self.name + " (" + self.city + ")"

    class Meta:
        db_table = "hospital_network"


class HospitalNetworkCertification(TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_certification"


class HospitalNetworkAward(TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])
    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_award"


class HospitalNetworkAccreditation(TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_accreditation"


class HospitalNetworkManager(TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager")])

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_manager"


class HospitalNetworkHelpline(TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    number = models.BigIntegerField()
    details = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_helpline"


class HospitalNetworkEmail(TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_email"


class DoctorOnboardingToken(TimeStampedModel):
    GENERATED = 1
    REJECTED = 2
    CONSUMED = 3
    STATUS_CHOICES = [(GENERATED, "Generated"), (REJECTED, "Rejected"), (CONSUMED, "Consumed")]
    doctor = models.ForeignKey(Doctor, null=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    verified_token = models.CharField(max_length=100, null=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=GENERATED)

    def __str__(self):
        return self.doctor.name+" "+self.email+" "+str(self.mobile)

    class Meta:
        db_table = "doctor_onboarding_token"


# class HospitalNetworkMapping(TimeStampedModel):
#     network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.network.name + " (" + self.hospital.name + ")"

#     class Meta:
#         db_table = "hospital_network_mapping"


class OpdAppointment(TimeStampedModel):
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_DOCTOR = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELED = 6
    COMPLETED = 7

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, "Payment Accepted"),
        (PAYMENT_PENDING, "Payment Pending"),
    )

    # PATIENT_SHOW = 1
    # PATIENT_DIDNT_SHOW = 2
    # PATIENT_STATUS_CHOICES = [PATIENT_SHOW, PATIENT_DIDNT_SHOW]
    doctor = models.ForeignKey(Doctor, related_name="appointments", on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, related_name="hospital_appointments", on_delete=models.CASCADE)
    profile = models.ForeignKey(UserProfile, related_name="appointments", on_delete=models.CASCADE)
    profile_detail = JSONField(blank=True, null=True)
    user = models.ForeignKey(User, related_name="appointments", on_delete=models.CASCADE)
    booked_by = models.ForeignKey(User, related_name="booked_appointements", on_delete=models.CASCADE)
    fees = models.FloatField()
    effective_price = models.FloatField(blank=False, null=False, default=0)
    mrp = models.FloatField(blank=False, null=False, default=0)
    discounted_price = models.FloatField(blank=False, default=0, null=False)
    status = models.PositiveSmallIntegerField(default=CREATED)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    otp = models.PositiveIntegerField(blank=True, null=True)
    #patient_status = models.PositiveSmallIntegerField(blank=True, null=True)
    time_slot_start = models.DateTimeField(blank=True, null=True)
    time_slot_end = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.profile.name + " (" + self.doctor.name + ")"

    def allowed_action(self, user_type):
        from ondoc.authentication.models import UserPermission
        allowed = []
        current_datetime = timezone.now()

        if user_type == User.DOCTOR and self.time_slot_start>current_datetime:
            perm_queryset =  UserPermission.objects.filter(doctor=self.doctor.id).filter(hospital=self.hospital_id).first()
            if perm_queryset:
                if not perm_queryset.read_permission:
                    if self.status == self.BOOKED:
                        allowed = [self.ACCEPTED, self.RESCHEDULED_DOCTOR]
                    elif self.status == self.ACCEPTED:
                        allowed = [self.RESCHEDULED_DOCTOR, self.COMPLETED]
                    elif self.status == self.RESCHEDULED_DOCTOR:
                        allowed = [self.ACCEPTED]

        elif user_type == User.CONSUMER and current_datetime<self.time_slot_start+timedelta(hours=6):
            if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_DOCTOR, self.RESCHEDULED_PATIENT):
                allowed = [self.RESCHEDULED_PATIENT, self.CANCELED]

        return allowed

    @transaction.atomic
    def action_rescheduled_doctor(self, appointment):
        appointment.status = self.RESCHEDULED_DOCTOR
        appointment.save()
        return appointment

    def action_rescheduled_patient(self, appointment, data):
        from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
        appointment.status = self.RESCHEDULED_PATIENT
        appointment.time_slot_start = data.get('time_slot_start')
        appointment.fees = data.get('fees', appointment.fees)
        appointment.mrp = data.get('mrp', appointment.mrp)
        appointment.discounted_price = data.get('discounted_price', appointment.discounted_price)
        appointment.effective_price = data.get('effective_price', appointment.effective_price)
        appointment.save()

        return appointment

    def action_accepted(self, appointment):
        appointment.status = self.ACCEPTED
        appointment.save()
        return appointment

    @transaction.atomic
    def action_cancelled(self, appointment):
        appointment.status = self.CANCELED
        appointment.save()

        consumer_account = ConsumerAccount.objects.get_or_create(user=self.user)
        consumer_account = ConsumerAccount.objects.select_for_update().get(user=self.user)

        data = dict()
        data["order"] = self.id
        data["user"] = self.user
        data["product"] = 1

        cancel_amount = self.get_cancel_amount(data)
        consumer_account.credit_cancellation(data, cancel_amount)

        return appointment

    def action_completed(self, appointment):
        appointment.status = self.COMPLETED
        appointment.save()
        return appointment

    def get_cancel_amount(self, data):
        consumer_tx = ConsumerTransaction.objects.filter(user=data["user"],
                                                         product=data["product"],
                                                         order=data["order"],
                                                         type=PgTransaction.DEBIT,
                                                         action=ConsumerTransaction.SALE).order_by("created_at").last()
        return consumer_tx.amount

    def send_notification(self, database_instance):
        if database_instance and database_instance.status == self.status:
            return
        if self.status == OpdAppointment.ACCEPTED:
            notification_models.NotificationAction.trigger(
                instance=self,
                user=self.user,
                notification_type=notification_models.NotificationAction.APPOINTMENT_ACCEPTED,
            )
        elif self.status == OpdAppointment.RESCHEDULED_PATIENT:
            notification_models.NotificationAction.trigger(
                instance=self,
                user=self.doctor.user,
                notification_type=notification_models.NotificationAction.APPOINTMENT_RESCHEDULED_BY_PATIENT)
        elif self.status == OpdAppointment.BOOKED:
            notification_models.NotificationAction.trigger(
                instance=self,
                user=self.user,
                notification_type=notification_models.NotificationAction.APPOINTMENT_BOOKED,
            )
            notification_models.NotificationAction.trigger(
                instance=self,
                user=self.doctor.user,
                notification_type=notification_models.NotificationAction.APPOINTMENT_BOOKED,
            )
        elif self.status == OpdAppointment.CANCELED:
            notification_models.NotificationAction.trigger(
                instance=self,
                user=self.doctor.user,
                notification_type=notification_models.NotificationAction.APPOINTMENT_CANCELLED,
            )

    def save(self, *args, **kwargs):
        database_instance = OpdAppointment.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        self.send_notification(database_instance)

    def payment_confirmation(self, consumer_account, data, amount):
        otp = random.randint(1000, 9999)
        self.payment_status = OpdAppointment.PAYMENT_ACCEPTED
        self.otp = otp
        self.save()
        consumer_account.debit_schedule(data, amount)

    class Meta:
        db_table = "opd_appointment"


class DoctorLeave(TimeStampedModel):
    INTERVAL_MAPPING = {
        ("00:00:00", "14:00:00"): 'morning',
        ("14:00:00", "23:59:59"): 'evening',
        ("00:00:00", "23:59:59"): 'all',
    }
    doctor = models.ForeignKey(Doctor, related_name="leaves", on_delete=models.CASCADE)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.doctor.name + "(" + str(self.start_time) + "," + str(self.end_date) + str(self.start_date)

    class Meta:
        db_table = "doctor_leave"

    @property
    def interval(self):
        return self.INTERVAL_MAPPING.get((str(self.start_time), str(self.end_time)))


class Prescription (TimeStampedModel):
    appointment = models.ForeignKey(OpdAppointment,  on_delete=models.CASCADE)
    prescription_details = models.TextField(max_length=300, blank=True, null=True)

    def __str__(self):
        return "{}-{}".format(self.id, self.appointment.id)

    class Meta:
        db_table = "prescription"


class PrescriptionFile(TimeStampedModel):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE)
    file = models.FileField(upload_to='prescriptions', blank=False, null=False)

    def __str__(self):
        return "{}-{}".format(self.id, self.prescription.id)

    class Meta:
        db_table = "prescription_file"


class MedicalCondition(TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name="Name")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = "medical_condition"
