from django.contrib.gis.db import models
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from ondoc.authentication.models import (TimeStampedModel, CreatedByModel, Image, Document, QCModel, UserProfile, User,
                                         UserPermission, GenericAdmin, LabUserPermission)
from ondoc.doctor.models import Hospital, SearchKey
from ondoc.notification import models as notification_models
from ondoc.api.v1.utils import AgreedPriceCalculate, DealPriceCalculate
from ondoc.account import models as account_model
from django.utils import timezone
from datetime import timedelta
from django.db.models import F, Sum, When, Case, Q
from django.contrib.postgres.fields import JSONField
from ondoc.doctor.models import OpdAppointment
from ondoc.payout.models import Outstanding
from ondoc.api.v1.utils import get_start_end_datetime
import decimal
import math
import random
import os
from ondoc.insurance import models as insurance_model
from django.contrib.contenttypes.fields import GenericRelation

class LabPricingGroup(TimeStampedModel, CreatedByModel):
    group_name = models.CharField(max_length=256)
    pathology_agreed_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                            decimal_places=2)
    pathology_deal_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                          decimal_places=2)
    radiology_agreed_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                            decimal_places=2)
    radiology_deal_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                          decimal_places=2)

    class Meta:
        db_table = 'lab_pricing_group'

    def __str__(self):
        return "{}".format(self.group_name)

    def save(self, *args, **kwargs):
        edit_instance = None
        if self.id is not None:
            edit_instance = 1
            original = LabPricingGroup.objects.get(pk=self.id)

        super(LabPricingGroup, self).save(*args, **kwargs)

        if edit_instance is not None:
            id = self.id

            path_agreed_price_prcnt = decimal.Decimal(
                self.pathology_agreed_price_percentage) if self.pathology_agreed_price_percentage is not None else None

            path_deal_price_prcnt = decimal.Decimal(
                self.pathology_deal_price_percentage) if self.pathology_deal_price_percentage is not None else None

            rad_agreed_price_prcnt = decimal.Decimal(
                self.radiology_agreed_price_percentage) if self.radiology_agreed_price_percentage is not None else None

            rad_deal_price_prcnt = decimal.Decimal(
                self.radiology_deal_price_percentage) if self.radiology_deal_price_percentage is not None else None

            if not original.pathology_agreed_price_percentage == self.pathology_agreed_price_percentage \
                    or not original.pathology_deal_price_percentage == self.pathology_deal_price_percentage:
                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.PATHOLOGY). \
                    update(computed_agreed_price=AgreedPriceCalculate(F('mrp'), path_agreed_price_prcnt))

                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.PATHOLOGY). \
                    update(
                    computed_deal_price=DealPriceCalculate(F('mrp'), F('computed_agreed_price'), path_deal_price_prcnt))

            if not original.radiology_agreed_price_percentage == self.radiology_agreed_price_percentage \
                    or not original.radiology_deal_price_percentage == self.radiology_deal_price_percentage:
                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.RADIOLOGY). \
                    update(computed_agreed_price=AgreedPriceCalculate(F('mrp'), rad_agreed_price_prcnt))

                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.RADIOLOGY). \
                    update(
                    computed_deal_price=DealPriceCalculate(F('mrp'), F('computed_agreed_price'), rad_deal_price_prcnt))


class LabTestPricingGroup(LabPricingGroup):

    class Meta:
        proxy = True
        default_permissions = []



