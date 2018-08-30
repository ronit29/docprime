from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.conf import settings
from ondoc.authentication.models import TimeStampedModel
import hashlib

class OnlineLead(TimeStampedModel):
    DOCTOR = 1
    DIAGNOSTICCENTER = 2
    HOSPITAL = 3
    TYPE_CHOICES = (("", "Select"), (DOCTOR, 'Doctor'), (DIAGNOSTICCENTER, "Diagnostic Center"),
                    (HOSPITAL, 'Hospital/Clinic'),)
    member_type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    speciality = models.CharField(max_length=255, blank=True, null=True)
    mobile = models.BigIntegerField(blank=False, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    city = models.CharField(max_length=255, blank=False, default='')
    email = models.EmailField(blank=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "online_lead"


class Career(TimeStampedModel):
    PRODUCT = 1
    TECHNOLOGY = 2
    SALES = 3
    CONTENT = 4
    MARKETING = 5
    QC = 6
    SUPPORT = 7
    DOCTORS = 8
    PROFILE_TYPE_CHOICES = (("", "Select Function"), (PRODUCT, 'Product'), (TECHNOLOGY, 'Technology'), (SALES, 'Sales'),
                             (CONTENT, 'Content'), (MARKETING, 'Marketing'), (QC, 'QC'), (SUPPORT, 'Support'),
                             (DOCTORS, 'Doctors'), )
    profile_type = models.PositiveSmallIntegerField(blank=False, choices=PROFILE_TYPE_CHOICES)
    name = models.CharField(max_length=255)
    mobile = models.BigIntegerField(blank=False, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)
                                                            ])
    email = models.EmailField()
    resume = models.FileField(upload_to='resumes', blank=False, null=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "career"


class ContactUs(TimeStampedModel):
    name = models.CharField(max_length=255)
    mobile = models.BigIntegerField(validators=[MaxValueValidator(9999999999),
                                                MinValueValidator(1000000000)])
    email = models.EmailField()
    message = models.CharField(max_length=2000)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "contactus"


class TinyUrl(TimeStampedModel):
    SHORT_URL_PREFIX = 'short'
    original_url = models.URLField(max_length=5000)
    short_code = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return "{}".format(self.id)

    def get_tiny_url(self):
        return "{}/{}/{}".format(settings.BASE_URL, TinyUrl.SHORT_URL_PREFIX, self.short_code)

    class Meta:
        db_table = 'tiny_url'
