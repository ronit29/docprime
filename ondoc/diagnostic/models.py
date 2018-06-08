from django.contrib.gis.db import models
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, Image, Document, QCModel, UserProfile, User
from ondoc.doctor.models import Hospital
from django.utils import timezone
from datetime import timedelta
from django.contrib.postgres.fields import JSONField
from ondoc.doctor.models import OpdAppointment
from django.utils.text import slugify

class Lab(TimeStampedModel, CreatedByModel, QCModel):
    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"), (ONBOARDED, "Onboarded")]
    name = models.CharField(max_length=200)
    about = models.CharField(max_length=1000, blank=True)
    license = models.CharField(max_length=200, blank=True)
    is_insurance_enabled = models.BooleanField(verbose_name= 'Enabled for Insurance Customer',default=False)
    is_retail_enabled = models.BooleanField(verbose_name= 'Enabled for Retail Customer', default=False)
    is_ppc_pathology_enabled = models.BooleanField(verbose_name= 'Enabled for Pathology Pre Policy Checkup', default=False)
    is_ppc_radiology_enabled = models.BooleanField(verbose_name= 'Enabled for Radiology Pre Policy Checkup', default=False)
    onboarding_status = models.PositiveSmallIntegerField(default=NOT_ONBOARDED, choices=ONBOARDING_STATUS)
    primary_email = models.EmailField(max_length=100, blank=True)
    primary_mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True,  validators=[MinValueValidator(1800)])
    parking = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Easy"), (2,"Difficult")])
    always_open = models.BooleanField(verbose_name= 'Is lab open 24X7', default=False)
    hospital = models.ForeignKey(Hospital, blank = True, null = True, on_delete=models.SET_NULL)
    network_type = models.PositiveSmallIntegerField(blank = True, null = True, choices=[("","Select"), (1,"Non Network Lab"), (2,"Network Lab")])
    network = models.ForeignKey('LabNetwork', null=True, blank=True, on_delete=models.SET_NULL)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    agreed_rate_list = models.FileField(upload_to='lab/docs',max_length=200, null=True, blank=True, validators=[FileExtensionValidator(allowed_extensions=['pdf'])])

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab"