class Lab(TimeStampedModel, CreatedByModel, QCModel, SearchKey):
    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"),
                         (ONBOARDED, "Onboarded")]
    name = models.CharField(max_length=200)
    about = models.CharField(max_length=1000, blank=True)
    license = models.CharField(max_length=200, blank=True)
    is_insurance_enabled = models.BooleanField(verbose_name= 'Enabled for Insurance Customer',default=False)
    is_retail_enabled = models.BooleanField(verbose_name= 'Enabled for Retail Customer', default=False)
    is_ppc_pathology_enabled = models.BooleanField(verbose_name= 'Enabled for Pathology Pre Policy Checkup', default=False)
    is_ppc_radiology_enabled = models.BooleanField(verbose_name= 'Enabled for Radiology Pre Policy Checkup', default=False)
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)
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
    agreed_rate_list = models.FileField(upload_to='lab/docs', max_length=200, null=True, blank=True, validators=[FileExtensionValidator(allowed_extensions=['pdf'])])
    pathology_agreed_price_percentage = models.DecimalField(blank=True, null=True, default=None,max_digits=7,
                                                         decimal_places=2)
    pathology_deal_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                       decimal_places=2)
    radiology_agreed_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                         decimal_places=2)
    radiology_deal_price_percentage = models.DecimalField(blank=True, null=True, default=None, max_digits=7,
                                                       decimal_places=2)

    lab_pricing_group = models.ForeignKey(LabPricingGroup, blank=True, null=True, on_delete=models.SET_NULL,
                                          related_name='labs')

    # generic_lab_admins = GenericRelation(GenericAdmin, related_query_name='manageable_labs')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_lab')
    matrix_lead_id = models.BigIntegerField(blank=True, null=True)
    matrix_reference_id = models.BigIntegerField(blank=True, null=True)
    is_home_pickup_available = models.BigIntegerField(null=True, blank=True)
    is_home_collection_enabled = models.BooleanField(default=False)
    home_pickup_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_live = models.BooleanField(verbose_name='Is Live', default=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab"

    def get_thumbnail(self):
        all_documents = self.lab_documents.all()
        for document in all_documents:
            if document.document_type == LabDocument.LOGO:
                return document.name.url
        return None
        # return static('lab_images/lab_default.png')

    def save(self, *args, **kwargs):
        self.clean()
        
        edit_instance = None
        if self.id is not None:
            edit_instance = 1
            original = Lab.objects.get(pk=self.id)

        super(Lab, self).save(*args, **kwargs)

        if edit_instance is not None:
            id = self.id

            path_agreed_price_prcnt = decimal.Decimal(self.pathology_agreed_price_percentage) if self.pathology_agreed_price_percentage is not None else None

            path_deal_price_prcnt = decimal.Decimal(self.pathology_deal_price_percentage) if self.pathology_deal_price_percentage is not None else None

            rad_agreed_price_prcnt = decimal.Decimal(self.radiology_agreed_price_percentage) if self.radiology_agreed_price_percentage is not None else None

            rad_deal_price_prcnt = decimal.Decimal(self.radiology_deal_price_percentage) if self.radiology_deal_price_percentage is not None else None

            if not original.pathology_agreed_price_percentage==self.pathology_agreed_price_percentage \
                or not original.pathology_deal_price_percentage==self.pathology_deal_price_percentage:
                AvailableLabTest.objects.\
                    filter(lab=id, test__test_type=LabTest.PATHOLOGY).\
                    update(computed_agreed_price=AgreedPriceCalculate(F('mrp'), path_agreed_price_prcnt))

                AvailableLabTest.objects.\
                    filter(lab=id, test__test_type=LabTest.PATHOLOGY).\
                    update(computed_deal_price=DealPriceCalculate(F('mrp'), F('computed_agreed_price'), path_deal_price_prcnt))

            if not original.radiology_agreed_price_percentage==self.radiology_agreed_price_percentage \
                or not original.radiology_deal_price_percentage==self.radiology_deal_price_percentage:

                AvailableLabTest.objects.\
                    filter(lab=id, test__test_type=LabTest.RADIOLOGY).\
                    update(computed_agreed_price=AgreedPriceCalculate(F('mrp'), rad_agreed_price_prcnt))

                AvailableLabTest.objects.\
                    filter(lab=id, test__test_type=LabTest.RADIOLOGY).\
                    update(computed_deal_price=DealPriceCalculate(F('mrp'), F('computed_agreed_price'), rad_deal_price_prcnt))



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
    CONTACT_TYPE_CHOICES = [(1, "Other"), (2, "Single Point of Contact"), (3, "Manager"), (4, "Owner")]
    contact_type = models.PositiveSmallIntegerField(
        choices=CONTACT_TYPE_CHOICES)

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

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='lab_timings')

    for_home_pickup = models.BooleanField(default=False)
    day = models.PositiveSmallIntegerField(blank=False, null=False,
                                           choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
                                                    (4, "Friday"), (5, "Saturday"), (6, "Sunday")])
    start = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    end = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)

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
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)

    # generic_lab_network_admins = GenericRelation(GenericAdmin, related_query_name='manageable_lab_networks')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_lab_networks')


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
    contact_type = models.PositiveSmallIntegerField(
        choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager")])

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
    name = models.CharField(max_length=200, unique=True)

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


class LabTest(TimeStampedModel, SearchKey):
    RADIOLOGY = 1
    PATHOLOGY = 2
    TEST_TYPE_CHOICES = (
        (RADIOLOGY, "Radiology"),
        (PATHOLOGY, "Pathology"),
    )
    name = models.CharField(max_length=200, unique=True)
    test_type = models.PositiveIntegerField(choices=TEST_TYPE_CHOICES, blank=True, null=True)
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    why = models.TextField(blank=True)
    pre_test_info = models.CharField(max_length=1000, blank=True)
    sample_handling_instructions = models.CharField(max_length=1000, blank=True)
    sample_collection_instructions = models.CharField(max_length=1000, blank=True)
    preferred_time = models.CharField(max_length=1000, blank=True)
    sample_amount = models.CharField(max_length=1000, blank=True)
    expected_tat = models.CharField(max_length=1000, blank=True)
    category = models.CharField(max_length=100, blank=True)
    excel_id = models.CharField(max_length=100, blank=True)
    sample_type = models.CharField(max_length=500, blank=True)
    home_collection_possible = models.BooleanField(default=False, verbose_name= 'Can sample be home collected for this test?')
    # test_sub_type = models.ManyToManyField(
    #     LabTestSubType,
    #     through='LabTestSubTypeMapping',
    #     through_fields=("lab_test", "test_sub_type", )
    # )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_test"


# class LabTestSubTypeMapping(TimeStampedModel):
#     lab_test = models.ForeignKey(LabTest, on_delete=models.CASCADE)
#     test_sub_type = models.ForeignKey(LabTestSubType, on_delete=models.CASCADE)

#     class Meta:
#         db_table = "labtest_subtype_mapping"

#     def __str__(self):
#         return "{}-{}".format(self.lab_test.id, self.test_sub_type.id)


class AvailableLabTest(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='availabletests', null=True, blank=True)
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='availablelabs')
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    computed_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    custom_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    computed_deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    custom_deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    enabled = models.BooleanField(default=False)
    lab_pricing_group = models.ForeignKey(LabPricingGroup, blank=True, null=True, on_delete=models.SET_NULL,
                                          related_name='available_lab_tests')

    def get_testid(self):
        return self.test.id

    def get_type(self):
        return self.test.test_type

    def __str__(self):
        return "{}, {}".format(self.test.name, self.lab.name if self.lab else self.lab_pricing_group.group_name)

    class Meta:
        db_table = "available_lab_test"


