from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator

class Image(models.Model):
    # name = models.ImageField(height_field='height', width_field='width')
    width = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)
    height = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)

    class Meta:
        abstract = True

class QCModel(models.Model):
    data_status = models.PositiveSmallIntegerField(default=1, editable=False, choices=[(1,"In Progress"), (2,"Submitted For QC Check"), (3,"QC approved")])

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
