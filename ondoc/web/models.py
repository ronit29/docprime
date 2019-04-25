import logging

from django.db import models, transaction
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.conf import settings
from ondoc.authentication.models import TimeStampedModel, UserProfile, User
from ondoc.common.models import Cities
from ondoc.doctor.models import Doctor, Hospital
from ondoc.matrix.tasks import push_signup_lead_to_matrix, push_non_bookable_doctor_lead_to_matrix
import json
from django.contrib.postgres.fields import JSONField
import hashlib

logger = logging.getLogger(__name__)

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
    city = models.CharField(max_length=255, blank=True, null=True, default='')
    city_name = models.ForeignKey(Cities, on_delete=models.SET_NULL, null=True)
    email = models.EmailField(blank=False)
    matrix_lead_id = models.IntegerField(null=True)
    utm_params = JSONField(blank=True, null=True)
    source = models.CharField(max_length=128, null=True)

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        push_to_matrix = kwargs.get('push_again_to_matrix', True)
        if 'push_again_to_matrix' in kwargs.keys():
            kwargs.pop('push_again_to_matrix')

        super().save(*args, **kwargs)

        if push_to_matrix:
            product_id = 0
            if self.member_type == 1 or self.member_type == 3:
                product_id = 1
            elif self.member_type == 2:
                product_id = 4

            if push_to_matrix:
                push_signup_lead_to_matrix.apply_async(({'type': 'SIGNUP_LEAD', 'lead_id': self.id,
                                                         'product_id': product_id, 'sub_product_id': 0}, ), countdown=5)

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
    from_app = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "contactus"


class TinyUrl(TimeStampedModel):
    SHORT_URL_PREFIX = 'short'
    original_url = models.URLField(max_length=5000)
    short_code = models.CharField(max_length=50, unique=True,db_index=True)

    def __str__(self):
        return "{}".format(self.id)

    def get_tiny_url(self):
        return "{}/{}/{}".format(settings.BASE_URL, TinyUrl.SHORT_URL_PREFIX, self.short_code)

    class Meta:
        db_table = 'tiny_url'


class TinyUrlHits(TimeStampedModel):
    tiny_url = models.ForeignKey(TinyUrl, blank=True, null=True, on_delete=models.SET_NULL)
    ip_address = models.CharField(max_length=500, blank=True, null=True)

    class Meta:
        db_table = 'tiny_url_hits'


class UploadImage(TimeStampedModel):
    name = models.CharField(blank=True, max_length=84)
    image = models.ImageField(upload_to='web/custom_images')

    def __str__(self):
        return "{}".format(self.name)


class NonBookableDoctorLead(TimeStampedModel):
    name = models.CharField(max_length=255, blank=True, default='')
    from_mobile = models.CharField(max_length=25)
    to_mobile = models.CharField(max_length=25, blank=True)
    doctor = models.ForeignKey(Doctor, on_delete=models.SET_NULL, null=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.SET_NULL, null=True)
    masked_mobile = models.CharField(max_length=25, blank=True, default='')
    matrix_lead_id = models.IntegerField(null=True)
    source = models.CharField(max_length=128, default='docprimeNB')

    @classmethod
    def create(cls, validated_data):
        t_from = validated_data.get('mobile', None)
        user_obj = User.objects.filter(phone_number=t_from, user_type=User.CONSUMER).first()
        t_user_prof = None
        if user_obj:
            t_user_prof = user_obj.profiles.filter(is_default_user=True).first()
        t_name = ''
        if t_user_prof:
            t_name = t_user_prof.name
        instance = NonBookableDoctorLead(name=t_name, from_mobile=t_from,
                       doctor=validated_data.get('doctor'), hospital=validated_data.get('hospital'))
        instance.save()
        try:
            push_non_bookable_doctor_lead_to_matrix.apply_async((instance.id,), countdown=5)
        except Exception as e:
            logger.error(str(e))
        return instance

    class Meta:
        db_table = "nb_doctor_lead"
