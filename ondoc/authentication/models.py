from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import JSONField
# from ondoc.doctor.models import OpdAppointment


class Image(models.Model):
    # name = models.ImageField(height_field='height', width_field='width')
    width = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)
    height = models.PositiveSmallIntegerField(editable=False,blank=True, null=True)

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

    def __str__(self):
        if self.user_type==1 and hasattr(self, 'staffprofile'):
            return self.staffprofile.name
        return str(self.phone_number)

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
    #user = models.OneToOneField(User, on_delete=models.CASCADE)

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
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE,"Male"), (FEMALE,"Female"), (OTHER,"Other")]
    user = models.ForeignKey(User, related_name="profiles", on_delete=models.CASCADE)
    name = models.CharField(max_length=100, blank=False, null=True, default=None)
    email = models.CharField(max_length=256, blank=False, null=True, default=None)
    gender = models.CharField(max_length=2, default=None, blank=True, null=True, choices=GENDER_CHOICES)
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
    is_expired = models.BooleanField(default=False)

    def __str__(self):
        return self.phone_number

    class Meta:
        db_table = "otp_verification"


class NotificationEndpoint(TimeStampedModel):
    user = models.ForeignKey(User, related_name='notification_endpoints', on_delete=models.CASCADE,
                             blank=True, null=True)
    device_id = models.TextField(blank=True, null=True)
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
    place_id = models.CharField(null=True, blank=True, max_length=100)
    address = models.TextField(null=True, blank=True)
    land_mark = models.TextField(null=True, blank=True)
    pincode = models.PositiveIntegerField(null=True, blank=True)
    phone_number = models.CharField(null=True, blank=True, max_length=10)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "address"

    def __str__(self):
        return str(self.user)


class UserPermission(TimeStampedModel):
    from ondoc.doctor.models import Hospital, HospitalNetwork, Doctor
    APPOINTMENT = 'appointment'
    type_choices = ((APPOINTMENT, 'Appointment'), )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hospital_network = models.ForeignKey(HospitalNetwork, null=True, blank=True, on_delete=models.CASCADE,


                                         related_name='network_admins')
    hospital = models.ForeignKey(Hospital, null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='hospital_admins')
    doctor = models.ForeignKey(Doctor, null=True, blank=True, on_delete=models.CASCADE,
                               related_name='doc_permission')

    permission_type = models.CharField(max_length=20, choices=type_choices, default=APPOINTMENT)

    read_permission = models.BooleanField(default=False)
    write_permission = models.BooleanField(default=False)
    delete_permission = models.BooleanField(default=False)

    class Meta:
        db_table = 'user_permission'

    def __str__(self):
        return str(self.user.email)


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

