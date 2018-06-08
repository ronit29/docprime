from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from PIL import Image as Img
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import math
import os
import hashlib


class Image(models.Model):
    # name = models.ImageField(height_field='height', width_field='width')
    width = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)
    height = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.__original_name = self.name

    def has_image_changed(self):
        if not self.pk:
            return False
        old_value = self.__class__._default_manager.filter(pk=self.pk).values('name').get()['name']
        return not getattr(self, 'name') == old_value


    def save(self, *args, **kwargs):
        self.has_image_changed()
        if self.name:
            max_allowed = 1000
            img = Img.open(self.name)
            size = img.size
            #new_size = ()

            if max(size)>max_allowed:
                size = tuple(math.floor(ti/(max(size)/max_allowed)) for ti in size)

            img = img.resize(size, Img.ANTIALIAS)

            # if img.mode != 'RGB':
            #     img = img.convert('RGB')

            md5_hash = hashlib.md5(img.tobytes()).hexdigest()
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
    # name = models.ImageField(height_field='height', width_field='width')
    # width = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)
    # height = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)
    def save(self, *args, **kwargs):
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

            # if img.mode != 'RGB':
            #     img = img.convert('RGB')

                md5_hash = hashlib.md5(img.tobytes()).hexdigest()
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
    DATA_STATUS_CHOICES = [(IN_PROGRESS, "In Progress"),(SUBMITTED_FOR_QC, "Submitted For QC Check"), (QC_APPROVED, "QC approved")]
    data_status = models.PositiveSmallIntegerField(default=1, editable=False, choices=DATA_STATUS_CHOICES)

    class Meta:
        abstract = True

class CustomUserManager(BaseUserManager):
    """Define a model manager for User model with no username field."""

    use_in_migrations = True

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
    USER_TYPE_CHOICES = ((1, 'staff'), (2, 'doctor'), (3, 'user'))
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

    def __str__(self):
        return self.phone_number

    def save(self, *args, **kwargs):
        if self.email:    
            self.email = self.email.lower()
        return super().save(*args, **kwargs)


    class Meta:
        unique_together = (("email", "user_type"), ("phone_number","user_type"))
        db_table = "auth_user"

class StaffProfile(models.Model):
    name = models.CharField(max_length=100, blank=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)

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

class CreatedByModel(models.Model):
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, editable=False, on_delete=models.SET_NULL)

    class Meta:
        abstract = True

class UserProfile(TimeStampedModel, Image):
    
    user = models.ForeignKey(User, related_name="profiles", on_delete=models.CASCADE)
    name = models.CharField(max_length=100, blank=False, default=None)
    email = models.CharField(max_length=20, blank=False, default=None)
    gender = models.CharField(max_length=2, default=None, blank=True, choices=[("","Select"), ("m","Male"), ("f","Female"), ("o","Other")])
    phone_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    is_otp_verified = models.BooleanField(default=False)
    is_default_user = models.BooleanField(default=False)
    dob = models.DateField(blank=True, null=True)
    
    profile_image = models.ImageField(upload_to='users/images' ,height_field='height', width_field='width',blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "user_profile"

class OtpVerifications(TimeStampedModel):
    phone_number = models.CharField(max_length=10)
    code = models.CharField(max_length=10)
    country_code = models.CharField(max_length=10)
    isExpired = models.BooleanField(default=False)

    def __str__(self):
        return self.phone_number

    class Meta:
        db_table = "otp_verification"
