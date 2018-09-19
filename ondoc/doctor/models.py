from django.contrib.gis.db import models
from django.db import migrations, transaction
from django.db.models import Count, Sum, When, Case, Q, F
from django.contrib.postgres.operations import CreateExtension
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.postgres.fields import JSONField
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.core.exceptions import NON_FIELD_ERRORS
from rest_framework.exceptions import ValidationError as RestFrameworkValidationError
from django.core.files.storage import get_storage_class
from django.conf import settings
from datetime import timedelta
from dateutil import tz
from django.utils import timezone
from ondoc.authentication import models as auth_model
from ondoc.location import models as location_models
from ondoc.account.models import Order, ConsumerAccount, ConsumerTransaction, PgTransaction, ConsumerRefund
from ondoc.payout.models import Outstanding
from ondoc.doctor.tasks import doc_app_auto_cancel
# from ondoc.account import models as account_model
from ondoc.insurance import models as insurance_model
from ondoc.payout import models as payout_model
from ondoc.notification import models as notification_models
from ondoc.notification import tasks as notification_tasks
from django.contrib.contenttypes.fields import GenericRelation
from ondoc.api.v1.utils import get_start_end_datetime, custom_form_datetime
from functools import reduce
from operator import or_
import logging
import math
import random
import os
import re
import datetime
from django.db.models import Q
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.safestring import mark_safe
from PIL import Image as Img
from io import BytesIO
import hashlib
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.matrix.tasks import push_appointment_to_matrix

logger = logging.getLogger(__name__)


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
                        self.__class__.__name__ + ' with same name already exists',
                    ],
                }
            )

    class Meta:
        abstract = True


class SearchKey(models.Model):
    search_key = models.CharField(max_length=256, blank=True, null=True)

    class Meta:
        db_table = 'search_key'
        abstract = True

    def save(self, *args, **kwargs):
        name = self.name
        if name:
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            self.search_key = search_key
        super().save(*args, **kwargs)


class MedicalService(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "medical_service"


class Hospital(auth_model.TimeStampedModel, auth_model.CreatedByModel, auth_model.QCModel, SearchKey):
    PRIVATE = 1
    CLINIC = 2
    HOSPITAL = 3
    HOSPITAL_TYPE_CHOICES = (("", "Select"), (PRIVATE, 'Private'), (CLINIC, "Clinic"), (HOSPITAL, "Hospital"),)
    name = models.CharField(max_length=200)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1800)])
    parking = models.PositiveSmallIntegerField(blank=True, null=True,
                                               choices=[("", "Select"), (1, "Easy"), (2, "Difficult")])
    registration_number = models.CharField(max_length=500, blank=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    hospital_type = models.PositiveSmallIntegerField(blank=True, null=True, choices=HOSPITAL_TYPE_CHOICES)
    network_type = models.PositiveSmallIntegerField(blank=True, null=True,
                                                    choices=[("", "Select"), (1, "Non Network Hospital"),
                                                             (2, "Network Hospital")])
    network = models.ForeignKey('HospitalNetwork', null=True, blank=True, on_delete=models.SET_NULL, related_name='assoc_hospitals')
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)
    is_appointment_manager = models.BooleanField(verbose_name='Enabled for Managing Appointments', default=False)
    is_live = models.BooleanField(verbose_name='Is Live', default=False)
    live_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_hospital')
    billing_merchant = GenericRelation(auth_model.BillingAccount)
    entity = GenericRelation(location_models.EntityLocationRelationship)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "hospital"

    def get_thumbnail(self):
        return None
        # return static("hospital_images/hospital_default.png")

    def get_address(self):
        address_items = [value for value in
                         [self.building, self.sublocality, self.locality, self.city, self.state, self.country] if value]
        return ", ".join(address_items)

    def get_short_address(self):
        address_items = [value for value in
                         [self.sublocality, self.locality] if value]
        return ", ".join(address_items)


    def save(self, *args, **kwargs):
        build_url = True
        if self.is_live:
            if Hospital.objects.filter(location__distance_lte=(self.location, 0), id=self.id).exists():
                build_url = False

        super(Hospital, self).save(*args, **kwargs)

        if self.is_appointment_manager:
            auth_model.GenericAdmin.objects.filter(hospital=self, permission_type=auth_model.GenericAdmin.APPOINTMENT)\
                .update(is_disabled=True)
        else:
            auth_model.GenericAdmin.objects.filter(hospital=self, permission_type=auth_model.GenericAdmin.APPOINTMENT)\
                .update(is_disabled=False)

        if build_url and self.location and self.is_live:
            ea = location_models.EntityLocationRelationship.create(latitude=self.location.y, longitude=self.location.x, content_object=self)