class LabAppointment(TimeStampedModel):
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_LAB = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7
    ACTIVE_APPOINTMENT_STATUS = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                                 (RESCHEDULED_LAB, 'Rescheduled by lab'),
                                 (RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                                 (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                                 (COMPLETED, 'Completed')]

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='labappointment')
    lab_test = models.ManyToManyField(AvailableLabTest)
    profile = models.ForeignKey(UserProfile, related_name="labappointments", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    profile_detail = JSONField(blank=True, null=True)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=ACTIVE_APPOINTMENT_STATUS)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # This is mrp
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    effective_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    time_slot_start = models.DateTimeField(blank=True, null=True)
    time_slot_end = models.DateTimeField(blank=True, null=True)
    otp = models.PositiveIntegerField(blank=True, null=True)
    payment_status = models.PositiveIntegerField(choices=OpdAppointment.PAYMENT_STATUS_CHOICES,
                                                 default=OpdAppointment.PAYMENT_PENDING)

    payment_type = models.PositiveSmallIntegerField(choices=OpdAppointment.PAY_CHOICES, default=OpdAppointment.PREPAID)
    insurance = models.ForeignKey(insurance_model.Insurance, blank=True, null=True, default=None,
                                  on_delete=models.DO_NOTHING)
    is_home_pickup = models.BooleanField(default=False)
    address = JSONField(blank=True, null=True)
    outstanding = models.ForeignKey(Outstanding, blank=True, null=True, on_delete=models.SET_NULL)

    def allowed_action(self, user_type):
        allowed = []
        current_datetime = timezone.now()
        if user_type == User.CONSUMER and current_datetime < self.time_slot_start + timedelta(hours=6):
            if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_LAB, self.RESCHEDULED_PATIENT):
                allowed = [self.RESCHEDULED_PATIENT, self.CANCELLED]

        return allowed

    def send_notification(self, database_instance):
        if database_instance and database_instance.status == self.status:
            return
        if not self.user:
            return
        if self.status == LabAppointment.COMPLETED:
            notification_models.NotificationAction.trigger(
                instance=self,
                user=self.user,
                notification_type=notification_models.NotificationAction.LAB_INVOICE,
            )

    def save(self, *args, **kwargs):
        database_instance = LabAppointment.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        self.send_notification(database_instance)

    @classmethod
    def create_appointment(cls, appointment_data):
        otp = random.randint(1000, 9999)
        appointment_data["payment_status"] = OpdAppointment.PAYMENT_ACCEPTED
        appointment_data["status"] = OpdAppointment.BOOKED
        appointment_data["otp"] = otp
        lab_ids = appointment_data.pop("lab_test")
        app_obj = cls.objects.create(**appointment_data)
        app_obj.lab_test.add(*lab_ids)
        return app_obj

    def action_rescheduled_lab(self):
        self.status = self.RESCHEDULED_LAB
        self.save()
        return self

    def action_rescheduled_patient(self, data):
        self.status = self.RESCHEDULED_PATIENT
        self.time_slot_start = data.get('time_slot_start')
        self.agreed_price = data.get('agreed_price', self.agreed_price)
        self.price = data.get('price', self.price)
        self.deal_price = data.get('deal_price', self.deal_price)
        self.effective_price = data.get('effective_price', self.effective_price)

        self.save()

    def action_accepted(self):
        self.status = self.ACCEPTED
        self.save()

    def action_cancelled(self, refund_flag=1):
        self.status = self.CANCELLED
        self.save()

        consumer_account = account_model.ConsumerAccount.objects.get_or_create(user=self.user)
        consumer_account = account_model.ConsumerAccount.objects.select_for_update().get(user=self.user)

        data = dict()
        data["reference_id"] = self.id
        data["user"] = self.user
        data["product_id"] = 1

        cancel_amount = self.effective_price
        consumer_account.credit_cancellation(data, cancel_amount)
        if refund_flag:
            ctx_obj = consumer_account.debit_refund()
            account_model.ConsumerRefund.initiate_refund(self.user, ctx_obj)

    def action_completed(self):
        self.status = self.COMPLETED
        self.save()
        if self.payment_type != OpdAppointment.INSURANCE:
            admin_obj, out_level = self.get_billable_admin_level()
            app_outstanding_fees = self.lab_payout_amount()
            Outstanding.create_outstanding(admin_obj, out_level, app_outstanding_fees)

        # if self.payment_type != self.INSURANCE:
        #     Outstanding.create_outstanding(self)

    def get_billable_admin_level(self):
        if self.lab.network and self.lab.network.is_billing_enabled:
            return self.lab.network, Outstanding.LAB_NETWORK_LEVEL
        else:
            return self.lab, Outstanding.LAB_LEVEL

    def lab_payout_amount(self):
        amount = 0
        if self.payment_type == OpdAppointment.COD:
            amount = (-1)*(self.effective_price - self.agreed_price)
        elif self.payment_type == OpdAppointment.PREPAID:
            amount = self.agreed_price

        return amount

    @classmethod
    def get_billing_summary(cls, user, req_data):
        month = req_data.get("month")
        year = req_data.get("year")
        payment_type = req_data.get("payment_type")
        out_level = req_data.get("outstanding_level")
        admin_id = req_data.get("admin_id")
        out_obj = Outstanding.objects.filter(outstanding_level=out_level, net_hos_doc_id=admin_id,
                                             outstanding_month=month, outstanding_year=year)
        start_date_time, end_date_time = get_start_end_datetime(month, year)
        lab_data = UserPermission.get_billable_doctor_hospital(user)
        lab_list = list()
        for data in lab_data:
            if data.get("lab"):
                lab_list.append(data["lab"])
        if payment_type in [OpdAppointment.COD, OpdAppointment.PREPAID]:
            payment_type = [OpdAppointment.COD, OpdAppointment.PREPAID]
        elif payment_type in [OpdAppointment.INSURANCE]:
            payment_type = [OpdAppointment.INSURANCE]
        queryset = (LabAppointment.objects.filter(status=OpdAppointment.COMPLETED,
                                                  time_slot_start__gte=start_date_time,
                                                  time_slot_start__lte=end_date_time,
                                                  payment_type__in=payment_type,
                                                  lab__in=lab_list, outstanding=out_obj))
        if payment_type != OpdAppointment.INSURANCE:
            tcp_condition = Case(When(payment_type=OpdAppointment.COD, then=F("effective_price")),
                                 When(~Q(payment_type=OpdAppointment.COD), then=0))
            tcs_condition = Case(When(payment_type=OpdAppointment.COD, then=F("agreed_price")),
                                 When(~Q(payment_type=OpdAppointment.COD), then=0))
            tpf_condition = Case(When(payment_type=OpdAppointment.PREPAID, then=F("agreed_price")),
                                 When(~Q(payment_type=OpdAppointment.PREPAID), then=0))
            queryset = queryset.values("lab").annotate(total_cash_payment=Sum(tcp_condition),
                                                       total_cash_share=Sum(tcs_condition),
                                                       total_online_payout=Sum(tpf_condition))

        return queryset

    @classmethod
    def get_billing_appointment(cls, user, req_data):
        month = req_data.get("month")
        year = req_data.get("year")
        payment_type = req_data.get("payment_type")
        out_level = req_data.get("outstanding_level")
        admin_id = req_data.get("admin_id")
        start_date_time, end_date_time = get_start_end_datetime(month, year)

        query_filter = dict()
        query_filter['user'] = user
        query_filter['write_permission'] = True
        query_filter['permission_type'] = UserPermission.BILLINNG
        if out_level == Outstanding.LAB_NETWORK_LEVEL:
            query_filter["lab_network"] = admin_id
        elif out_level == Outstanding.LAB_LEVEL:
            query_filter["lab"] = admin_id

        permission = LabUserPermission.objects.filter(**query_filter).exists()

        if payment_type in [OpdAppointment.COD, OpdAppointment.PREPAID]:
            payment_type = [OpdAppointment.COD, OpdAppointment.PREPAID]
        elif payment_type in [OpdAppointment.INSURANCE]:
            payment_type = [OpdAppointment.INSURANCE]

        queryset = None

        if permission:
            out_obj = Outstanding.objects.filter(outstanding_level=out_level, net_hos_doc_id=admin_id,
                                                 outstanding_month=month, outstanding_year=year)

            queryset = (LabAppointment.objects.filter(status=OpdAppointment.COMPLETED,
                                                      time_slot_start__gte=start_date_time,
                                                      time_slot_start__lte=end_date_time,
                                                      payment_type__in=payment_type,
                                                      outstanding=out_obj))

        return queryset
        # lab_data = UserPermission.get_billable_doctor_hospital(user)
        # lab_list = list()
        # for data in lab_data:
        #     if data.get("lab"):
        #         lab_list.append(data["lab"])
        # if payment_type in [OpdAppointment.COD, OpdAppointment.PREPAID]:
        #     payment_type = [OpdAppointment.COD, OpdAppointment.PREPAID]
        # elif payment_type in [OpdAppointment.INSURANCE]:
        #     payment_type = [OpdAppointment.INSURANCE]
        # queryset = (LabAppointment.objects.filter(status=OpdAppointment.COMPLETED,
        #                                           time_slot_start__gte=start_date_time,
        #                                           time_slot_start__lte=end_date_time,
        #                                           payment_type__in=payment_type,
        #                                           lab__in=lab_list))
        # return queryset

    def __str__(self):
        return self.profile.name + ', ' + self.lab.name

    class Meta:
        db_table = "lab_appointment"


