from django.contrib.gis.db import models
from django.db import migrations
from django.contrib.postgres.operations import CreateExtension
from django.core.validators import MaxValueValidator, MinValueValidator
from django.core.exceptions import ValidationError
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils.safestring import mark_safe

from ondoc.authentication.models import TimeStampedModel, CreatedByModel, Image, QCModel


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
        db_table = "medical_services"


class Hospital(TimeStampedModel, CreatedByModel, QCModel):

    name = models.CharField(max_length=200, blank=True)
    address = models.CharField(max_length=500)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    years_operational = models.PositiveSmallIntegerField(blank=True, null=True,  validators=[MaxValueValidator(200), MinValueValidator(1)])
    registration_number = models.CharField(max_length=500, blank=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    hospital_type = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Private"), (2,"Clinic"), (3,"Hospital")])

    def __str__(self):
        return self.name

    class Meta:
        db_table = "hospital"


class Doctor(TimeStampedModel, CreatedByModel, QCModel):

    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=2, default=None, blank=True, choices=[("","Select"), ("m","Male"), ("f","Female"), ("o","Other")])
    practice_duration = models.PositiveSmallIntegerField(default=None, blank=True, null=True,validators=[MaxValueValidator(100), MinValueValidator(1)])
    about = models.CharField(max_length=2000, blank=True)
    registration_details = models.CharField(max_length=200, blank=True)
    additional_details = models.CharField(max_length=2000, blank=True)
    country_code = models.PositiveSmallIntegerField(default=91, blank=True, null=True)
    phone_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    is_phone_number_verified = models.BooleanField(verbose_name= 'Phone Number Verified', default=False)
    email = models.EmailField(max_length=100, blank=True)
    is_email_verified = models.BooleanField(verbose_name= 'Email Verified', default=False)

    hospitals = models.ManyToManyField(
        Hospital,
        through='DoctorHospital',
        through_fields=('doctor', 'hospital'),
    )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "doctor"


class Specialization(TimeStampedModel, CreatedByModel, UniqueNameModel):
    name = models.CharField(max_length=200)
    human_readable_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "specialization"


class Qualification(TimeStampedModel, CreatedByModel, UniqueNameModel):
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
    doctor = models.ForeignKey(Doctor, related_name="qualificationSpecialization", on_delete=models.CASCADE)
    qualification = models.ForeignKey(Qualification, on_delete=models.CASCADE)
    specialization = models.ForeignKey(Specialization, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        if self.specialization_id:
            return self.qualification.name + " (" + self.specialization.name + ")"
        return self.qualification.name

    class Meta:
        db_table = "doctor_qualification"
        unique_together = (("doctor", "qualification", "specialization"))


class DoctorHospital(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="availability", on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=[(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"), (6, "Saturday"), (7, "Sunday")])

    start = models.PositiveSmallIntegerField(
        blank=False, null=False, choices=[(6, "6 AM"), (7, "7 AM"),
        (8, "8 AM"), (9, "9 AM"), (10, "10 AM"), (11, "11 AM"),
        (12, "12 PM"), (13, "1 PM"), (14, "2 PM"), (15, "3 PM"),
        (16, "4 PM"), (17, "5 PM"), (18, "6 PM"), (19, "7 PM"),
        (20, "8 PM"), (21, "9 PM"), (22, "10 PM"), (23, "11 PM")])

    end = models.PositiveSmallIntegerField(
        blank=False, null=False, choices=[(6, "6 AM"), (7, "7 AM"),
        (8, "8 AM"), (9, "9 AM"), (10, "10 AM"), (11, "11 AM"),
        (12, "12 PM"), (13, "1 PM"), (14, "2 PM"), (15, "3 PM"),
        (16, "4 PM"), (17, "5 PM"), (18, "6 PM"), (19, "7 PM"),
        (20, "8 PM"), (21, "9 PM"), (22, "10 PM"), (23, "11 PM")])

    fees = models.PositiveSmallIntegerField(blank=False, null=False)

    class Meta:
        db_table = "doctor_hospital"


class DoctorImage(TimeStampedModel, Image):
    doctor = models.ForeignKey(Doctor, related_name="profile_img", on_delete=models.CASCADE)
    name = models.ImageField(upload_to='doctor/images',height_field='height', width_field='width')

    class Meta:
        db_table = "doctor_image"

class DoctorDocument(TimeStampedModel, Image):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='doctor/documents',height_field='height', width_field='width')

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
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_awards"

class DoctorAssociation(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_association"


class DoctorExperience(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="pastExperience", on_delete=models.CASCADE)
    hospital = models.CharField(max_length=200)
    start_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,validators=[MinValueValidator(1950)])
    end_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,validators=[MinValueValidator(1950)])

    class Meta:
        db_table = "doctor_experience"


class DoctorMedicalService(TimeStampedModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    service = models.ForeignKey(MedicalService, on_delete=models.CASCADE)

    class Meta:
        db_table = "doctor_medical_service"
        unique_together = (("doctor", "service"))
