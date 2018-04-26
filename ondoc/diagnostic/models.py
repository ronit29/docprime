from django.contrib.gis.db import models
from django.core.validators import MaxValueValidator, MinValueValidator
from ondoc.authentication.models import TimeStampedModel, CreatedByModel, Image, QCModel
from ondoc.doctor.models import Hospital


class Lab(TimeStampedModel, CreatedByModel, QCModel):
    name = models.CharField(max_length=200)
    about = models.CharField(max_length=1000, blank=True)
    license = models.CharField(max_length=200, blank=True)
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
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab"


class LabCertification(TimeStampedModel):
    lab = models.ForeignKey(Lab, related_name = 'lab_certificates', on_delete=models.CASCADE)
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
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='lab/images',height_field='height', width_field='width')

    class Meta:
        db_table = "lab_image"


class LabTiming(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)

    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=[(1, "Monday"), (2, "Tuesday"), (3, "Wednesday"), (4, "Thursday"), (5, "Friday"), (6, "Saturday"), (7, "Sunday")])
    start = models.PositiveSmallIntegerField(
        blank=False, null=False, choices=[(6, "6 AM"), (7, "7 AM"),
        (8, "8 AM"), (9, "9 AM"), (10, "10 AM"), (11, "11 AM"),
        (12, "12 PM"), (13, "1 PM"), (14, "2 PM"), (15, "3 PM"),
        (16, "4 PM"), (17, "5 PM"), (18, "6 PM"), (19, "7 PM"),
        (20, "8 PM"), (21, "9 PM"), (22, "10 PM"), (23, "11 PM")])
    end = models.PositiveSmallIntegerField(
        blank=False, null=False, choices=[(6, "6 AM"), (7, "7 AM"),
        (8, "8 AM"), (9, "9 AM"), (10, "10 AM"), (11, "11 AM"),
        (12, "12 PM"), (13, "1 PM"), (14, "2 PM"), (15, "3 PM"),
        (16, "4 PM"), (17, "5 PM"), (18, "6 PM"), (19, "7 PM"),
        (20, "8 PM"), (21, "9 PM"), (22, "10 PM"), (23, "11 PM")])

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
        return self.number

    class Meta:
        db_table = "lab_network_helpline"


class LabNetworkEmail(TimeStampedModel):
    network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)

    def __str__(self):
        return self.email

    class Meta:
        db_table = "lab_network_email"


class PathologyTestType(TimeStampedModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "pathology_test_type"

class RadiologyTestType(TimeStampedModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "radiology_test_type"

class PathologyTest(TimeStampedModel):
    name = models.CharField(max_length=200)
    test_type = models.ForeignKey(PathologyTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_type')
    test_sub_type = models.ForeignKey(PathologyTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_sub_type')
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    why = models.CharField(max_length=1000, blank=True)
    pre_test_info = models.CharField(max_length=1000, blank=True)
    sample_handling_instructions = models.CharField(max_length=1000, blank=True)
    sample_collection_instructions = models.CharField(max_length=1000, blank=True)
    sample_amount = models.CharField(max_length=1000, blank=True)
    expected_tat = models.CharField(max_length=1000, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "pathalogy_test"

class RadiologyTest(TimeStampedModel):
    name = models.CharField(max_length=200)
    test_type = models.ForeignKey(RadiologyTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_type')
    test_sub_type = models.ForeignKey(RadiologyTestType, blank=True, null=True, on_delete=models.SET_NULL, related_name='test_sub_type')
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    why = models.CharField(max_length=1000, blank=True)
    pre_test_info = models.CharField(max_length=1000, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "radiology_test"

class LabService(TimeStampedModel):
    SERVICE_CHOICES = [(1,"Pathology"), (2,"Radiology")]
    lab = models.ForeignKey(Lab, null=True, on_delete=models.CASCADE)
    service = models.PositiveSmallIntegerField(default=None, choices=SERVICE_CHOICES)

    def __str__(self):
        return self.name

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


class LabDocument(TimeStampedModel, Image):
    PAN = 1
    ADDRESS = 2
    GST = 3
    REGISTRATION = 4
    CHEQUE = 5
    CHOICES = [(PAN,"PAN Card"), (ADDRESS,"Address Proof"), (GST,"GST Certificate"), (REGISTRATION,"Registration Certificate"),(CHEQUE,"Cancel Cheque Copy")]
    lab = models.ForeignKey(Lab, null=True, blank=True, default=None, on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.ImageField(upload_to='lab/images', height_field='height', width_field='width')

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_document"

class LabOnboardingToken(TimeStampedModel):
    GENERATED = 1
    REJECTED = 2
    CONSUMED = 3
    STATUS_CHOICES = [(GENERATED, "Generated"), (REJECTED, "Rejected"), (CONSUMED, "Consumed")]
    lab = models.ForeignKey(Lab, null=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=100)
    verified_token = models.CharField(max_length=100, null=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=GENERATED)

    class Meta:
        db_table = "lab_onboarding_token"