class CommonTest(TimeStampedModel):
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='commontest')


class CommonDiagnosticCondition(TimeStampedModel):
    name = models.CharField(max_length=200)
    lab_test = models.ManyToManyField(
        LabTest,
        through='DiagnosticConditionLabTest',
        through_fields=('diagnostic_condition', 'lab_test'),
    )
    # test = models.ManyToManyField(LabTest)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "common_diagnostic_condition"


class DiagnosticConditionLabTest(TimeStampedModel):
    diagnostic_condition = models.ForeignKey(CommonDiagnosticCondition, on_delete=models.CASCADE)
    lab_test = models.ForeignKey(LabTest, on_delete=models.CASCADE)

    def __str__(self):
        return self.diagnostic_condition.name + " " + self.lab_test.name

    class Meta:
        db_table = "diagnostic_condition_labtest"


class PromotedLab(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)

    def __str__(self):
        return self.lab.name

    class Meta:
        db_table = "promoted_lab"


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
    SLOT_CHOICES = [("m", "Morning"), ("e", "Evening")]
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    is_male_available = models.BooleanField(verbose_name='Male', default=False)
    is_female_available = models.BooleanField(verbose_name='Female', default=False)
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
    EMAIL_CONFIRMATION = 9
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (REGISTRATION, "Registration Certificate"), (CHEQUE, "Cancel Cheque Copy"), (LOGO, "LOGO"),
               (EMAIL_CONFIRMATION, "Email Confirmation")]
    lab = models.ForeignKey(Lab, null=True, blank=True, default=None, on_delete=models.CASCADE,
                            related_name='lab_documents')
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='lab/images', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')

    # def __str__(self):
        # return self.name

    class Meta:
        db_table = "lab_document"


