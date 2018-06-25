from django.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from ondoc.authentication.models import TimeStampedModel


class OnlineLeads(TimeStampedModel):
    DOCTOR = 1
    DIAGNOSTICCENTER = 2
    HOSPITAL = 3
    TYPE_CHOICES = (("", "Select"), (DOCTOR, 'Doctor'), (DIAGNOSTICCENTER, "Diagnostic Center"),
                    (HOSPITAL, 'Hospital/Clinic'),)
    member_type = models.PositiveSmallIntegerField(choices=TYPE_CHOICES)
    name = models.CharField(max_length=255)
    mobile = models.BigIntegerField(blank=False, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)
                                                            ])
    email = models.EmailField(blank=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "online_leads"


class Careers(TimeStampedModel):
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
        db_table = "careers"