class LabCertification(TimeStampedModel):
    lab = models.ForeignKey(Lab, related_name = 'lab_certificate', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_certification"


class LabAccreditation(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_accreditation"


class LabAward(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_award"


class LabManager(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager"), (4, "Owner")])

    def __str__(self):
        return self.lab.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_manager"


class LabImage(TimeStampedModel, Image):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='lab_image')
    name = models.ImageField(upload_to='lab/images', height_field='height', width_field='width')

    class Meta:
        db_table = "lab_image"


class LabTiming(TimeStampedModel):

    TIME_CHOICES = [(7.0, "7 AM"), (7.5, "7:30 AM"),
    (8.0, "8 AM"), (8.5, "8:30 AM"),
    (9.0, "9 AM"), (9.5, "9:30 AM"),
    (10.0, "10 AM"), (10.5, "10:30 AM"),
    (11.0, "11 AM"), (11.5, "11:30 AM"),
    (12.0, "12 PM"), (12.5, "12:30 PM"),
    (13.0, "1 PM"), (13.5, "1:30 PM"),
    (14.0, "2 PM"), (14.5, "2:30 PM"),
    (15.0, "3 PM"), (15.5, "3:30 PM"),
    (16.0, "4 PM"), (16.5, "4:30 PM"),
    (17.0, "5 PM"), (17.5, "5:30 PM"),
    (18.0, "6 PM"), (18.5, "6:30 PM"),
    (19.0, "7 PM"), (19.5, "7:30 PM"),
    (20.0, "8 PM"), (20.5, "8:30 PM"),
    (21.0, "9 PM"), (21.5, "9:30 PM"),
    (22.0, "10 PM"), (22.5, "10:30 PM")]

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)

    pickup_flag = models.BooleanField(default=False)
    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")])
    start = models.DecimalField(max_digits=3,decimal_places=1, choices = TIME_CHOICES)
    end = models.DecimalField(max_digits=3,decimal_places=1, choices = TIME_CHOICES)

    class Meta:
        db_table = "lab_timing"


class LabNetwork(TimeStampedModel, CreatedByModel, QCModel):
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

    def __str__(self):
        return self.name + " (" + self.city + ")"

    class Meta:
        db_table = "lab_network"


class LabNetworkCertification(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_network_certification"


class LabNetworkAward(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_network_award"


class LabNetworkAccreditation(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "lab_network_accreditation"


class LabNetworkManager(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager")])

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_network_manager"


class LabNetworkHelpline(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    number = models.BigIntegerField()
    details = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return str(self.number)

    class Meta:
        db_table = "lab_network_helpline"


class LabNetworkEmail(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)

    def __str__(self):
        return self.email

    class Meta:
        db_table = "lab_network_email"


class LabTestType(TimeStampedModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_test_type"


class LabTestSubType(TimeStampedModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_test_sub_type"


# class RadiologyTestType(TimeStampedModel):
#     name = models.CharField(max_length=200)

#     def __str__(self):
#         return self.name

#     class Meta:
#         db_table = "radiology_test_type"

class LabTest(TimeStampedModel):
    name = models.CharField(max_length=200)
    test_type = models.ForeignKey(LabTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_type')
    test_sub_type = models.ForeignKey(LabTestSubType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_sub_type')
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    why = models.CharField(max_length=1000, blank=True)
    pre_test_info = models.CharField(max_length=1000, blank=True)
    sample_handling_instructions = models.CharField(max_length=1000, blank=True)
    sample_collection_instructions = models.CharField(max_length=1000, blank=True)
    preferred_time = models.CharField(max_length=1000, blank=True)
    sample_amount = models.CharField(max_length=1000, blank=True)
    expected_tat = models.CharField(max_length=1000, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_test"


class AvailableLabTest(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='availabletests')
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='availablelabs')
    mrp = models.PositiveSmallIntegerField()
    agreed_price = models.PositiveSmallIntegerField()
    deal_price = models.PositiveSmallIntegerField()

    def __str__(self):
        return self.test.name+', '+self.lab.name

    class Meta:
        db_table = "available_lab_test"


class LabAppointment(TimeStampedModel):
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_LAB = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5

    # RESCHEDULED_BY_USER = 4
    # REJECTED = 4
    CANCELED = 6
    COMPLETED = 7

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='labappointment')
    lab_test = models.ManyToManyField(AvailableLabTest)
    profile = models.ForeignKey(UserProfile, related_name="labappointments", on_delete=models.CASCADE)
    profile_detail = JSONField(blank=True, null=True)
    status = models.PositiveSmallIntegerField(default=CREATED)
    price = models.PositiveSmallIntegerField()
    time_slot_start = models.DateTimeField(blank=True, null=True)
    time_slot_end = models.DateTimeField(blank=True, null=True)
    otp = models.PositiveIntegerField(blank=True, null=True)
    payment_status = models.PositiveIntegerField(choices=OpdAppointment.PAYMENT_STATUS_CHOICES,
                                                 default=OpdAppointment.PAYMENT_PENDING)
    is_home_pickup = models.BooleanField(default=False)
    address = JSONField(blank=True, null=True)

    def allowed_action(self, user_type):
        allowed = []
        current_datetime = timezone.now()
        if user_type == User.CONSUMER and current_datetime < self.time_slot_start + timedelta(hours=6):
            if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_LAB, self.RESCHEDULED_PATIENT):
                allowed = [self.RESCHEDULED_PATIENT, self.CANCELED]

        return allowed

    def __str__(self):
        return self.profile.name+', '+self.lab.name

    class Meta:
        db_table = "lab_appointment"


class CommonTest(TimeStampedModel):
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='commontest')


class CommonDiagnosticCondition(TimeStampedModel):
    name = models.CharField(max_length=200)
    test = models.ManyToManyField(LabTest)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "common_diagnostic_condition"


class PromotedLab(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)

    def __str__(self):
        return self.lab.name

    class Meta:
        db_table = "promoted_lab"

# class RadiologyTest(TimeStampedModel):
#     name = models.CharField(max_length=200)
#     test_type = models.ForeignKey(RadiologyTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_type')
#     test_sub_type = models.ForeignKey(RadiologyTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_sub_type')
#     is_package = models.BooleanField(verbose_name= 'Is this test package type?')
#     why = models.CharField(max_length=1000, blank=True)
#     pre_test_info = models.CharField(max_length=1000, blank=True)

#     def __str__(self):
#         return self.name

#     class Meta:
#         db_table = "radiology_test"


class LabService(TimeStampedModel):
    PATHOLOGY = 1
    RADIOLOGY = 2
    SERVICE_CHOICES = [(PATHOLOGY, "Pathology"), (RADIOLOGY, "Radiology")]
    lab = models.ForeignKey(Lab, null=True, on_delete=models.CASCADE)
    service = models.PositiveSmallIntegerField(default=None, choices=SERVICE_CHOICES)

    def __str__(self):
        return str(self.service)

    class Meta:
        db_table = "lab_service"


class LabDoctorAvailability(TimeStampedModel):
    SLOT_CHOICES = [("m","Morning"), ("e","Evening")]
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    is_male_available = models.BooleanField(verbose_name= 'Male', default=False)
    is_female_available = models.BooleanField(verbose_name= 'Female', default=False)
    slot = models.CharField(blank=False, max_length=2, choices=SLOT_CHOICES)

    def __str__(self):
        return self.lab.name

    class Meta:
        db_table = "lab_doctor_availability"


class LabDoctor(TimeStampedModel):
    registration_number = models.CharField(max_length=100, blank=False)
    lab = models.ForeignKey(Lab, null=True, blank=True, default=None, on_delete=models.CASCADE)

    def __str__(self):
        return self.registration_number

    class Meta:
        db_table = "lab_doctor"


class LabDocument(TimeStampedModel, Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    REGISTRATION = 4
    CHEQUE = 5
    LOGO = 6
    CHOICES = [(PAN, "PAN Card"), (ADDRESS,"Address Proof"), (GST,"GST Certificate"), (REGISTRATION,"Registration Certificate"),(CHEQUE,"Cancel Cheque Copy"),(LOGO,"LOGO")]
    lab = models.ForeignKey(Lab, null=True, blank=True, default=None, on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='lab/images', validators=[FileExtensionValidator(allowed_extensions=['pdf','jfif','jpg','jpeg','png'])])

    def prefix(self):
        return slugify(self.lab.name)
        


    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')


    # def __str__(self):
        # return self.name

    class Meta:
        db_table = "lab_document"


class LabOnboardingToken(TimeStampedModel):
    GENERATED = 1
    REJECTED = 2
    CONSUMED = 3
    STATUS_CHOICES = [(GENERATED, "Generated"), (REJECTED, "Rejected"), (CONSUMED, "Consumed")]
    lab = models.ForeignKey(Lab, null=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    verified_token = models.CharField(max_length=100, null=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=GENERATED)

    class Meta:
        db_table = "lab_onboarding_token"