class LabNetworkDocument(TimeStampedModel, Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    REGISTRATION = 4
    CHEQUE = 5
    LOGO = 6
    EMAIL_CONFIRMATION = 9
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (REGISTRATION, "Registration Certificate"), (CHEQUE, "Cancel Cheque Copy"), (LOGO, "LOGO"),
               (EMAIL_CONFIRMATION, "Email Confirmation"),
               ]
    lab_network = models.ForeignKey(LabNetwork, null=True, blank=True, default=None, on_delete=models.CASCADE,
                            related_name='lab_documents')
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='lab_network/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')

    # def __str__(self):
        # return self.name

    class Meta:
        db_table = "lab_network_document"


class LabOnboardingToken(TimeStampedModel):
    GENERATED = 1
    REJECTED = 2
    CONSUMED = 3
    STATUS_CHOICES = [(GENERATED, "Generated"), (REJECTED, "Rejected"), (CONSUMED, "Consumed")]
    lab = models.ForeignKey(Lab, null=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    mobile = models.BigIntegerField(blank=True, null=True,
                                    validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    verified_token = models.CharField(max_length=100, null=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=GENERATED)

    class Meta:
        db_table = "lab_onboarding_token"

# Used to display pricing in admin
class LabPricing(Lab):
    class Meta:
        proxy = True
        default_permissions = []