class HospitalAward(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_award"


class HospitalAccreditation(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_accreditation"


class HospitalCertification(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_certification"


class HospitalSpeciality(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_speciality"


# class ClinicalSpeciality(auth_model.TimeStampedModel):
#     name = models.CharField(max_length=1000)

#     def __str__(self):
#         return self.name

#     class Meta:
#         db_table = "clinical_speciality"


# class HospitalClinicalSpeciality(auth_model.TimeStampedModel):
#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
#     speciality = models.ForeignKey(ClinicalSpeciality, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.hospital.name + " (" + self.clinical_speciality.name + ")"

#     class Meta:
#         db_table = "hospital_clinical_speciality"
#         unique_together = (("hospital", "speciality"))


class College(auth_model.TimeStampedModel):
    name = models.CharField(max_length=200, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "college"


class Doctor(auth_model.TimeStampedModel, auth_model.QCModel, SearchKey):
    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"),
                         (ONBOARDED, "Onboarded")]

    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=2, default=None, blank=True, null=True,
                              choices=[("", "Select"), ("m", "Male"), ("f", "Female"), ("o", "Other")])
    practicing_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])
    raw_about = models.CharField(max_length=2000, blank=True)
    about = models.CharField(max_length=2000, blank=True)
    # primary_mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999),
    #                                                                            MinValueValidator(1000000000)])
    license = models.CharField(max_length=200, blank=True)
    onboarding_status = models.PositiveSmallIntegerField(default=NOT_ONBOARDED, choices=ONBOARDING_STATUS)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    additional_details = models.CharField(max_length=2000, blank=True)
    # email = models.EmailField(max_length=100, blank=True)
    is_email_verified = models.BooleanField(verbose_name='Email Verified', default=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="doctor", on_delete=models.SET_NULL, default=None,
                                blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_doctors", null=True, editable=False,
                                   on_delete=models.SET_NULL)

    is_insurance_enabled = models.BooleanField(verbose_name='Enabled for Insurance Customer', default=False)
    is_retail_enabled = models.BooleanField(verbose_name='Enabled for Retail Customer', default=False)
    is_online_consultation_enabled = models.BooleanField(verbose_name='Available for Online Consultation',
                                                         default=False)
    online_consultation_fees = models.PositiveSmallIntegerField(blank=True, null=True)
    is_live = models.BooleanField(verbose_name='Is Live', default=False)
    live_at = models.DateTimeField(null=True, blank=True)
    is_internal = models.BooleanField(verbose_name='Is Staff Doctor', default=False)
    is_test_doctor = models.BooleanField(verbose_name='Is Test Doctor', default=False)
    # doctor_admins = models.ForeignKey(auth_model.GenericAdmin, related_query_name='manageable_doctors')
    hospitals = models.ManyToManyField(
        Hospital,
        through='DoctorClinic',
        through_fields=('doctor', 'hospital'),
        related_name='assoc_doctors',
    )
    assigned_to = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_doctors')
    matrix_lead_id = models.BigIntegerField(blank=True, null=True)
    matrix_reference_id = models.BigIntegerField(blank=True, null=True)
    signature = models.ImageField('Doctor Signature', upload_to='doctor/images', null=True, blank=True)
    billing_merchant = GenericRelation(auth_model.BillingAccount)
    enabled = models.BooleanField(verbose_name='Is Enabled', default=True)

    def __str__(self):
        return self.name

    def get_display_name(self):
        return "Dr. {}".format(self.name.title()) if self.name else None

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

    def get_thumbnail(self):
        for image in self.images.all():
            if image.cropped_image:
                return image.get_thumbnail_path(image.cropped_image.url,'80x80')
        # if self.images.all():
        #     return self.images.all()[0].name.url
        return None

    def update_live_status(self):

        if not self.is_live and (self.onboarding_status == self.ONBOARDED and self.data_status == self.QC_APPROVED and self.enabled == True):
            # dochospitals = []
            # for hosp in self.hospitals.all():
            #     dochospitals.append(hosp.id)
            # queryset = auth_model.GenericAdmin.objects.filter(Q(is_disabled=False, user__isnull=False, permission_type = auth_model.GenericAdmin.APPOINTMENT),
            #                                (Q(doctor__isnull=False, doctor=self) |
            #                                 Q(doctor__isnull=True, hospital__id__in=dochospitals)))

            self.is_live = True
            if not self.live_at:
                self.live_at = datetime.datetime.now()
        if self.is_live and (self.onboarding_status != self.ONBOARDED or self.data_status != self.QC_APPROVED or self.enabled == False):
            self.is_live = False

    def save(self, *args, **kwargs):
        self.update_live_status()
        super(Doctor, self).save(*args, **kwargs)
        if self.is_live:
            location_models.EntityUrls.create_page_url(self)



    class Meta:
        db_table = "doctor"


class AboutDoctor(Doctor):

    class Meta:
        proxy = True
        default_permissions = []


class Specialization(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=200)
    human_readable_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "specialization"


class Qualification(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "qualification"


class Symptoms(auth_model.TimeStampedModel, auth_model.CreatedByModel, UniqueNameModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "symptoms"


class DoctorQualification(auth_model.TimeStampedModel):
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
        unique_together = (("doctor", "qualification", "specialization", "college"),)


class GeneralSpecialization(auth_model.TimeStampedModel, UniqueNameModel, SearchKey):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "general_specialization"


class DoctorSpecialization(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="doctorspecializations", on_delete=models.CASCADE)
    specialization = models.ForeignKey(GeneralSpecialization, on_delete=models.CASCADE, blank=False, null=False)

    def __str__(self):
       return self.doctor.name + " (" + self.specialization.name + ")"

    class Meta:
        db_table = "doctor_specialization"
        unique_together = ("doctor", "specialization")


class DoctorClinic(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='doctor_clinics')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    followup_duration = models.PositiveSmallIntegerField(blank=True, null=True)
    followup_charges = models.PositiveSmallIntegerField(blank=True, null=True)

    class Meta:
        db_table = "doctor_clinic"
        unique_together = (('doctor', 'hospital', ),)

    def __str__(self):
        return '{}-{}'.format(self.doctor, self.hospital)


class DoctorClinicTiming(auth_model.TimeStampedModel):
    DAY_CHOICES = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE, related_name='availability')
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

    TYPE_CHOICES = [(1, "Fixed"),
                    (2, "On Call")]

    start = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    end = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    fees = models.PositiveSmallIntegerField(blank=False, null=False)
    deal_price = models.PositiveSmallIntegerField(blank=True, null=True)
    mrp = models.PositiveSmallIntegerField(blank=False, null=True)
    type = models.IntegerField(default=1, choices=TYPE_CHOICES)
    # followup_duration = models.PositiveSmallIntegerField(blank=False, null=True)
    # followup_charges = models.PositiveSmallIntegerField(blank=False, null=True)

    class Meta:
        db_table = "doctor_clinic_timing"
        # unique_together = (("start", "end", "day", "doctor_clinic",),)

    def save(self, *args, **kwargs):
        if self.mrp!=None:
            deal_price = math.ceil(self.fees + (self.mrp - self.fees)*.1)
            deal_price = math.ceil(deal_price/10)*10
            if deal_price<self.fees:
                deal_price = self.fees

            deal_price = max(deal_price, 100)
            deal_price = min(self.mrp, deal_price)
            #if deal_price>self.mrp:
            #    deal_price = self.mrp
            self.deal_price = deal_price
        super().save(*args, **kwargs)


class DoctorHospital(auth_model.TimeStampedModel):
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
    fees = models.PositiveSmallIntegerField(blank=False, null=False)
    deal_price = models.PositiveSmallIntegerField(blank=True, null=True)
    mrp = models.PositiveSmallIntegerField(blank=False, null=True)
    followup_duration = models.PositiveSmallIntegerField(blank=False, null=True)
    followup_charges = models.PositiveSmallIntegerField(blank=False, null=True)

    def __str__(self):
        return self.doctor.name + " " + self.hospital.name + " ," + str(self.start)+ " " + str(self.end) + " " + str(self.day)

    def discounted_fees(self):
        return self.fees

    class Meta:
        db_table = "doctor_hospital"
        unique_together = (("start", "end", "day", "hospital", "doctor"),)

    def save(self, *args, **kwargs):
        if self.mrp!=None:
            deal_price = math.ceil(self.fees + (self.mrp - self.fees)*.1)
            deal_price = math.ceil(deal_price/10)*10
            if deal_price>self.mrp:
                deal_price = self.mrp
            if deal_price<self.fees:
                deal_price = self.fees
            self.deal_price = deal_price
        super().save(*args, **kwargs)


class DoctorImage(auth_model.TimeStampedModel, auth_model.Image):
    image_sizes = [(80, 80)]
    image_base_path = 'doctor/images'
    doctor = models.ForeignKey(Doctor, related_name="images", on_delete=models.CASCADE)
    name = models.ImageField('Original Image Name',upload_to='doctor/images',height_field='height', width_field='width')
    cropped_image = models.ImageField(upload_to='doctor/images', height_field='height', width_field='width',
                                      blank=True, null=True)

    def __str__(self):
        return '{}'.format(self.doctor)

    def resize_cropped_image(self, width, height):
        default_storage_class = get_storage_class()
        storage_instance = default_storage_class()

        path = self.get_thumbnail_path(self.cropped_image.name,"{}x{}".format(width, height))
        if storage_instance.exists(path):
            return

        if self.cropped_image.closed:
            self.cropped_image.open()
        with Img.open(self.cropped_image) as img:
            img = img.copy()

                # original_width, original_height = img.size
                # if original_width > original_height:
                #     ratio = width/float(original_width)
                #     height = int(float(original_height)*float(ratio))
                # else:
                #     ratio = height / float(original_height)
                #     width = int(float(original_width) * float(ratio))
            img.thumbnail(tuple([width, height]), Img.LANCZOS)

                #img = img.resize(tuple([width, height]), Img.ANTIALIAS)
            if img.mode != 'RGB':
                img = img.convert('RGB')

            new_image_io = BytesIO()
            img.save(new_image_io, format='JPEG')
            in_memory_file = InMemoryUploadedFile(new_image_io, None, os.path.basename(path), 'image/jpeg',
                                                      new_image_io.tell(), None)
            storage_instance.save(path, in_memory_file)


    def create_all_images(self):
        if not self.cropped_image:
            return
        for size in DoctorImage.image_sizes:
            width = size[0]
            height = size[1]
            self.resize_cropped_image(width, height)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.create_all_images()

    def original_image(self):
        return mark_safe('<div><img crossOrigin="anonymous" style="max-width:300px; max-height:300px;" src="{0}"/></div>'.format(self.name.url))

    def cropped_img(self):
        return mark_safe('<div><img style="max-width:200px; max-height:200px;" src="{0}"/></div>'.format(self.cropped_image.url))

    def crop_image(self):
        if self.cropped_image:
            return
        if self.name:
            img = Img.open(self.name)
            w, h = img.size
            if w > h:
                cropping_area = (w / 2 - h / 2,  0, w / 2 + h / 2, h)
            else:
                cropping_area = (0, h / 2 - w / 2, w, h / 2 + w / 2)
            if h != w:
                img = img.crop(cropping_area)
            new_image_io = BytesIO()
            img.save(new_image_io, format='JPEG')
            md5_hash = hashlib.md5(img.tobytes()).hexdigest()
            self.cropped_image = InMemoryUploadedFile(new_image_io, None, md5_hash + ".jpg", 'image/jpeg',
                                                      new_image_io.tell(), None)
            self.save()

    def save_to_cropped_image(self, image_file):
        if image_file:
            img = Img.open(image_file)
            md5_hash = hashlib.md5(img.tobytes()).hexdigest()
            self.cropped_image.save(md5_hash + ".jpg", image_file, save=True)
            #self.save()

    class Meta:
        db_table = "doctor_image"


class DoctorDocument(auth_model.TimeStampedModel, auth_model.Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    REGISTRATION = 4
    CHEQUE = 5
    AADHAR = 7
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (REGISTRATION, "MCI Registration Number"), (CHEQUE, "Cancel Cheque Copy"), (AADHAR, "Aadhar Card")]

    doctor = models.ForeignKey(Doctor, related_name="documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='doctor/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')

    class Meta:
        db_table = "doctor_document"


class HospitalImage(auth_model.TimeStampedModel, auth_model.Image):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='hospital/images', height_field='height', width_field='width')

    class Meta:
        db_table = "hospital_image"


class HospitalDocument(auth_model.TimeStampedModel, auth_model.Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    CHEQUE = 5
    COI = 8
    EMAIL_CONFIRMATION = 9
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (CHEQUE, "Cancel Cheque Copy"), (COI, "COI/Company Registration"),
               (EMAIL_CONFIRMATION, "Email Confirmation")]

    hospital = models.ForeignKey(Hospital, related_name="hospital_documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES, default=ADDRESS)
    name = models.FileField(upload_to='hospital/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    class Meta:
        db_table = "hospital_document"


class Language(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "language"


class DoctorLanguage(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="languages", on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)

    def __str__(self):
        return self.doctor.name + " (" + self.language.name + ")"

    class Meta:
        db_table = "doctor_language"
        unique_together = (("doctor", "language"),)


class DoctorAward(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="awards", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_awards"


class DoctorAssociation(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="associations", on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_association"


class DoctorExperience(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="experiences", on_delete=models.CASCADE)
    hospital = models.CharField(max_length=200)
    start_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,
                                                  validators=[MinValueValidator(1950)])
    end_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,
                                                validators=[MinValueValidator(1950)])

    class Meta:
        db_table = "doctor_experience"


class DoctorMedicalService(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="medical_services", on_delete=models.CASCADE)
    service = models.ForeignKey(MedicalService, on_delete=models.CASCADE)

    class Meta:
        db_table = "doctor_medical_service"
        unique_together = (("doctor", "service"),)


class DoctorMobile(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="mobiles", on_delete=models.CASCADE)
    country_code = models.PositiveSmallIntegerField(default=91, blank=True, null=True)
    number = models.BigIntegerField(blank=True, null=True,
                                    validators=[MaxValueValidator(9999999999), MinValueValidator(7000000000)])
    is_primary = models.BooleanField(verbose_name='Primary Number?', default=False)
    is_phone_number_verified = models.BooleanField(verbose_name='Phone Number Verified?', default=False)

    class Meta:
        db_table = "doctor_mobile"
        unique_together = (("doctor", "number"),)


class DoctorEmail(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="emails", on_delete=models.CASCADE)
    email = models.EmailField(max_length=100, blank=True)
    is_primary = models.BooleanField(verbose_name='Primary Email?', default=False)
    is_email_verified = models.BooleanField(verbose_name='Phone Number Verified?', default=False)

    class Meta:
        db_table = "doctor_email"
        unique_together = (("doctor", "email"),)


class HospitalNetwork(auth_model.TimeStampedModel, auth_model.CreatedByModel, auth_model.QCModel):
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
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)

    # generic_hospital_network_admins = GenericRelation(auth_model.GenericAdmin, related_query_name='manageable_hospital_networks')
    assigned_to = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_hospital_networks')
    billing_merchant = GenericRelation(auth_model.BillingAccount)

    def __str__(self):
        return self.name + " (" + self.city + ")"

    class Meta:
        db_table = "hospital_network"


class HospitalNetworkDocument(auth_model.TimeStampedModel, auth_model.Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    CHEQUE = 5
    COI = 8
    EMAIL_CONFIRMATION = 9
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (CHEQUE, "Cancel Cheque Copy"),(COI, "COI/Company Registration"),
               (EMAIL_CONFIRMATION, "Email Confirmation")]

    hospital_network = models.ForeignKey(HospitalNetwork, related_name="hospital_network_documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='hospital_network/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    class Meta:
        db_table = "hospital_network_document"


class HospitalNetworkCertification(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_certification"


class HospitalNetworkAward(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_award"


class HospitalNetworkAccreditation(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_accreditation"


class HospitalNetworkManager(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(
        choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager")])

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_manager"


class HospitalNetworkHelpline(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    number = models.BigIntegerField()
    details = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_helpline"


class HospitalNetworkEmail(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_email"


class DoctorOnboardingToken(auth_model.TimeStampedModel):
    GENERATED = 1
    REJECTED = 2
    CONSUMED = 3
    STATUS_CHOICES = [(GENERATED, "Generated"), (REJECTED, "Rejected"), (CONSUMED, "Consumed")]
    doctor = models.ForeignKey(Doctor, null=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    mobile = models.BigIntegerField(blank=True, null=True,
                                    validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    verified_token = models.CharField(max_length=100, null=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=GENERATED)

    def __str__(self):
        return self.doctor.name + " " + self.email + " " + str(self.mobile)

    class Meta:
        db_table = "doctor_onboarding_token"


# class HospitalNetworkMapping(auth_model.TimeStampedModel):
#     network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.network.name + " (" + self.hospital.name + ")"

#     class Meta:
#         db_table = "hospital_network_mapping"


class OpdAppointment(auth_model.TimeStampedModel):
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_DOCTOR = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )
    PREPAID = 1
    COD = 2
    INSURANCE = 3
    PAY_CHOICES = ((PREPAID, 'Prepaid'), (COD, 'COD'), (INSURANCE, 'Insurance'))
    ACTIVE_APPOINTMENT_STATUS = [BOOKED, ACCEPTED, RESCHEDULED_PATIENT, RESCHEDULED_DOCTOR]
    STATUS_CHOICES = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                      (RESCHEDULED_DOCTOR, 'Rescheduled by Doctor'),
                      (RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                      (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                      (COMPLETED, 'Completed')]
    PATIENT_CANCELLED = 1
    AGENT_CANCELLED = 2
    AUTO_CANCELLED = 3
    CANCELLATION_TYPE_CHOICES = [(PATIENT_CANCELLED, 'Patient Cancelled'), (AGENT_CANCELLED, 'Agent Cancelled'),
                                 (AUTO_CANCELLED, 'Auto Cancelled')]
    # PATIENT_SHOW = 1
    # PATIENT_DIDNT_SHOW = 2
    # PATIENT_STATUS_CHOICES = [PATIENT_SHOW, PATIENT_DIDNT_SHOW]
    doctor = models.ForeignKey(Doctor, related_name="appointments", on_delete=models.SET_NULL, null=True)
    hospital = models.ForeignKey(Hospital, related_name="hospital_appointments", on_delete=models.SET_NULL, null=True)
    profile = models.ForeignKey(auth_model.UserProfile, related_name="appointments", on_delete=models.SET_NULL, null=True)
    profile_detail = JSONField(blank=True, null=True)
    user = models.ForeignKey(auth_model.User, related_name="appointments", on_delete=models.SET_NULL, null=True)
    booked_by = models.ForeignKey(auth_model.User, related_name="booked_appointements", on_delete=models.SET_NULL, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2)
    effective_price = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=None)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=None)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2, blank=False, default=None, null=False)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)
    cancellation_type = models.PositiveSmallIntegerField(choices=CANCELLATION_TYPE_CHOICES, blank=True, null=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    otp = models.PositiveIntegerField(blank=True, null=True)
    # patient_status = models.PositiveSmallIntegerField(blank=True, null=True)
    time_slot_start = models.DateTimeField(blank=True, null=True)
    time_slot_end = models.DateTimeField(blank=True, null=True)
    payment_type = models.PositiveSmallIntegerField(choices=PAY_CHOICES, default=PREPAID)
    insurance = models.ForeignKey(insurance_model.Insurance, blank=True, null=True, default=None,
                                  on_delete=models.DO_NOTHING)
    outstanding = models.ForeignKey(Outstanding, blank=True, null=True, on_delete=models.SET_NULL)
    matrix_lead_id = models.IntegerField(null=True)

    def __str__(self):
        return self.profile.name + " (" + self.doctor.name + ")"

    def allowed_action(self, user_type, request):
        allowed = []
        current_datetime = timezone.now()
        today = datetime.date.today()
        if user_type == auth_model.User.DOCTOR and self.time_slot_start.date() >= today:
            perm_queryset = auth_model.GenericAdmin.objects.filter(is_disabled=False,
                                                                   hospital=self.hospital,
                                                                   user=request.user)
            if perm_queryset.first():
                doc_permission = perm_queryset.first()
                if doc_permission.write_permission or doc_permission.super_user_permission:
                    if self.status in [self.BOOKED, self.RESCHEDULED_PATIENT]:
                        allowed = [self.ACCEPTED, self.RESCHEDULED_DOCTOR]
                    elif self.status == self.ACCEPTED:
                        allowed = [self.RESCHEDULED_DOCTOR, self.COMPLETED]
                    elif self.status == self.RESCHEDULED_DOCTOR:
                        allowed = [self.ACCEPTED]

        elif user_type == auth_model.User.CONSUMER and current_datetime <= self.time_slot_start:
            if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_DOCTOR, self.RESCHEDULED_PATIENT):
                allowed = [self.RESCHEDULED_PATIENT, self.CANCELLED]

        return allowed

    @classmethod
    def create_appointment(cls, appointment_data):
        otp = random.randint(1000, 9999)
        appointment_data["payment_status"] = OpdAppointment.PAYMENT_ACCEPTED
        appointment_data["status"] = OpdAppointment.BOOKED
        appointment_data["otp"] = otp
        app_obj = cls.objects.create(**appointment_data)
        return app_obj

    @transaction.atomic
    def action_rescheduled_doctor(self):
        self.status = self.RESCHEDULED_DOCTOR
        self.save()

    def action_rescheduled_patient(self, data):
        self.status = self.RESCHEDULED_PATIENT
        self.time_slot_start = data.get('time_slot_start')
        self.fees = data.get('fees', self.fees)
        self.mrp = data.get('mrp', self.mrp)
        self.deal_price = data.get('deal_price', self.deal_price)
        self.effective_price = data.get('effective_price', self.effective_price)
        self.save()

        # return self

    def action_accepted(self):
        self.status = self.ACCEPTED
        self.save()

    @transaction.atomic
    def action_cancelled(self, refund_flag=1):
        logger.error("Entered action_cancelled  - " + str(self.id) + " timezone - " + str(timezone.now()))

        # Taking Lock first
        consumer_account = None
        if self.payment_type == self.PREPAID:
            logger.error("Before Lock - " + str(self.id) + " timezone - " + str(timezone.now()))
            temp_list = ConsumerAccount.objects.get_or_create(user=self.user)
            consumer_account = ConsumerAccount.objects.select_for_update().get(user=self.user)
            logger.error("After Lock - " + str(self.id) + " timezone - " + str(timezone.now()))

        old_instance = OpdAppointment.objects.get(pk=self.id)
        if old_instance.status != self.CANCELLED:
            self.status = self.CANCELLED
            self.save()
            product_id = Order.DOCTOR_PRODUCT_ID
            if self.payment_type == self.PREPAID and ConsumerTransaction.valid_appointment_for_cancellation(self.id,
                                                                                                            product_id):
                cancel_amount = self.effective_price
                consumer_account.credit_cancellation(self, product_id, cancel_amount)

                if refund_flag:
                    ctx_obj = consumer_account.debit_refund()
                    ConsumerRefund.initiate_refund(self.user, ctx_obj)

    def action_completed(self):
        self.status = self.COMPLETED
        if self.payment_type != self.INSURANCE:
            admin_obj, out_level = self.get_billable_admin_level()
            app_outstanding_fees = self.doc_payout_amount()
            out_obj = payout_model.Outstanding.create_outstanding(admin_obj, out_level, app_outstanding_fees)
            self.outstanding = out_obj
        self.save()

    def generate_invoice(self):
        pass

    def get_billable_admin_level(self):
        if self.hospital.network and self.hospital.network.is_billing_enabled:
            return self.hospital.network, payout_model.Outstanding.HOSPITAL_NETWORK_LEVEL
        elif self.hospital.is_billing_enabled:
            return self.hospital, payout_model.Outstanding.HOSPITAL_LEVEL
        else:
            return self.doctor, payout_model.Outstanding.DOCTOR_LEVEL

    def get_cancel_amount(self, data):
        consumer_tx = (ConsumerTransaction.objects.filter(user=data["user"],
                                                                        product=data["product"],
                                                                        order=data["order"],
                                                                        type=PgTransaction.DEBIT,
                                                                        action=ConsumerTransaction.SALE).
                       order_by("created_at").last())
        return consumer_tx.amount

    def is_doctor_available(self):
        if DoctorLeave.objects.filter(start_date__lte=self.time_slot_start.date(),
                                      end_date__gte=self.time_slot_start.date(),
                                      start_time__lte=self.time_slot_start.time(),
                                      end_time__gte=self.time_slot_start.time(),
                                      doctor=self.doctor,
                                      deleted_at__isnull=True).exists():
            return False
        return True

    def is_to_send_notification(self, database_instance):
        if not database_instance:
            return True
        if database_instance.status != self.status:
            return True
        if (database_instance.status == self.status
                and database_instance.time_slot_start != self.time_slot_start
                and database_instance.status in [OpdAppointment.RESCHEDULED_DOCTOR, OpdAppointment.RESCHEDULED_PATIENT]
                and self.status in [OpdAppointment.RESCHEDULED_DOCTOR, OpdAppointment.RESCHEDULED_PATIENT]):
            return True
        return False

    def after_commit_tasks(self, old_instance, push_to_matrix):
        if push_to_matrix:
        # Push the appointment data to the matrix .
            push_appointment_to_matrix.apply_async(({'type': 'OPD_APPOINTMENT', 'appointment_id': self.id,
                                                     'product_id': 5, 'sub_product_id': 2}, ), countdown=5)

        if self.is_to_send_notification(old_instance):
            notification_tasks.send_opd_notifications.apply_async(kwargs={'appointment_id': self.id}, countdown=1)
        if not old_instance or old_instance.status != self.status:
            for e_id in settings.OPS_EMAIL_ID:
                notification_models.EmailNotification.ops_notification_alert(self, email_list=e_id, product=Order.DOCTOR_PRODUCT_ID)
        # try:
        #     if self.status not in [OpdAppointment.COMPLETED, OpdAppointment.CANCELLED, OpdAppointment.ACCEPTED]:
        #         countdown = self.get_auto_cancel_delay(self)
        #         doc_app_auto_cancel.apply_async(({
        #             "id": self.id,
        #             "status": self.status,
        #             "updated_at": int(self.updated_at.timestamp())
        #         }, ), countdown=countdown)
        # except Exception as e:
        #     logger.error("Error in auto cancel flow - " + str(e))
        print('all ops tasks completed')

    def save(self, *args, **kwargs):
        logger.error("opd save started - " + str(self.id) + " timezone - " + str(timezone.now()))
        database_instance = OpdAppointment.objects.filter(pk=self.id).first()
        # if not self.is_doctor_available():
        #     raise RestFrameworkValidationError("Doctor is on leave.")

        push_to_matrix = kwargs.get('push_again_to_matrix', True)
        if 'push_again_to_matrix' in kwargs.keys():
            kwargs.pop('push_again_to_matrix')

        logger.error("before super save  - " + str(self.id) + " timezone - " + str(timezone.now()))    
        super().save(*args, **kwargs)
        logger.error("after super save - " + str(self.id) + " timezone - " + str(timezone.now()))


        transaction.on_commit(lambda: self.after_commit_tasks(database_instance, push_to_matrix))
        logger.error("opd save completed - " + str(self.id) + " timezone - " + str(timezone.now()))

        # if push_to_matrix:
        #     # Push the appointment data to the matrix .
        #     push_appointment_to_matrix.apply_async(({'type': 'OPD_APPOINTMENT', 'appointment_id': self.id,
        #                                              'product_id': 5, 'sub_product_id': 2}, ), countdown=5)

        # if self.is_to_send_notification(database_instance):
        #     notification_tasks.send_opd_notifications.apply_async(kwargs={'appointment_id': self.id}, countdown=1)
        # if not database_instance or database_instance.status != self.status:
        #     for e_id in settings.OPS_EMAIL_ID:
        #         notification_models.EmailNotification.ops_notification_alert(self, email_list=e_id, product=Order.DOCTOR_PRODUCT_ID)

        # try:
        #     if self.status not in [OpdAppointment.COMPLETED, OpdAppointment.CANCELLED, OpdAppointment.ACCEPTED]:
        #         countdown = self.get_auto_cancel_delay(self)
        #         doc_app_auto_cancel.apply_async(({
        #             "id": self.id,
        #             "status": self.status,
        #             "updated_at": int(self.updated_at.timestamp())
        #         }, ), countdown=countdown)
        # except Exception as e:
        #     logger.error("Error in auto cancel flow - " + str(e))

    def doc_payout_amount(self):
        amount = 0
        if self.payment_type == self.COD:
            amount = (-1)*(self.effective_price - self.fees)
        elif self.payment_type == self.PREPAID:
            amount = self.fees

        return amount

    @classmethod
    def get_billing_summary(cls, user, req_data):
        month = req_data.get("month")
        year = req_data.get("year")
        payment_type = req_data.get("payment_type")
        out_level = req_data.get("level")
        admin_id = req_data.get("admin_id")
        out_obj = Outstanding.objects.filter(outstanding_level=out_level, net_hos_doc_id=admin_id,
                                             outstanding_month=month, outstanding_year=year).first()
        start_date_time, end_date_time = get_start_end_datetime(month, year)
        if payment_type in [cls.COD, cls.PREPAID]:
            payment_type = [cls.COD, cls.PREPAID]
        elif payment_type in [cls.INSURANCE]:
            payment_type = [cls.INSURANCE]
        queryset = (OpdAppointment.objects.filter(outstanding=out_obj).
                    filter(status=OpdAppointment.COMPLETED,
                           time_slot_start__gte=start_date_time,
                           time_slot_start__lte=end_date_time,
                           payment_type__in=payment_type))
        if payment_type != cls.INSURANCE:
            tcp_condition = Case(When(payment_type=cls.COD, then=F("effective_price")),
                                 When(~Q(payment_type=cls.COD), then=0))
            tdcs_condition = Case(When(payment_type=cls.COD, then=F("fees")),
                                  When(~Q(payment_type=cls.COD), then=0))
            tpf_condition = Case(When(payment_type=cls.PREPAID, then=F("fees")),
                                 When(~Q(payment_type=cls.PREPAID), then=0))
            queryset = queryset.values("doctor", "hospital").annotate(total_cash_payment=Sum(tcp_condition),
                                                                      total_cash_share=Sum(tdcs_condition),
                                                                      total_online_payout=Sum(tpf_condition))

        return queryset

    @classmethod
    def get_billing_appointment(cls, user, req_data):
        month = req_data.get("month")
        year = req_data.get("year")
        payment_type = req_data.get("payment_type")
        out_level = req_data.get("level")
        admin_id = req_data.get("admin_id")

        start_date_time, end_date_time = get_start_end_datetime(month, year)
        query_filter = dict()
        opd_filter_query = dict()
        query_filter['user'] = user
        query_filter['write_permission'] = True
        query_filter['permission_type'] = auth_model.GenericAdmin.BILLINNG
        if out_level == Outstanding.HOSPITAL_NETWORK_LEVEL:
            query_filter["hospital_network"] = admin_id
        elif out_level == Outstanding.HOSPITAL_LEVEL:
            query_filter["hospital"] = admin_id
            if req_data.get("doctor_hospital"):
                opd_filter_query["doctor"] = req_data.get("doctor_hospital")
        elif out_level == Outstanding.DOCTOR_LEVEL:
            query_filter["doctor"] = admin_id
            if req_data.get("doctor_hospital"):
                opd_filter_query["hospital"] = req_data.get("doctor_hospital")

        permission = auth_model.GenericAdmin.objects.filter(**query_filter).exists()

        if payment_type in [cls.COD, cls.PREPAID]:
            payment_type = [cls.COD, cls.PREPAID]
        elif payment_type in [cls.INSURANCE]:
            payment_type = [cls.INSURANCE]

        queryset = None
        if permission:
            out_obj = Outstanding.objects.filter(outstanding_level=out_level, net_hos_doc_id=admin_id,
                                                 outstanding_month=month, outstanding_year=year).first()
            queryset = (OpdAppointment.objects.filter(status=OpdAppointment.COMPLETED,
                                                      time_slot_start__gte=start_date_time,
                                                      time_slot_start__lte=end_date_time,
                                                      payment_type__in=payment_type,
                                                      outstanding=out_obj).filter(**opd_filter_query))

        return queryset

    def get_auto_cancel_delay(self, app_obj):
        delay = settings.AUTO_CANCEL_OPD_DELAY * 60
        to_zone = tz.gettz(settings.TIME_ZONE)
        app_updated_time = app_obj.updated_at.astimezone(to_zone)
        morning_time = "09:00:00"  # In IST
        evening_time = "20:00:00"  # In IST
        present_day_end = custom_form_datetime(evening_time, to_zone)
        next_day_start = custom_form_datetime(morning_time, to_zone, diff_days=1)
        time_diff = next_day_start - app_updated_time

        if present_day_end - timedelta(minutes=settings.AUTO_CANCEL_OPD_DELAY) < app_updated_time < next_day_start:
            return time_diff.seconds
        else:
            return delay

    class Meta:
        db_table = "opd_appointment"


class DoctorLeave(auth_model.TimeStampedModel):
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

    def start_time_in_float(self):
        start_time = self.start_time
        start_time = round(float(start_time.hour) + (float(start_time.minute) * 1 / 60), 2)
        return start_time

    def end_time_in_float(self):
        end_time = self.end_time
        end_time = round(float(end_time.hour) + (float(end_time.minute) * 1 / 60), 2)
        return end_time

    class Meta:
        db_table = "doctor_leave"

    @property
    def interval(self):
        return self.INTERVAL_MAPPING.get((str(self.start_time), str(self.end_time)))


class Prescription(auth_model.TimeStampedModel):
    appointment = models.ForeignKey(OpdAppointment, on_delete=models.CASCADE)
    prescription_details = models.TextField(max_length=300, blank=True, null=True)

    def __str__(self):
        return "{}-{}".format(self.id, self.appointment.id)

    class Meta:
        db_table = "prescription"


class PrescriptionFile(auth_model.TimeStampedModel, auth_model.Document):
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE)
    name = models.FileField(upload_to='prescriptions', blank=False, null=False)

    def __str__(self):
        return "{}-{}".format(self.id, self.prescription.id)

    def send_notification(self, database_instance):
        appointment = self.prescription.appointment
        if not appointment.user:
            return
        if not database_instance:
            notification_models.NotificationAction.trigger(
                instance=appointment,
                user=appointment.user,
                notification_type=notification_models.NotificationAction.PRESCRIPTION_UPLOADED,
            )

    def save(self, *args, **kwargs):
        database_instance = PrescriptionFile.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        self.send_notification(database_instance)

    class Meta:
        db_table = "prescription_file"


class MedicalCondition(auth_model.TimeStampedModel, SearchKey):
    name = models.CharField(max_length=100, verbose_name="Name")
    specialization = models.ManyToManyField(
        GeneralSpecialization,
        through='MedicalConditionSpecialization',
        through_fields=('medical_condition', 'specialization'),
    )

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = "medical_condition"


class MedicalConditionSpecialization(auth_model.TimeStampedModel):
    medical_condition = models.ForeignKey(MedicalCondition, on_delete=models.CASCADE)
    specialization = models.ForeignKey(GeneralSpecialization, on_delete=models.CASCADE)

    def __str__(self):
        return self.medical_condition.name + " " + self.specialization.name

    class Meta:
        db_table = "medical_condition_specialization"


class DoctorSearchResult(auth_model.TimeStampedModel):
    results = JSONField()
    result_count = models.PositiveIntegerField()

    class Meta:
        db_table = "doctor_search_result"


class HealthTip(auth_model.TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name="Name")
    text = models.CharField(max_length=1000)

    class Meta:
        db_table = "health_tip"


class CommonMedicalCondition(auth_model.TimeStampedModel):
    condition = models.OneToOneField(MedicalCondition, related_name="common_condition", on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)
    def __str__(self):
        return "{}".format(self.condition)

    class Meta:
        db_table = "common_medical_condition"


class CommonSpecialization(auth_model.TimeStampedModel):
    specialization = models.OneToOneField(GeneralSpecialization, related_name="common_specialization", on_delete=models.CASCADE)
    icon = models.ImageField(upload_to='doctor/common_specialization_icons', null=True)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "{}".format(self.specialization)

    class Meta:
        db_table = "common_specializations"


class DoctorMapping(auth_model.TimeStampedModel):

    doctor = models.ForeignKey(Doctor, related_name='doctor_mapping', on_delete=models.CASCADE)
    profile_to_be_shown = models.ForeignKey(Doctor, related_name='profile_to_be_shown_mapping', on_delete=models.CASCADE)

    class Meta:
        db_table = "doctor_mapping"


class CompetitorInfo(auth_model.TimeStampedModel):
    PRACTO = 1
    LYBRATE = 2
    NAME_TYPE_CHOICES = (("", "Select"), (PRACTO, 'Practo'), (LYBRATE, "Lybrate"),)
    name = models.PositiveSmallIntegerField(blank=True, null=True,
                                            choices=NAME_TYPE_CHOICES)

    doctor = models.ForeignKey(Doctor, related_name="competitor_doctor", on_delete=models.CASCADE, null=True,
                               blank=True)
    hospital = models.ForeignKey(Hospital, related_name="competitor_hospital", on_delete=models.CASCADE, null=True,
                                 blank=True)
    hospital_name = models.CharField(max_length=200)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    url = models.URLField(null=True)
    processed_url = models.URLField(null=True)

    #
    # url = url.replace("http://", "")

    class Meta:
        db_table = "competitor_info"
        #unique_together = ('name', 'hospital_name', 'doctor')

    def save(self, *args, **kwargs):
        url = self.url
        if url:
            if ('//') in url:
                url = url.split('//')[1]
            if ('?') in url:
                url = url.split('?')[0]
            self.processed_url = url

        super().save(*args, **kwargs)


class CompetitorHit(models.Model):
    NAME_TYPE_CHOICES = CompetitorInfo.NAME_TYPE_CHOICES
    doctor = models.ForeignKey(Doctor, related_name="competitor_doctor_hits", on_delete=models.CASCADE)
    name = models.PositiveSmallIntegerField(choices=NAME_TYPE_CHOICES)
    hits = models.BigIntegerField()

    class Meta:
        db_table = "competitor_hit"
