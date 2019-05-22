from django.conf import settings
from django.db import models, transaction
from django.contrib.gis.db import models as geo_models
from django.db.models import Q, Prefetch
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import JSONField
from django.utils import timezone
from PIL import Image as Img
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import math
import os
import hashlib
import random, string
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.utils.functional import cached_property
from datetime import date, datetime
from safedelete import SOFT_DELETE
from safedelete.models import SafeDeleteModel
import reversion

import requests
import json
from rest_framework import status
from collections import OrderedDict
from django.utils.text import slugify


class Image(models.Model):
    # name = models.ImageField(height_field='height', width_field='width')
    width = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)
    height = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_name = self.name

    def use_image_name(self):
        return False

    def auto_generate_thumbnails(self):
        return False

    def crop_existing_image(self, width, height):
        if not hasattr(self, 'name'):
            return
        if not self.name:
            return
        if not hasattr(self, 'get_image_name'):
            return
        # from django.core.files.storage import get_storage_class
        # default_storage_class = get_storage_class()
        # storage_instance = default_storage_class()

        path = "{}".format(self.get_image_name())
        # if storage_instance.exists(path):
        #     return
        if self.name.closed:
            self.name.open()
        with Img.open(self.name) as img:
            img = img.copy()
            img.thumbnail(tuple([width, height]), Img.LANCZOS)
            if img.mode != 'RGB':
                img = img.convert('RGB')
            new_image_io = BytesIO()
            img.save(new_image_io, format='JPEG')
            in_memory_file = InMemoryUploadedFile(new_image_io, None, path + ".jpg", 'image/jpeg', new_image_io.tell(),
                                                  None)
            self.cropped_image = in_memory_file
            self.save()

    def create_thumbnail(self):
        if not hasattr(self, 'cropped_image'):
            return
        if not (hasattr(self, 'auto_generate_thumbnails') and self.auto_generate_thumbnails()):
            return
        if self.cropped_image:
            return
        from ondoc.doctor.models import DoctorImage
        size = DoctorImage.image_sizes[0]
        width = size[0]
        height = size[1]
        self.crop_existing_image(width, height)

    def get_thumbnail_path(self, path, prefix):
        first, last = path.rsplit('/', 1)
        return "{}/{}/{}".format(first, prefix, last)


    def has_image_changed(self):
        if not self.pk:
            return True
        old_value = self.__class__._default_manager.filter(pk=self.pk).values('name').get()['name']
        return not getattr(self, 'name').name == old_value

    def save(self, *args, **kwargs):

        if not self.has_image_changed():
            return super().save(*args, **kwargs)

        if self.name:
            max_allowed = 1000
            img = Img.open(self.name)
            size = img.size
            #new_size = ()

            if max(size) > max_allowed:
                size = tuple(math.floor(ti / (max(size) / max_allowed)) for ti in size)

            img = img.resize(size, Img.ANTIALIAS)

            if img.mode != 'RGB':
                img = img.convert('RGB')

            md5_hash = hashlib.md5(img.tobytes()).hexdigest()
            if hasattr(self, 'use_image_name') and self.use_image_name() and hasattr(self, 'get_image_name'):
                md5_hash = self.get_image_name()
            # if img.multiple_chunks():
            #    for chunk in img.chunks():
            #       hash.update(chunk)
            # else:    
            #   hash.update(img.read())

            new_image_io = BytesIO()
            img.save(new_image_io, format='JPEG')
            # im = img.save(md5_hash+'.jpg')
            self.name = InMemoryUploadedFile(new_image_io, None, md5_hash+".jpg", 'image/jpeg',
                                  new_image_io.tell(), None)

            # self.name = InMemoryUploadedFile(output, 'ImageField', md5_hash+".jpg", 'image/jpeg',
            #                                     output.len, None)
            # self.name = img
            # img.thumbnail((self.image.width/1.5,self.image.height/1.5), Img.ANTIALIAS)
            # output = StringIO.StringIO()
            # img.save(output, format='JPEG', quality=70)
            # output.seek(0)
            # self.image= InMemoryUploadedFile(output,'ImageField', "%s.jpg" %self.image.name.split('.')[0], 'image/jpeg', output.len, None)
        super().save(*args, **kwargs)


    class Meta:
        abstract = True

class Document(models.Model):

    def use_image_name(self):
        return False

    def get_thumbnail_path(self, path, prefix):
        first, last = path.rsplit('/', 1)
        return "{}/{}/{}".format(first,prefix,last)

    def has_changed(self):
        if not self.pk:
            return True
        old_value = self.__class__._default_manager.filter(pk=self.pk).values('name').get()['name']
        return not getattr(self, 'name').name == old_value

    def save(self, *args, **kwargs):
        if not self.has_changed():
            return super().save(*args, **kwargs)

        if self.name:
            max_allowed = 1000
            img = None

            try:
                img = Img.open(self.name)
            except IOError:
                pass

            if img:
                size = img.size
                #new_size = ()

                if max(size)>max_allowed:
                    size = tuple(math.floor(ti/(max(size)/max_allowed)) for ti in size)

                img = img.resize(size, Img.ANTIALIAS)

                if img.mode != 'RGB':
                    img = img.convert('RGB')

                md5_hash = hashlib.md5(img.tobytes()).hexdigest()
                if hasattr(self, 'use_image_name') and self.use_image_name() and hasattr(self, 'get_image_name'):
                    md5_hash = self.get_image_name()
                #if img.multiple_chunks():
                #    for chunk in img.chunks():
                #       hash.update(chunk)
                # else:    
                #   hash.update(img.read())

                new_image_io = BytesIO()
                img.save(new_image_io, format='JPEG')


            #im = img.save(md5_hash+'.jpg')
                self.name = InMemoryUploadedFile(new_image_io, None, md5_hash+".jpg", 'image/jpeg',
                                  new_image_io.tell(), None)
            else:                
                hash = None
                md5 = hashlib.md5()
                bytes_io = self.name.file.read()
                md5.update(bytes_io)
                hash = md5.hexdigest()
                name, extension = os.path.splitext(self.name.name)
                filename = hash+extension
                self.name.file.seek(0,2)
                self.name = InMemoryUploadedFile(self.name.file, None, filename, None,
                    self.name.file.tell(), None)

                # with self.name.file as f:
                #     for chunk in f.chunks(8192):
                #         md5.update(chunk)
                #     hash = md5.hexdigest()
                print(' not image ')

            # self.name = InMemoryUploadedFile(output, 'ImageField', md5_hash+".jpg", 'image/jpeg',
            #                                     output.len, None)

            # self.name = img
            # img.thumbnail((self.image.width/1.5,self.image.height/1.5), Img.ANTIALIAS)
            # output = StringIO.StringIO()
            # img.save(output, format='JPEG', quality=70)
            # output.seek(0)
            # self.image= InMemoryUploadedFile(output,'ImageField', "%s.jpg" %self.image.name.split('.')[0], 'image/jpeg', output.len, None)
        super().save(*args, **kwargs)


    class Meta:
        abstract = True


class QCModel(models.Model):
    IN_PROGRESS = 1
    SUBMITTED_FOR_QC = 2
    QC_APPROVED = 3
    REOPENED = 4
    DATA_STATUS_CHOICES = [(IN_PROGRESS, "In Progress"), (SUBMITTED_FOR_QC, "Submitted For QC Check"), (QC_APPROVED, "QC approved"), (REOPENED, "Reopened")]
    data_status = models.PositiveSmallIntegerField(default=1, editable=False, choices=DATA_STATUS_CHOICES)
    qc_approved_at = models.DateTimeField(null=True, blank=True)
    history = GenericRelation('authentication.StatusHistory')

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk is not None:
            orig = self.__class__.objects.get(pk=self.pk)
            if orig.data_status != self.data_status:
                StatusHistory.create(content_object=self)

        super().save(*args, **kwargs)


class CustomUserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""
    use_in_migrations = True

    def get_queryset(self):
        return super().get_queryset().prefetch_related('staffprofile')

    def _create_user(self, email, password, **extra_fields):
        """Create and save a User with the given email and password."""
        if not email:
            raise ValueError('The given email must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, user_type=1, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Create and save a regular User with the given email and password."""
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Create and save a SuperUser with the given email and password."""
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    STAFF = 1
    DOCTOR = 2
    CONSUMER = 3
    USER_TYPE_CHOICES = ((STAFF, 'staff'), (DOCTOR, 'doctor'), (CONSUMER, 'user'))
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone_number']

    # EMAIL_FIELD = 'email'
    objects = CustomUserManager()
    username = None
    phone_number = models.CharField(max_length=10, blank=False, null=True, default=None)
    email = models.EmailField(max_length=100, blank=False, null=True, default=None)
    user_type = models.PositiveSmallIntegerField(choices=USER_TYPE_CHOICES)
    is_phone_number_verified = models.BooleanField(verbose_name= 'Phone Number Verified', default=False)
    is_active = models.BooleanField(verbose_name= 'Active', default=True, help_text= 'Designates whether this user should be treated as active.')

    is_staff = models.BooleanField(verbose_name= 'Staff Status', default=False, help_text= 'Designates whether the user can log into this admin site.')
    date_joined = models.DateTimeField(auto_now_add=True)
    auto_created = models.BooleanField(default=False)

    def __hash__(self):
        return self.id

    def __eq__(self, other):
        if self and other and self.id and other.id:
            return self.id == other.id
        return False

    def __str__(self):
        name = self.phone_number
        try:
            name = self.staffprofile.name
        except:
            pass
        return name
        # if self.user_type==1 and hasattr(self, 'staffprofile'):
        #     return self.staffprofile.name
        # return str(self.phone_number)

    # @property
    @cached_property
    def active_insurance(self):
        active_insurance = self.purchased_insurance.filter().order_by('id').last()
        return active_insurance if active_insurance and active_insurance.is_valid() else None

    def get_phone_number_for_communication(self):
        from ondoc.communications.models import unique_phone_numbers
        receivers = []
        default_user_profile = self.profiles.filter(is_default_user=True).first()
        if default_user_profile and default_user_profile.phone_number:
            receivers.append({'user': self, 'phone_number': default_user_profile.phone_number})
        receivers.append({'user': self, 'phone_number': self.phone_number})
        receivers = unique_phone_numbers(receivers)
        return receivers

    def get_full_name(self):
        return self.full_name

    @cached_property
    def full_name(self):
        profile = self.get_default_profile()
        if profile and profile.name:
            return profile.name
        return ''

    @cached_property
    def get_default_email(self):
        profile = self.get_default_profile()
        if profile and profile.email:
            return profile.email
        return ''

    # @cached_property
    # def get_default_profile(self):
    #     user_profile = self.profiles.all().filter(is_default_user=True).first()
    #     if user_profile:
    #         return user_profile
    #     return ''
        
        # self.profiles.filter(is_default=True).first()

    @cached_property
    def my_groups(self):
        return self.groups.all()

    def is_member_of(self, group_name):
        for group in self.my_groups:
            if group.name == group_name:
                return True

        return False

    def get_unrated_opd_appointment(self):
        from ondoc.doctor import models as doc_models
        opd_app = None
        opd_all = self.appointments.all().order_by('-id')
        for opd in opd_all:
            if opd.status == doc_models.OpdAppointment.COMPLETED:
                if opd.is_rated == False and opd.rating_declined == False:
                    opd_app = opd
                break
        return opd_app

    def get_unrated_lab_appointment(self):
        from ondoc.diagnostic import models as lab_models
        lab_app = None
        lab_all = self.lab_appointments.all().order_by('-id')
        for lab in lab_all:
            if lab.status == lab_models.LabAppointment.COMPLETED:
                if lab.is_rated == False and lab.rating_declined == False:
                    lab_app = lab
                break
        return lab_app

    def save(self, *args, **kwargs):
        if self.email:
            self.email = self.email.lower()
        return super().save(*args, **kwargs)

    def get_default_profile(self):
        default_profile = self.profiles.filter(is_default_user=True)
        if default_profile.exists():
            return default_profile.first()
        else:
            return None

    class Meta:
        unique_together = (("email", "user_type"), ("phone_number","user_type"))
        db_table = "auth_user"


class StaffProfile(models.Model):
    name = models.CharField(max_length=100, blank=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    #user = models.OneToOneField(User, on_delete=models.CASCADE)
    employee_id = models.CharField(max_length=10, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "staff_profile"


class PhoneVerifications(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    phone_number = models.CharField(max_length=10)
    code = models.CharField(max_length=10)

    class Meta:
        db_table = "phone_verification"


class TimeStampedModel(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class SoftDeleteModel(models.Model):
    deleted_at = models.DateTimeField(blank=True, null=True)

    def mark_delete(self):
        self.deleted_at = datetime.now()
        self.save()

    class Meta:
        abstract = True


class CreatedByModel(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, editable=False, on_delete=models.SET_NULL)

    class Meta:
        abstract = True


@reversion.register()
class UserProfile(TimeStampedModel):
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE,"Male"), (FEMALE,"Female"), (OTHER,"Other")]
    user = models.ForeignKey(User, related_name="profiles", on_delete=models.SET_NULL, null=True)
    name = models.CharField(max_length=100, blank=False, null=True, default=None)
    email = models.CharField(max_length=256, blank=False, null=True, default=None)
    gender = models.CharField(max_length=2, default=None, blank=True, null=True, choices=GENDER_CHOICES)
    phone_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    is_otp_verified = models.BooleanField(default=False)
    is_default_user = models.BooleanField(default=False)
    dob = models.DateField(blank=True, null=True)
    
    profile_image = models.ImageField(upload_to='users/images', height_field=None, width_field=None, blank=True, null=True)
    whatsapp_optin = models.NullBooleanField(default=None) # optin check of the whatsapp
    whatsapp_is_declined = models.BooleanField(default=False) # flag to whether show whatsapp pop up or not.

    def __str__(self):
        return "{}-{}".format(self.name, self.id)

    def get_thumbnail(self):
        if self.profile_image:
            return self.profile_image.url
        return None
        # return static('doctor_images/no_image.png')

    def has_image_changed(self):
        if not self.pk:
            return True
        old_value = self.__class__._default_manager.filter(pk=self.pk).values('profile_image').get()['profile_image']
        return not getattr(self, 'profile_image').name == old_value

    def get_age(self):
        user_age = None
        if self.dob:
            today = date.today()
            user_age = today.year - self.dob.year - ((today.month, today.day) < (self.dob.month, self.dob.day))
        return user_age

    def save(self, *args, **kwargs):
        if not self.has_image_changed():
            return super().save(*args, **kwargs)

        if self.profile_image:
            max_allowed = 1000
            img = Img.open(self.profile_image)
            size = img.size
            if max(size)>max_allowed:
                size = tuple(math.floor(ti/(max(size)/max_allowed)) for ti in size)

            img = img.resize(size, Img.ANTIALIAS)

            if img.mode != 'RGB':
                img = img.convert('RGB')

            md5_hash = hashlib.md5(img.tobytes()).hexdigest()
            new_image_io = BytesIO()
            img.save(new_image_io, format='JPEG')
            self.profile_image = InMemoryUploadedFile(new_image_io, None, md5_hash + ".jpg", 'image/jpeg',
                                                      new_image_io.tell(), None)
        super().save(*args, **kwargs)

    class Meta:
        db_table = "user_profile"


class OtpVerifications(TimeStampedModel):
    OTP_EXPIRY_TIME = 120  # In minutes
    phone_number = models.CharField(max_length=10)
    code = models.CharField(max_length=10)
    country_code = models.CharField(max_length=10)
    is_expired = models.BooleanField(default=False)
    otp_request_source = models.CharField(null=True, max_length=200, blank=True)
    via_whatsapp = models.NullBooleanField(null=True)
    via_sms = models.NullBooleanField(null=True)

    def __str__(self):
        return self.phone_number

    class Meta:
        db_table = "otp_verification"

    @staticmethod
    def get_otp_message(platform, user_type, is_doc=False, version=None):
        from packaging.version import parse
        result = "OTP for login is {}.\nDon't share this code with others."
        if platform == "android" and version:
            if (user_type == 'doctor' or is_doc) and parse(version) > parse("2.100.4"):
                result = "<#>\n" + result + "\n" + settings.PROVIDER_ANDROID_MESSAGE_HASH
            elif parse(version) > parse("1.1"):
                result = "<#>\n" + result + "\n" + settings.CONSUMER_ANDROID_MESSAGE_HASH
        return result


class NotificationEndpoint(TimeStampedModel):
    user = models.ForeignKey(User, related_name='notification_endpoints', on_delete=models.CASCADE,
                             blank=True, null=True)
    device_id = models.TextField(blank=True, null=True)
    platform = models.TextField(blank=True, null=True)
    app_name = models.TextField(blank=True, null=True)
    app_version = models.TextField(blank=True, null=True)
    token = models.TextField(unique=True)

    class Meta:
        db_table = 'notification_endpoint'

    def __str__(self):
        return "{}-{}".format(self.user.phone_number, self.token)


class Notification(TimeStampedModel):
    ACCEPTED = 1
    REJECTED = 2
    TYPE_CHOICES = ((ACCEPTED, 'Accepted'), (REJECTED, 'Rejected'), )
    user = models.ForeignKey(User, related_name='notifications', on_delete=models.CASCADE)
    content = JSONField()
    type = models.PositiveIntegerField(choices=TYPE_CHOICES)
    viewed_at = models.DateTimeField(blank=True, null=True)
    read_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'notification'

    def __str__(self):
        return "{}-{}".format(self.user.phone_number, self.id)


class Address(TimeStampedModel):
    HOME_ADDRESS = "home"
    WORK_ADDRESS = "office"
    OTHER = "other"
    TYPE_CHOICES = (
        (HOME_ADDRESS, 'Home Address'),
        (WORK_ADDRESS, 'Work Address'),
        (OTHER, 'Other'),
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    profile = models.ForeignKey(UserProfile, null=True, blank=True, on_delete=models.CASCADE)
    locality_place_id = models.CharField(null=True, blank=True, max_length=400)
    locality_location = geo_models.PointField(geography=True, srid=4326, blank=True, null=True)
    locality = models.CharField(null=True, blank=True, max_length=400)
    landmark_place_id = models.CharField(null=True, blank=True, max_length=400)
    landmark_location = geo_models.PointField(geography=True, srid=4326, blank=True, null=True)
    address = models.TextField(null=True, blank=True)
    land_mark = models.TextField(null=True, blank=True)
    pincode = models.PositiveIntegerField(null=True, blank=True)
    phone_number = models.CharField(null=True, blank=True, max_length=10)
    is_default = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.is_default:
            if not Address.objects.filter(user=self.user).exists():
                self.is_default = True
        super().save(*args, **kwargs)

    class Meta:
        db_table = "address"

    def __str__(self):
        return str(self.user)


class UserPermission(TimeStampedModel):
    APPOINTMENT = 'appointment'
    BILLINNG = 'billing'
    type_choices = ((APPOINTMENT, 'Appointment'), (BILLINNG, 'Billing'), )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hospital_network = models.ForeignKey("doctor.HospitalNetwork", null=True, blank=True,
                                         on_delete=models.CASCADE,
                                         related_name='network_admins')
    hospital = models.ForeignKey("doctor.Hospital", null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='hospital_admins')
    doctor = models.ForeignKey("doctor.Doctor", null=True, blank=True, on_delete=models.CASCADE,
                               related_name='doc_permission')

    permission_type = models.CharField(max_length=20, choices=type_choices, default=APPOINTMENT)

    read_permission = models.BooleanField(default=False)
    write_permission = models.BooleanField(default=False)
    delete_permission = models.BooleanField(default=False)

    class Meta:
        db_table = 'user_permission'

    def __str__(self):
        return str(self.user.email)

    # @classmethod
    # def get_user_admin_obj(cls, user):
    #     from ondoc.payout.models import Outstanding
    #     access_list = []
    #     get_permissions = (GenericAdmin.objects.select_related('hospital_network', 'hospital', 'doctor').
    #                        filter(user_id=user.id, write_permission=True, permission_type=GenericAdmin.BILLINNG))
    #     if get_permissions:
    #         for permission in get_permissions:
    #             if permission.hospital_network_id:
    #                 if permission.hospital_network.is_billing_enabled:
    #                     access_list.append({'admin_obj': permission.hospital_network, 'admin_level': Outstanding.HOSPITAL_NETWORK_LEVEL})
    #             elif permission.hospital_id:
    #                 if permission.hospital.is_billing_enabled:
    #                     access_list.append({'admin_obj': permission.hospital, 'admin_level': Outstanding.HOSPITAL_LEVEL})
    #             else:
    #                 access_list.append({'admin_obj': permission.doctor, 'admin_level': Outstanding.DOCTOR_LEVEL})
    #     return access_list
    #     # TODO PM - Logic to get admin for a particular User
    #
    # @classmethod
    # def get_billable_doctor_hospital(cls, user):
    #     permission_data = (UserPermission.objects.
    #                        filter(user=user, permission_type=cls.BILLINNG, write_permission=True).
    #                        values('hospital_network', 'hospital', 'hospital__assoc_doctors',
    #                               'hospital_network__assoc_hospitals__assoc_doctors',
    #                               'hospital_network__assoc_hospitals'))
    #     doc_hospital = list()
    #     for data in permission_data:
    #         if data.get("hospital_network"):
    #             doc_hospital.append({
    #                 "doctor": data.get("hospital_network__assoc_hospitals__assoc_doctors"),
    #                 "hospital": data.get("hospital_network__assoc_hospitals")
    #             })
    #         elif data.get("hospital"):
    #             doc_hospital.append({
    #                 "doctor": data.get("hospital__assoc_doctors"),
    #                 "hospital": data.get("hospital")
    #             })
    #     return doc_hospital


class AppointmentTransaction(TimeStampedModel):
    appointment = models.PositiveIntegerField(blank=True, null=True)
    transaction_time = models.DateTimeField()
    transaction_status = models.CharField(max_length=100)
    status_code = models.PositiveIntegerField()
    transaction_details = JSONField()

    class Meta:
        db_table = "appointment_transaction"

    def __str__(self):
        return "{}-{}".format(self.id, self.appointment)


class LabUserPermission(TimeStampedModel):
    APPOINTMENT = 'appointment'
    BILLINNG = 'billing'
    type_choices = ((APPOINTMENT, 'Appointment'), (BILLINNG, 'Billing'), )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    lab_network = models.ForeignKey("diagnostic.LabNetwork", null=True, blank=True, on_delete=models.CASCADE,
                                         related_name='lab_network_admins')
    lab = models.ForeignKey("diagnostic.Lab", null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='lab_admins')
    permission_type = models.CharField(max_length=20, choices=type_choices, default=APPOINTMENT)

    read_permission = models.BooleanField(default=False)
    write_permission = models.BooleanField(default=False)
    delete_permission = models.BooleanField(default=False)

    class Meta:
        db_table = 'lab_user_permission'

    def __str__(self):
        return str(self.user.email)


    @classmethod
    def get_lab_user_admin_obj(cls, user):
        from ondoc.payout.models import Outstanding
        access_list = []
        get_permissions = LabUserPermission.objects.select_related('lab_network', 'lab').filter(user_id=user.id,
                                                        write_permission=True, permission_type=UserPermission.BILLINNG)
        if get_permissions:
            for permission in get_permissions:
                if permission.lab_network_id:
                    if permission.lab_network.is_billing_enabled:
                        access_list.append({'admin_id': permission.lab_network_id, 'admin_level': Outstanding.LAB_NETWORK_LEVEL})
                elif permission.lab_id:
                    if permission.lab.is_billing_enabled:
                        access_list.append({'admin_id': permission.lab_id, 'admin_level': Outstanding.LAB_LEVEL})
        return access_list
        # TODO PM - Logic to get admin for a particular User


class GenericLabAdmin(TimeStampedModel, CreatedByModel):
    APPOINTMENT = 1
    BILLING = 2
    ALL = 3
    CRM = 1
    APP = 2
    source_choices = ((CRM, 'CRM'), (APP, 'App'),)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manages_lab', null=True, blank=True)
    phone_number = models.CharField(max_length=10)
    type_choices = ((APPOINTMENT, 'Appointment'), (BILLING, 'Billing'),)
    lab_network = models.ForeignKey("diagnostic.LabNetwork", null=True, blank=True,
                                    on_delete=models.CASCADE,
                                    related_name='manageable_lab_network_admins')
    lab = models.ForeignKey("diagnostic.Lab", null=True, blank=True, on_delete=models.CASCADE,
                            related_name='manageable_lab_admins')
    permission_type = models.PositiveSmallIntegerField(choices=type_choices, default=APPOINTMENT)
    is_disabled = models.BooleanField(default=False)
    super_user_permission = models.BooleanField(default=False)
    read_permission = models.BooleanField(default=False)
    write_permission = models.BooleanField(default=False)
    name = models.CharField(max_length=24, blank=True, null=True)
    source_type = models.PositiveSmallIntegerField(choices=source_choices, default=CRM)

    class Meta:
        db_table = 'generic_lab_admin'

    def save(self, *args, **kwargs):
        user = User.objects.filter(phone_number=self.phone_number, user_type=User.DOCTOR).first()
        if user is not None:
            self.user = user
        super(GenericLabAdmin, self).save(*args, **kwargs)

    def __str__(self):
        return "{}".format(self.phone_number)

    @classmethod
    def update_user_lab_admin(cls, phone_number):
        user = User.objects.filter(phone_number=phone_number, user_type=User.DOCTOR).first()
        if user:
            admin = GenericLabAdmin.objects.filter(phone_number=phone_number, user__isnull=True)
            if admin.exists():
                admin.update(user=user)

    @classmethod
    def get_user_admin_obj(cls, user):
        from ondoc.payout.models import Outstanding
        access_list = []
        permissions = (cls.objects.select_related('lab_network', 'lab').
                           filter(Q(user_id=user.id,
                                    permission_type=cls.BILLINNG,
                                    is_disabled=False,
                                    write_permission=True)
                                  |
                                  Q(user_id=user.id,
                                    super_user_permission=True,
                                    is_disabled=False))
                       )
        if permissions:
            for permission in permissions:
                if permission.lab_network and permission.lab_network.is_billing_enabled:
                    access_list.append({'admin_obj': permission.lab_network,
                                        'admin_level': Outstanding.LAB_NETWORK_LEVEL})
                else:
                    access_list.append({'admin_obj': permission.lab, 'admin_level': Outstanding.LAB_LEVEL})
        return access_list

    @staticmethod
    def create_admin_permissions(lab):
        from ondoc.diagnostic import models as diag_models
        if lab is not  None:
            manager_queryset = diag_models.LabManager.objects.filter(lab=lab, contact_type= diag_models.LabManager.SPOC)
            delete_queryset = GenericLabAdmin.objects.filter(lab=lab, super_user_permission=True)
            if delete_queryset.exists():
                delete_queryset.delete()
            if manager_queryset.exists():
                for mgr in manager_queryset.all():
                    if lab.network and lab.network.manageable_lab_network_admins.exists():
                        is_disabled = True
                    else:
                        is_disabled = False
                    if mgr.number and not mgr.lab.manageable_lab_admins.filter(phone_number=mgr.number).exists():
                        admin_object = GenericLabAdmin(lab=lab,
                                                       phone_number=mgr.number,
                                                       lab_network=None,
                                                       permission_type=GenericLabAdmin.APPOINTMENT,
                                                       is_disabled=is_disabled,
                                                       super_user_permission=True,
                                                       write_permission=True,
                                                       read_permission=True,
                                                       )
                        admin_object.save()

    @classmethod
    def create_permission_object(cls, user, phone_number, lab_network, lab, permission_type,
                                 is_disabled, super_user_permission, write_permission, read_permission):
        return GenericLabAdmin(user=user,
                               phone_number=phone_number,
                               lab_network=lab_network,
                               lab=lab,
                               permission_type=permission_type,
                               is_disabled=is_disabled,
                               super_user_permission=super_user_permission,
                               write_permission=write_permission,
                               read_permission=read_permission
                               )


class GenericAdmin(TimeStampedModel, CreatedByModel):
    APPOINTMENT = 1
    BILLINNG = 2
    ALL = 3
    DOCTOR = 1
    HOSPITAL =2
    OTHER = 3
    CRM = 1
    APP = 2
    entity_choices = ((OTHER, 'Other'), (DOCTOR, 'Doctor'), (HOSPITAL, 'Hospital'),)
    source_choices = ((CRM, 'CRM'), (APP, 'App'),)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='manages', null=True, blank=True)
    phone_number = models.CharField(max_length=10)
    type_choices = ((APPOINTMENT, 'Appointment'), (BILLINNG, 'Billing'),)
    hospital_network = models.ForeignKey("doctor.HospitalNetwork", null=True, blank=True,
                                         on_delete=models.CASCADE,
                                         related_name='manageable_hospital_networks')
    hospital = models.ForeignKey("doctor.Hospital", null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='manageable_hospitals')
    doctor = models.ForeignKey("doctor.Doctor", null=True, blank=True, on_delete=models.CASCADE,
                               related_name='manageable_doctors')
    permission_type = models.PositiveSmallIntegerField(choices=type_choices, default=APPOINTMENT)
    is_doc_admin = models.BooleanField(default=False)
    is_disabled = models.BooleanField(default=False)
    super_user_permission = models.BooleanField(default=False)
    read_permission = models.BooleanField(default=False)
    write_permission = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    source_type = models.PositiveSmallIntegerField(choices=source_choices, default=CRM)
    entity_type = models.PositiveSmallIntegerField(choices=entity_choices, default=OTHER)
    auto_created_from_SPOCs = models.BooleanField(default=False)


    class Meta:
        db_table = 'generic_admin'

    def __str__(self):
        return "{}:{}".format(self.phone_number, self.hospital)

    def save(self, *args, **kwargs):
        self.clean()
        # if not self.created_by:
        #     self.created_by = self.request.user
        # if self.permission_type == self.BILLINNG and self.doctor is not None:
        #     self.hospital = None
        super(GenericAdmin, self).save(*args, **kwargs)
        GenericAdmin.update_user_admin(self.phone_number)

    def delete(self, *args, **kwargs):
        self.clean()
        super(GenericAdmin, self).delete(*args, **kwargs)

    @classmethod
    def update_user_admin(cls, phone_number):
        user = User.objects.filter(phone_number=phone_number, user_type = User.DOCTOR)
        if user.exists():
            admin = GenericAdmin.objects.filter(phone_number=phone_number, user__isnull=True)
            if admin.exists():
                admin.update(user=user.first())

    @classmethod
    def create_admin_permissions(cls, doctor):
        from ondoc.doctor.models import DoctorClinic, DoctorMobile
        doc_user = None
        doc_number = None
        doctor_admins = []
        doc_admin_usr_list = []
        if doctor.user:
            doc_user = doctor.user
        doc_mobile = DoctorMobile.objects.filter(doctor=doctor, is_primary=True)
        if doc_mobile.exists():
            if not doc_user:
                doc_number = doc_mobile.first().number
            else:
                doc_number = doc_user.phone_number
        doc_admin_users = GenericAdmin.objects.select_related('user').filter(Q(doctor=doctor,
                                                                               is_doc_admin=True,
                                                                               permission_type=GenericAdmin.APPOINTMENT),
                                                                             ~Q(phone_number=doc_number)).distinct('user')
        doc_hosp_data = DoctorClinic.objects.select_related('doctor', 'hospital')\
                                      .filter(doctor=doctor)\
                                      .distinct('hospital')

        if doc_admin_users.exists():
            for doc_admin_usr in doc_admin_users.all():
                doc_admin_usr_list.append(doc_admin_usr)
        delete_list = GenericAdmin.objects.filter(doctor=doctor,
                                                  is_doc_admin=True,
                                                  permission_type=GenericAdmin.APPOINTMENT)
        if delete_list.exists():
            delete_list.delete()

        if doc_hosp_data.exists():
            for row in doc_hosp_data.all():
                if not row.hospital.is_appointment_manager:
                    is_disabled = False
                else:
                    is_disabled = True
                if doc_number:
                    doctor_admins.append(cls.create_permission_object(user=doc_user,
                                                                      doctor=doctor,
                                                                      phone_number=doc_number,
                                                                      hospital_network=None,
                                                                      hospital=row.hospital,
                                                                      permission_type=GenericAdmin.APPOINTMENT,
                                                                      is_doc_admin=True,
                                                                      is_disabled=is_disabled,
                                                                      super_user_permission=True,
                                                                      write_permission=True,
                                                                      read_permission=True,
                                                                    ))
                if doc_admin_usr_list:
                    for doc_admin_user in doc_admin_usr_list:
                        duser = None
                        if doc_admin_user.user:
                            duser= doc_admin_user.user
                            dphone = doc_admin_user.user.phone_number
                        else:
                            dphone = doc_admin_user.phone_number
                        doctor_admins.append(cls.create_permission_object(user=duser,
                                                                          doctor=doctor,
                                                                          phone_number=dphone,
                                                                          hospital_network=None,
                                                                          hospital=row.hospital,
                                                                          permission_type=GenericAdmin.APPOINTMENT,
                                                                          is_doc_admin=True,
                                                                          is_disabled=is_disabled,
                                                                          super_user_permission=False,
                                                                          write_permission=doc_admin_user.write_permission,
                                                                          read_permission=doc_admin_user.read_permission))

            if doctor_admins:
                GenericAdmin.objects.bulk_create(doctor_admins)

    @classmethod
    def create_admin_billing_permissions(cls, doctor):
        from ondoc.doctor.models import DoctorMobile
        doc_user = None
        doc_number = None
        if doctor.user:
            doc_user = doctor.user
        doc_mobile = DoctorMobile.objects.filter(doctor=doctor, is_primary=True)
        if doc_mobile.exists():
            if not doc_user:
                doc_number = doc_mobile.first().number
            else:
                doc_number = doc_user.phone_number

        billing_perm = GenericAdmin.objects.filter(doctor=doctor,
                                                   phone_number=doc_number,
                                                   permission_type=GenericAdmin.BILLINNG)
        if not billing_perm.exists():
            if doc_number:
                GenericAdmin.objects.create(user=doc_user,
                                            doctor=doctor,
                                            phone_number=doc_number,
                                            hospital_network=None,
                                            hospital=None,
                                            permission_type=GenericAdmin.BILLINNG,
                                            is_doc_admin=False,
                                            is_disabled=False,
                                            super_user_permission=True,
                                            write_permission=True,
                                            read_permission=True)

    @classmethod
    def create_hospital_spoc_admin(cls, hospital):
        spoc_objs = (
            SPOCDetails.objects.filter(object_id=hospital.id, content_type=ContentType.objects.get_for_model(hospital),
                                       std_code__isnull=True))
        spoc_numbers = list()
        admin_objs = list()

        for obj in spoc_objs:
            spoc_numbers.append(obj.number)
            admin_objs.extend(obj.get_admin_objs())

        admin_to_be_deleted = cls.objects.filter(~Q(phone_number__in=spoc_numbers), Q(hospital=hospital))
        if admin_to_be_deleted:
            admin_to_be_deleted.delete()

        if admin_objs:
            cls.objects.bulk_create(admin_objs)

    @classmethod
    def create_permission_object(cls, user, doctor, name, phone_number, hospital, permission_type, is_disabled,
                             super_user_permission, write_permission, created_by, source_type, entity_type):
        return GenericAdmin(user=user,
                            doctor=doctor,
                            name=name,
                            phone_number=phone_number,
                            hospital_network=None,
                            hospital=hospital,
                            permission_type=permission_type,
                            is_doc_admin=False,
                            is_disabled=is_disabled,
                            super_user_permission=super_user_permission,
                            write_permission=write_permission,
                            read_permission=True,
                            created_by=created_by,
                            source_type=source_type,
                            entity_type=entity_type
                            )

    @classmethod
    def get_user_admin_obj(cls, user):
        from ondoc.payout.models import Outstanding
        access_list = []
        get_permissions = (GenericAdmin.objects.select_related('hospital_network', 'hospital', 'doctor')
                           .filter(Q(user_id=user.id,
                                     write_permission=True,
                                     permission_type=GenericAdmin.BILLINNG,
                                     is_disabled=False)
                                   |
                                   Q(user_id=user.id,
                                     super_user_permission=True,
                                     is_disabled=False)
                                   )
                           )
        if get_permissions:
            for permission in get_permissions:
                if permission.hospital_network_id:
                    if permission.hospital_network.is_billing_enabled:
                        access_list.append({'admin_obj': permission.hospital_network,
                                            'admin_level': Outstanding.HOSPITAL_NETWORK_LEVEL})
                elif permission.hospital_id:
                    if permission.hospital.is_billing_enabled:
                        access_list.append(
                            {'admin_obj': permission.hospital, 'admin_level': Outstanding.HOSPITAL_LEVEL})
                else:
                    access_list.append({'admin_obj': permission.doctor, 'admin_level': Outstanding.DOCTOR_LEVEL})
        return access_list
        # TODO PM - Logic to get admin for a particular User

    @classmethod
    def get_billable_doctor_hospital(cls, user):
        permission_data = (GenericAdmin.objects.
                           filter(user=user, permission_type=cls.BILLINNG, write_permission=True).
                           values('hospital_network', 'hospital', 'hospital__assoc_doctors',
                                  'hospital_network__assoc_hospitals__assoc_doctors',
                                  'hospital_network__assoc_hospitals'))
        doc_hospital = list()
        for data in permission_data:
            if data.get("hospital_network"):
                doc_hospital.append({
                    "doctor": data.get("hospital_network__assoc_hospitals__assoc_doctors"),
                    "hospital": data.get("hospital_network__assoc_hospitals")
                })
            elif data.get("hospital"):
                doc_hospital.append({
                    "doctor": data.get("hospital__assoc_doctors"),
                    "hospital": data.get("hospital")
                })
        return doc_hospital

    @classmethod
    def get_appointment_admins(cls, appoinment):
        from ondoc.api.v1.utils import GenericAdminEntity
        if not appoinment:
            return []
        admins = GenericAdmin.objects.filter(
                Q(is_disabled=False),
                (Q(
                    (Q(doctor=appoinment.doctor,
                       hospital=appoinment.hospital)
                     |
                     Q(doctor__isnull=True,
                       hospital=appoinment.hospital)
                     |
                     Q(hospital__isnull=True,
                       doctor=appoinment.doctor)
                     )
                 )|
                Q(
                    Q(super_user_permission=True,
                      entity_type=GenericAdminEntity.DOCTOR,
                      doctor=appoinment.doctor)
                    |
                    Q(super_user_permission=True,
                      entity_type=GenericAdminEntity.HOSPITAL,
                      hospital=appoinment.hospital)
                ))
        ).distinct('user')
        admin_users = []
        for admin in admins:
            if admin.user:
                admin_users.append(admin.user)
        return admin_users

    @staticmethod
    def get_manageable_hospitals(user):
        manageable_hosp_list = GenericAdmin.objects.filter(Q(is_disabled=False, user=user),
                                                           (Q(permission_type=GenericAdmin.APPOINTMENT)
                                                            |
                                                            Q(super_user_permission=True))) \
                                                   .values_list('hospital', flat=True)
        return list(manageable_hosp_list)


class BillingAccount(models.Model):
    SAVINGS = 1
    CURRENT = 2
    merchant_id = models.BigIntegerField(null=True, default=None, blank=True)
    account_number = models.CharField(max_length=50, null=True, default=None, blank=True)
    ifsc_code = models.CharField(max_length=128, null=True)
    pan_number = models.CharField(max_length=20, null=True)
    TYPE_CHOICES = (
        (SAVINGS, 'Savings'),
        (CURRENT, 'Current'),
    )
    pan_copy = models.ImageField('Pan Card Image',upload_to='billing/documents', null=True, blank=True)
    account_copy = models.ImageField('Account/Cheque Image',upload_to='billing/documents', null=True, blank=True)
    type = models.PositiveIntegerField(choices=TYPE_CHOICES, null=True)
    enabled = models.BooleanField(default=False)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'billing_account'

    def save(self, *args, **kwargs):
        if not self.merchant_id:
            self.merchant_id = self.get_merchant_id()
        super(BillingAccount, self).save(*args, **kwargs)

    def get_merchant_id(self):
        from ondoc.api.v1.utils import RawSql
        merchant_id = None
        query = '''select nextval('merchant_id_seq') as inc'''
        seq = RawSql(query,[]).fetch_all()
        if seq:
            merchant_id = seq[0]['inc'] if seq[0]['inc'] else None
        return merchant_id

    def __str__(self):
        if self.merchant_id and self.content_type:
            return '{}-{}'.format(self.content_type, self.merchant_id)
        else:
            return self.id


class UserSecretKey(TimeStampedModel):

    key = models.CharField(max_length=40, unique=True)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, related_name='secret_key',
        on_delete=models.CASCADE, verbose_name="User"
    )

    class Meta:
        db_table = "user_secret_key"

    def __str__(self):
        return '{}-{}'.format(self.user, self.key)

    def save(self, *args, **kwargs):
        if not self.key:
            self.key = self.generate_key()
        return super(UserSecretKey, self).save(*args, **kwargs)

    def generate_key(self):
        import binascii
        return binascii.hexlify(os.urandom(20)).decode()


class AgentTokenManager(models.Manager):
    def create_token(self, user):
        expiry_time = timezone.now() + timezone.timedelta(hours=AgentToken.expiry_duration)
        token = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(10)])
        return super().create(user=user, token=token, expiry_time=expiry_time)


class AgentToken(TimeStampedModel):
    expiry_duration = 24  # IN HOURS
    user = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    token = models.CharField(max_length=100)
    is_consumed = models.BooleanField(default=False)
    expiry_time = models.DateTimeField()
    order_id = models.IntegerField(blank=True, null=True)

    objects = AgentTokenManager()  # The default manager.

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = 'agent_token'


class SPOCDetails(TimeStampedModel):
    OTHER = 1
    SPOC = 2
    MANAGER = 3
    OWNER = 4
    name = models.CharField(max_length=200)
    std_code = models.IntegerField(blank=True, null=True)
    number = models.BigIntegerField(blank=True, null=True)
    email = models.EmailField(max_length=100, blank=True, null=True)
    details = models.CharField(max_length=200, blank=True)
    CONTACT_TYPE_CHOICES = [(OTHER, "Other"), (SPOC, "Single Point of Contact"), (MANAGER, "Manager"), (OWNER, "Owner")]
    contact_type = models.PositiveSmallIntegerField(
        choices=CONTACT_TYPE_CHOICES)
    source = models.CharField(max_length=2000, blank=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    def get_admin_objs(self):
        from ondoc.doctor.models import Hospital, HospitalNetwork
        from ondoc.diagnostic.models import LabNetwork
        if self.std_code is None:
            if isinstance(self.content_object, Hospital):
                return self.get_hospital_admin_objs()
            elif isinstance(self.content_object, HospitalNetwork):
                return self.get_hospital_network_admin_objs()
            elif isinstance(self.content_object, LabNetwork):
                return self.get_lab_network_admin_objs()
        else:
            return []

    def app_admin_obj_hospitals(self, perm_dict, hospital_obj, hospital_network_obj, user):
        admin_objs = list()
        if perm_dict.get("is_app_admin"):
            admin_objs.append(GenericAdmin.create_permission_object(user=user,
                                                                    doctor=None,
                                                                    phone_number=self.number,
                                                                    hospital_network=hospital_network_obj,
                                                                    hospital=hospital_obj,
                                                                    permission_type=GenericAdmin.APPOINTMENT,
                                                                    is_doc_admin=False,
                                                                    is_disabled=False,
                                                                    super_user_permission=False,
                                                                    write_permission=perm_dict.get(
                                                                        "app_write_permission"),
                                                                    read_permission=perm_dict.get(
                                                                        "app_read_permission"), ))
        return admin_objs

    def bill_admin_obj_hospitals(self, perm_dict, hospital_obj, hospital_network_obj, user):
        admin_objs = list()
        if perm_dict.get("is_billing_admin"):
            admin_objs.append(GenericAdmin.create_permission_object(user=user,
                                                                    doctor=None,
                                                                    phone_number=self.number,
                                                                    hospital_network=hospital_network_obj,
                                                                    hospital=hospital_obj,
                                                                    permission_type=GenericAdmin.BILLINNG,
                                                                    is_doc_admin=False,
                                                                    is_disabled=False,
                                                                    super_user_permission=False,
                                                                    write_permission=perm_dict.get(
                                                                        "bill_write_permission"),
                                                                    read_permission=perm_dict.get(
                                                                        "bill_read_permission"), ))
        return admin_objs

    def app_admin_obj_labs(self, perm_dict, lab_obj, lab_network_obj, user):
        admin_objs = list()
        if perm_dict.get("is_app_admin"):
            admin_objs.append(GenericLabAdmin.create_permission_object(user=user,
                                                                       phone_number=self.number,
                                                                       lab_network=lab_network_obj,
                                                                       lab=lab_obj,
                                                                       permission_type=GenericAdmin.APPOINTMENT,
                                                                       is_disabled=False,
                                                                       super_user_permission=False,
                                                                       write_permission=perm_dict.get(
                                                                           "app_write_permission"),
                                                                       read_permission=perm_dict.get(
                                                                           "app_read_permission"), ))
        return admin_objs

    def bill_admin_obj_labs(self, perm_dict, lab_obj, lab_network_obj, user):
        admin_objs = list()
        if perm_dict.get("is_billing_admin"):
            admin_objs.append(GenericLabAdmin.create_permission_object(user=user,
                                                                       phone_number=self.number,
                                                                       lab_network=lab_network_obj,
                                                                       lab=lab_obj,
                                                                       permission_type=GenericAdmin.BILLINNG,
                                                                       is_disabled=False,
                                                                       super_user_permission=False,
                                                                       write_permission=perm_dict.get(
                                                                           "bill_write_permission"),
                                                                       read_permission=perm_dict.get(
                                                                           "bill_read_permission"), ))
        return admin_objs

    def get_hospital_admin_objs(self):
        perm_dict = self.get_spoc_permissions()
        hospital = self.content_object
        user_obj = User.objects.filter(phone_number=self.number, user_type=User.DOCTOR).first()
        if not user_obj:
            user_obj = None
        admin_objs = list()
        # if hospital.is_billing_enabled:
        #     admin_objs.extend(self.bill_admin_obj_hospitals(perm_dict, hospital, None, user_obj))
        # if hospital.is_appointment_manager:
        #     admin_objs.extend(self.app_admin_obj_hospitals(perm_dict, hospital, None, user_obj))
        admin_objs.extend(self.bill_admin_obj_hospitals(perm_dict, hospital, None, user_obj))
        admin_objs.extend(self.app_admin_obj_hospitals(perm_dict, hospital, None, user_obj))
        return admin_objs

    def get_hospital_network_admin_objs(self):
        perm_dict = self.get_spoc_permissions()
        hospital_network = self.content_object
        user_obj = User.objects.filter(phone_number=self.number).first()
        if not user_obj:
            user_obj = None
        admin_objs = list()
        admin_objs.extend(self.app_admin_obj_hospitals(perm_dict, None, hospital_network, user_obj))
        admin_objs.extend(self.bill_admin_obj_hospitals(perm_dict, None, hospital_network, user_obj))
        return admin_objs

    def get_lab_network_admin_objs(self):
        perm_dict = self.get_spoc_permissions()
        lab_network = self.content_object
        user_obj = User.objects.filter(phone_number=self.number).first()
        if not user_obj:
            user_obj = None
        admin_objs = list()
        admin_objs.extend(self.app_admin_obj_labs(perm_dict, None, lab_network, user_obj))
        admin_objs.extend(self.bill_admin_obj_labs(perm_dict, None, lab_network, user_obj))
        return admin_objs

    def get_spoc_permissions(self):
        is_app_admin = True
        is_billing_admin = False
        app_write_permission = False
        app_read_permission = False
        bill_write_permission = False
        bill_read_permission = False
        if self.contact_type == self.MANAGER:
            app_write_permission = True
            # app_read_permission = True

            is_billing_admin = True
            bill_write_permission = True
            # bill_read_permission = True
        elif self.contact_type == self.SPOC:
            app_write_permission = True
            # app_read_permission = True
        elif self.contact_type == self.OWNER:
            app_write_permission = True
            # app_read_permission = True

            is_billing_admin = True
            bill_write_permission = True
            # bill_read_permission = True
        elif self.contact_type == self.OTHER:
            app_read_permission = True

        return {
            "is_app_admin": is_app_admin,
            "is_billing_admin": is_billing_admin,
            "app_write_permission": app_write_permission,
            "app_read_permission": app_read_permission,
            "bill_write_permission": bill_write_permission,
            "bill_read_permission": bill_read_permission
        }

    # def save(self, *args, **kwargs):
    #     from ondoc.doctor.models import Hospital, HospitalNetwork
    #     from ondoc.diagnostic.models import LabNetwork
    #     prev_instance = SPOCDetails.objects.filter(pk=self.id).first()
    #     if prev_instance:
    #         admin_to_be_deleted = None
    #         if isinstance(self.content_object, Hospital):
    #             admin_to_be_deleted = GenericAdmin.objects.filter(phone_number=prev_instance.number, hospital=self.content_object)
    #         elif isinstance(self.content_object, HospitalNetwork):
    #             admin_to_be_deleted = GenericAdmin.objects.filter(phone_number=prev_instance.number, hospital_network=self.content_object)
    #         elif isinstance(self.content_object, LabNetwork):
    #             admin_to_be_deleted = GenericLabAdmin.objects.filter(phone_number=prev_instance.number, lab_network=self.content_object)
    #         if admin_to_be_deleted:
    #             admin_to_be_deleted.delete()
    #     saved_obj = super(SPOCDetails, self).save(*args, **kwargs)
    #     admin_objs = self.get_admin_objs()
    #     if admin_objs:
    #         if isinstance(self.content_object, Hospital) or isinstance(self.content_object, HospitalNetwork):
    #             GenericAdmin.objects.bulk_create(admin_objs)
    #         elif isinstance(self.content_object, LabNetwork):
    #             GenericLabAdmin.objects.bulk_create(admin_objs)
    #     return saved_obj

    # def delete(self, *args, **kwargs):
    #     from ondoc.doctor.models import Hospital, HospitalNetwork
    #     from ondoc.diagnostic.models import LabNetwork
    #     admin_to_be_deleted = None
    #     if isinstance(self.content_object, Hospital):
    #         admin_to_be_deleted = GenericAdmin.objects.filter(phone_number=self.number,
    #                                                           hospital=self.content_object)
    #     elif isinstance(self.content_object, HospitalNetwork):
    #         admin_to_be_deleted = GenericAdmin.objects.filter(phone_number=self.number,
    #                                                           hospital_network=self.content_object)
    #     elif isinstance(self.content_object, LabNetwork):
    #         admin_to_be_deleted = GenericLabAdmin.objects.filter(phone_number=self.number,
    #                                                              lab_network=self.content_object)
    #     if admin_to_be_deleted:
    #         admin_to_be_deleted.delete()
    #     return super(SPOCDetails, self).delete(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "spoc_details"


class DoctorNumber(TimeStampedModel):
    phone_number = models.CharField(max_length=10)
    doctor = models.ForeignKey("doctor.Doctor", on_delete=models.CASCADE, related_name='doctor_number')
    hospital = models.ForeignKey("doctor.Hospital", on_delete=models.CASCADE, related_name='hospital_doctor_number', null=True)


    class Meta:
        db_table = 'doctor_number'
        unique_together = (("doctor", "hospital"), )

    def __str__(self):
        return '{}-{}'.format(self.phone_number, self.doctor)


class Merchant(TimeStampedModel):

    STATE_ABBREVIATIONS = ('Andhra Pradesh','AP'),('Arunachal Pradesh','AR'),('Assam','AS'),('Bihar','BR'),('Chhattisgarh','CG'),('Goa','GA'),('Gujarat','GJ'),('Haryana','HR'),('Himachal Pradesh','HP'),('Jammu and Kashmir','JK'),('Jharkhand','JH'),('Karnataka','KA'),('Kerala','KL'),('Madhya Pradesh','MP'),('Maharashtra','MH'),('Manipur','MN'),('Meghalaya','ML'),('Mizoram','MZ'),('Nagaland','NL'),('Orissa','OR'),('Punjab','PB'),('Rajasthan','RJ'),('Sikkim','SK'),('Tamil Nadu','TN'),('Tripura','TR'),('Uttarakhand','UK'),('Uttar Pradesh','UP'),('West Bengal','WB'),('Tamil Nadu','TN'),('Tripura','TR'),('Andaman and Nicobar Islands','AN'),('Chandigarh','CH'),('Dadra and Nagar Haveli','DH'),('Daman and Diu','DD'),('Delhi','DL'),('Lakshadweep','LD'),('Pondicherry','PY')

    SAVINGS = 1
    CURRENT = 2

    #pg merchant creation codes
    NOT_INITIATED = 0
    INITIATED = 1
    INPROCESS = 2
    COMPLETE = 3
    FAILURE = 4
    CREATION_STATUS_CHOICES = ((NOT_INITIATED, 'Not Initiated'),
        (INITIATED,'Initiated'),(INPROCESS, 'In Progress'),
         (COMPLETE, 'Complete'), (FAILURE, 'Failure')
        )

    beneficiary_name = models.CharField(max_length=128, null=True)
    account_number = models.CharField(max_length=50, null=True, default=None, blank=True)
    ifsc_code = models.CharField(max_length=128, null=True)
    pan_number = models.CharField(max_length=20, null=True)
    TYPE_CHOICES = (
        (SAVINGS, 'Savings'),
        (CURRENT, 'Current'),
    )
    pan_copy = models.ImageField('Pan Card Image',upload_to='billing/documents', null=True, blank=True)
    account_copy = models.ImageField('Account/Cheque Image',upload_to='billing/documents', null=True, blank=True)
    type = models.PositiveIntegerField(choices=TYPE_CHOICES, null=True)
    enabled = models.BooleanField(default=False)
    verified_by_finance = models.BooleanField(default=False)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, editable=False, on_delete=models.SET_NULL)
    verified_at = models.DateTimeField(null=True, blank=True, editable=False)
    merchant_add_1 = models.CharField(max_length=200, null=False, blank= True)
    merchant_add_2 = models.CharField(max_length=200, null=False, blank= True)
    merchant_add_3 = models.CharField(max_length=200, null=False, blank= True)
    merchant_add_4 = models.CharField(max_length=200, null=False, blank= True)
    city = models.CharField(max_length=200, null=False, blank= True)
    pin = models.CharField(max_length=200, null=False, blank= True)
    state = models.CharField(max_length=200, null=False, blank= True)
    country = models.CharField(max_length=200, null=False, blank= True)
    email = models.CharField(max_length=200, null=False, blank= True)
    mobile = models.CharField(max_length=200, null=False, blank= True)
    pg_status = models.PositiveIntegerField(choices=CREATION_STATUS_CHOICES, default=NOT_INITIATED, editable=False)
    api_response = JSONField(blank=True, null=True, editable=False)

    class Meta:
        db_table = 'merchant'

    def __str__(self):
        return self.beneficiary_name+"("+self.account_number+")-("+str(self.id)+")"

    def save(self, *args, **kwargs):
        if self.verified_by_finance and (self.pg_status == self.NOT_INITIATED or self.pg_status == self.FAILURE):
            pass
            #self.create_in_pg()

        super().save(*args, **kwargs)

    def create_in_pg(self, *args, **kwargs):
        resp_data = None
        request_payload = dict()
        request_payload["Bene_Code"] = str(self.id)
        request_payload["Bene Name"] = self.beneficiary_name
        request_payload["Bene Add 1"] = self.merchant_add_1
        request_payload["Bene Add 2"] = self.merchant_add_2
        request_payload["Bene Add 3"] = self.merchant_add_3
        request_payload["Bene Add 4"] = self.merchant_add_4
        request_payload["Bene Add 5"] = None
        request_payload["Bene_City"] = self.city
        request_payload["Bene_Pin"] = self.pin
        request_payload["State"] = self.state

        abbr = Merchant.get_abbreviation(self.state)
        if abbr:
            request_payload["State"] = abbr
        else:
            request_payload["State"] = self.state

        #request_payload["Country"] = self.country
        request_payload["Country"] = 'in'
        request_payload["Bene_Email"] = 'payment@docprime.com'
        request_payload["Bene_Mobile"] = self.mobile
        request_payload["Bene_Tel"] = None
        request_payload["Bene_Fax"] = None
        request_payload["IFSC"] = self.ifsc_code
        request_payload["Bene_A/c No"] = self.account_number
        request_payload["Bene Bank"] = None
        request_payload["PaymentType"] = None
        request_payload["isBulk"] = "0"

        #from ondoc.api.v1.utils import payout_checksum
        checksum_response = Merchant.generate_checksum(request_payload)
        request_payload["hash"] = checksum_response
        url = settings.NODAL_BENEFICIARY_API

        nodal_beneficiary_api_token = settings.NODAL_BENEFICIARY_TOKEN

        response = requests.post(url, data=json.dumps(request_payload), headers={'auth': nodal_beneficiary_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code == status.HTTP_200_OK:
            resp_data = response.json()
            self.api_response = resp_data
            if resp_data.get('StatusCode') and resp_data.get('StatusCode') in [1,2,3,4]:
                self.pg_status = resp_data.get('StatusCode')

    @classmethod
    def get_abbreviation(cls, state_name):
        state_slug = slugify(state_name)
        for state,abbr in cls.STATE_ABBREVIATIONS:
            if state_slug == slugify(state):
                return abbr

        return None

    @classmethod
    def get_states_list(cls):        
        states = [x[0] for x in cls.STATE_ABBREVIATIONS]
        return states

    @classmethod
    def get_states_string(cls):
        return ", ".join(cls.get_states_list())

    @classmethod
    def generate_checksum(cls, request_payload):

        secretkey = settings.PG_SECRET_KEY_P1
        accesskey = settings.PG_CLIENT_KEY_P1

        checksum = ""

        curr = ''

        keylist = sorted(request_payload)
        for k in keylist:
            if request_payload[k] is not None:
                curr = curr + k + '=' + str(request_payload[k]) + ';'

        checksum += curr

        checksum = accesskey + "|" + checksum + "|" + secretkey
        checksum_hash = hashlib.sha256(str(checksum).encode())
        checksum_hash = checksum_hash.hexdigest()
        return checksum_hash


    @classmethod
    def update_status_from_pg(cls):
        merchant = Merchant.objects.filter(pg_status__in=[cls.NOT_INITIATED, cls.INITIATED, cls.INPROCESS, cls.FAILURE])
        for data in merchant:
            resp_data = None
            request_payload = {"beneCode": str(data.pk)}
            url = settings.BENE_STATUS_API
            bene_status_token = settings.BENE_STATUS_TOKEN
            response = requests.post(url, data=json.dumps(request_payload), headers={'auth': bene_status_token,
                                                                                     'Content-Type': 'application/json'})
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                data.api_response = resp_data
                if resp_data.get('statusCode') and resp_data.get('statusCode') in [cls.INITIATED, cls.INPROCESS]:
                    data.pg_status = resp_data.get('statusCode')
                    data.save()

class AssociatedMerchant(TimeStampedModel):

    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE, related_name='establishments')
    verified = models.BooleanField(default=False)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'associated_merchant'


class SoftDelete(SafeDeleteModel):
    _safedelete_policy = SOFT_DELETE

    class Meta:
        abstract = True


class StatusHistory(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    status = models.PositiveSmallIntegerField(null=False)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    @classmethod
    def create(cls, *args, **kwargs):
        obj = kwargs.get('content_object')
        if not obj:
            raise Exception('Function accept content_object in **kwargs')

        content_type = ContentType.objects.get_for_model(obj)
        cls(content_type=content_type, object_id=obj.id, status=obj.data_status, user=obj.status_changed_by).save()

    class Meta:
        db_table = 'status_history'


class WelcomeCallingDone(models.Model):
    welcome_calling_done = models.BooleanField(default=False)
    welcome_calling_done_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.welcome_calling_done and not self.welcome_calling_done_at:
            self.welcome_calling_done_at = timezone.now()
        elif not self.welcome_calling_done and self.welcome_calling_done_at:
            self.welcome_calling_done_at = None
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class ClickLoginToken(TimeStampedModel):
    URL_KEY_LENGTH = 30
    token = models.CharField(max_length=300)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    expiration_time = models.DateTimeField(null=True)
    is_consumed = models.BooleanField(default=False)
    url_key = models.CharField(max_length=URL_KEY_LENGTH)

    class Meta:
        db_table = 'click_login_token'


class PhysicalAgreementSigned(models.Model):
    physical_agreement_signed = models.BooleanField(default=False)
    physical_agreement_signed_at = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        from ondoc.api.v1.utils import update_physical_agreement_timestamp
        update_physical_agreement_timestamp(self)
        super().save(*args, **kwargs)

    class Meta:
        abstract = True


class RefundMixin(object):

    @transaction.atomic
    def action_refund(self, refund_flag=1):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.account.models import ConsumerAccount
        from ondoc.common.models import RefundDetails
        from ondoc.account.models import ConsumerTransaction
        from ondoc.account.models import ConsumerRefund
        # Taking Lock first
        consumer_account = None
        product_id = self.PRODUCT_ID
        if self.payment_type == OpdAppointment.PREPAID:
            temp_list = ConsumerAccount.objects.get_or_create(user=self.user)
            consumer_account = ConsumerAccount.objects.select_for_update().get(user=self.user)
        if self.payment_type == OpdAppointment.PREPAID and ConsumerTransaction.valid_appointment_for_cancellation(self.id, product_id):
            RefundDetails.log_refund(self)
            wallet_refund, cashback_refund = self.get_cancellation_breakup()
            consumer_account.credit_cancellation(self, product_id, wallet_refund, cashback_refund)
            if refund_flag:
                ctx_obj = consumer_account.debit_refund()
                ConsumerRefund.initiate_refund(self.user, ctx_obj)

    def can_agent_refund(self, user):
        from ondoc.crm.constants import constants
        if self.status == self.COMPLETED and (user.groups.filter(name=constants['APPOINTMENT_REFUND_TEAM']).exists() or user.is_superuser) and not self.has_app_consumer_trans():
            return True
        return False

    def has_app_consumer_trans(self):
        from ondoc.account.models import ConsumerTransaction
        product_id = self.PRODUCT_ID
        return not ConsumerTransaction.valid_appointment_for_cancellation(self.id, product_id)
        # return ConsumerRefund.objects.filter(consumer_transaction__reference_id=self.id,
        #                               consumer_transaction__product_id=product_id).first()


class LastLoginTimestamp(TimeStampedModel):

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="last_login_timestamp")
    last_login = models.DateTimeField(auto_now=True)
    source = models.CharField(max_length=100)

    def __str__(self):
        return self.user

    class Meta:
        db_table = "last_login_timestamp"