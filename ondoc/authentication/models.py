from django.conf import settings
from django.db import models
from django.db.models import Q, Prefetch
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.core.validators import MaxValueValidator, MinValueValidator
from django.contrib.postgres.fields import JSONField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


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
    DATA_STATUS_CHOICES = [(IN_PROGRESS, "In Progress"), (SUBMITTED_FOR_QC, "Submitted For QC Check"), (QC_APPROVED, "QC approved")]
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
    
    profile_image = models.ImageField(upload_to='users/images', height_field='height', width_field='width', blank=True, null=True)

    def __str__(self):
        return "{}-{}".format(self.name, self.id)

    class Meta:
        db_table = "user_profile"


class OtpVerifications(TimeStampedModel):
    OTP_EXPIRY_TIME = 60  # In minutes
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
    APPOINTMENT = 'appointment'
    BILLINNG = 'billing'
    type_choices = ((APPOINTMENT, 'Appointment'), (BILLINNG, 'Billing'), )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hospital_network = models.ForeignKey("doctor.HospitalNetwork", null=True, blank=True,
                                         on_delete=models.CASCADE,
                                         related_name='network_admins')
    hospital = models.ForeignKey("doctor.Hospital", null=True, blank=True,on_delete=models.CASCADE,
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

    @classmethod
    def get_user_admin_obj(cls, user):
        from ondoc.payout.models import Outstanding
        access_list = []
        get_permissions = (UserPermission.objects.select_related('hospital_network', 'hospital').
                           filter(user_id=user.id, write_permission=True, permission_type=UserPermission.BILLINNG))
        if get_permissions:
            for permission in get_permissions:
                if permission.hospital_network_id:
                    if permission.hospital_network.is_billing_enabled:
                        access_list.append({'admin_obj': permission.hospital_network, 'admin_level': Outstanding.HOSPITAL_NETWORK_LEVEL})
                elif permission.hospital_id:
                    if permission.hospital.is_billing_enabled:
                        access_list.append({'admin_obj': permission.hospital, 'admin_level': Outstanding.HOSPITAL_LEVEL})
                else:
                    access_list.append({'admin_obj': permission.doctor, 'admin_level': Outstanding.DOCTOR_LEVEL})
        return access_list
        # TODO PM - Logic to get admin for a particular User

    @classmethod
    def get_billable_doctor_hospital(cls, user):
        permission_data = (UserPermission.objects.
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


class GenericAdmin(TimeStampedModel):
    APPOINTMENT = 1
    BILLINNG = 2

    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.CharField(max_length=10)
    type_choices = ((APPOINTMENT, 'Appointment'), (BILLINNG, 'Billing'),)
    hospital_network = models.ForeignKey("doctor.HospitalNetwork", null=True, blank=True,
                                         on_delete=models.CASCADE,
                                         related_name='manageable_hospital_networks')
    hospital = models.ForeignKey("doctor.Hospital", null=True, blank=True, on_delete=models.CASCADE,
                                 related_name='manageable_hospitals')
    doctor = models.ForeignKey("doctor.Doctor", null=True, blank=True, on_delete=models.CASCADE,
                               related_name='manageable_doctors')
    permission_type = models.PositiveSmallIntegerField(max_length=20, choices=type_choices, default=APPOINTMENT)
    is_doc_admin = models.BooleanField(default=False)
    is_disabled = models.BooleanField(default=False)
    super_user_permission = models.BooleanField(default=False)
    read_permission = models.BooleanField(default=False)
    write_permission = models.BooleanField(default=False)

    class Meta:
        db_table = 'generic_admin'

    def __str__(self):
        return "{}:{}".format(self.phone_number, self.hospital)

    def save(self, *args, **kwargs):
        self.clean()
        user = User.objects.filter(phone_number=self.phone_number).first()
        if user is not None:
            self.user = user
        if self.permission_type == self.BILLINNG:
            self.hospital = None
        super(GenericAdmin, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.clean()
        super(GenericAdmin, self).delete(*args, **kwargs)

    @classmethod
    def update_user_admin(cls, phone_number):
        user = User.objects.filter(phone_number=phone_number)
        if user.exists():
            admin = GenericAdmin.objects.filter(phone_number=phone_number, user__isnull=True)
            if admin.exists():
                admin.update(user=user.first())


    @classmethod
    def create_admin_permissions(cls, doctor):
        from ondoc.doctor.models import DoctorHospital, DoctorMobile
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
                                                                             ~Q(user=doc_user)).distinct('user')
        doc_hosp_data = DoctorHospital.objects.select_related('doctor', 'hospital')\
                                      .filter(doctor=doctor)\
                                      .distinct('hospital')

        if doc_admin_users.exists():
            for doc_admin_usr in doc_admin_users.all():
                doc_admin_usr_list.append(doc_admin_usr.user)
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
                        doctor_admins.append(cls.create_permission_object(user=doc_admin_user,
                                                                          doctor=doctor,
                                                                          phone_number=doc_admin_user.phone_number,
                                                                          hospital_network=None,
                                                                          hospital=row.hospital,
                                                                          permission_type=GenericAdmin.APPOINTMENT,
                                                                          is_doc_admin=True,
                                                                          is_disabled=is_disabled,
                                                                          super_user_permission=False,
                                                                          write_permission=True,
                                                                          read_permission=True))

            if doctor_admins:
                GenericAdmin.objects.bulk_create(doctor_admins)

    @classmethod
    def create_admin_billing_permissions(cls, doctor):
        from ondoc.doctor.models import DoctorMobile
        doc_user = None
        doc_number = None
        doc_mobile = DoctorMobile.objects.filter(doctor=doctor, is_primary=True)
        if doc_mobile.exists():
            doc_number = doc_mobile.first().number
        if doctor.user:
            doc_user = doctor.user
        if doc_number:
            billing_perm = GenericAdmin.objects.filter(doctor=doctor,
                                                       phone_number=doc_number,
                                                       permission_type=GenericAdmin.BILLINNG)
            if not billing_perm.exists():
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
    def create_permission_object(cls, user, doctor, phone_number, hospital_network, hospital, permission_type,
                                 is_doc_admin, is_disabled, super_user_permission, write_permission, read_permission):
        return GenericAdmin(user=user,
                            doctor=doctor,
                            phone_number=phone_number,
                            hospital_network=hospital_network,
                            hospital=hospital,
                            permission_type=permission_type,
                            is_doc_admin=is_doc_admin,
                            is_disabled=is_disabled,
                            super_user_permission=super_user_permission,
                            write_permission=write_permission,
                            read_permission=read_permission
                            )





