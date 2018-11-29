from django.contrib.gis.db import models
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from ondoc.authentication.models import (TimeStampedModel, CreatedByModel, Image, Document, QCModel, UserProfile, User,
                                         UserPermission, GenericAdmin, LabUserPermission, GenericLabAdmin, BillingAccount)
from ondoc.doctor.models import Hospital, SearchKey, CancellationReason
from ondoc.coupon.models import Coupon
from ondoc.notification import models as notification_models
from ondoc.notification import tasks as notification_tasks
from ondoc.notification.labnotificationaction import LabNotificationAction
from django.core.files.storage import get_storage_class
from ondoc.api.v1.utils import AgreedPriceCalculate, DealPriceCalculate, TimeSlotExtraction, CouponsMixin
from ondoc.account import models as account_model
from django.utils import timezone
from datetime import timedelta
from django.db.models import F, Sum, When, Case, Q
from django.db import transaction
from django.contrib.postgres.fields import JSONField
from ondoc.doctor.models import OpdAppointment
from ondoc.payout.models import Outstanding
from ondoc.authentication import models as auth_model
from django.core.files.uploadedfile import InMemoryUploadedFile
from io import BytesIO
import datetime
from ondoc.api.v1.utils import get_start_end_datetime, custom_form_datetime
from ondoc.diagnostic import tasks
from dateutil import tz
from django.conf import settings
import logging
import decimal
from PIL import Image as Img
import math
import random
import os
from ondoc.insurance import models as insurance_model
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.matrix.tasks import push_appointment_to_matrix
from ondoc.location import models as location_models
from ondoc.ratings_review import models as ratings_models
from decimal import Decimal
import reversion

logger = logging.getLogger(__name__)


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

                # AvailableLabTest.objects. \
                #     filter(lab_pricing_group__id=id, test__test_type=LabTest.PATHOLOGY). \
                #     update(
                #     computed_deal_price=DealPriceCalculate(F('mrp'), F('computed_agreed_price'), path_deal_price_prcnt))
                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.PATHOLOGY). \
                    update(
                    computed_deal_price=F('computed_agreed_price'))

            if not original.radiology_agreed_price_percentage == self.radiology_agreed_price_percentage \
                    or not original.radiology_deal_price_percentage == self.radiology_deal_price_percentage:
                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.RADIOLOGY). \
                    update(computed_agreed_price=AgreedPriceCalculate(F('mrp'), rad_agreed_price_prcnt))

                # AvailableLabTest.objects. \
                #     filter(lab_pricing_group__id=id, test__test_type=LabTest.RADIOLOGY). \
                #     update(
                #     computed_deal_price=DealPriceCalculate(F('mrp'), F('computed_agreed_price'), rad_deal_price_prcnt))
                AvailableLabTest.objects. \
                    filter(lab_pricing_group__id=id, test__test_type=LabTest.RADIOLOGY). \
                    update(
                    computed_deal_price=F('computed_agreed_price'))

class LabTestPricingGroup(LabPricingGroup):

    class Meta:
        proxy = True
        default_permissions = []


class HomePickupCharges(models.Model):
    home_pickup_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    distance = models.PositiveIntegerField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()


class Lab(TimeStampedModel, CreatedByModel, QCModel, SearchKey):
    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"),
                         (ONBOARDED, "Onboarded")]
    name = models.CharField(max_length=200)
    about = models.CharField(max_length=1000, blank=True)
    license = models.CharField(max_length=200, blank=True)
    is_insurance_enabled = models.BooleanField(verbose_name='Enabled for Insurance Customer',default=False)
    is_retail_enabled = models.BooleanField(verbose_name= 'Enabled for Retail Customer', default=False)
    is_ppc_pathology_enabled = models.BooleanField(verbose_name= 'Enabled for Pathology Pre Policy Checkup', default=False)
    is_ppc_radiology_enabled = models.BooleanField(verbose_name= 'Enabled for Radiology Pre Policy Checkup', default=False)
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)
    onboarding_status = models.PositiveSmallIntegerField(default=NOT_ONBOARDED, choices=ONBOARDING_STATUS)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    primary_email = models.EmailField(max_length=100, blank=True)
    primary_mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True,  validators=[MinValueValidator(1800)])
    parking = models.PositiveSmallIntegerField(blank=True, null=True,
                                               choices=[("", "Select"), (1, "Easy"), (2, "Difficult")])
    always_open = models.BooleanField(verbose_name='Is lab open 24X7', default=False)
    hospital = models.ForeignKey(Hospital, blank=True, null=True, on_delete=models.SET_NULL)
    network_type = models.PositiveSmallIntegerField(blank=True, null=True,
                                                    choices=[("", "Select"), (1, "Non Network Lab"),
                                                             (2, "Network Lab")])
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
    agreed_rate_list = models.FileField(upload_to='lab/docs', max_length=200, null=True, blank=True,
                                        validators=[FileExtensionValidator(allowed_extensions=['pdf', 'xls', 'xlsx'])],
                                        help_text='Supported formats : pdf, xls, xlsx')
    ppc_rate_list = models.FileField(upload_to='lab/docs', max_length=200, null=True, blank=True,
                                    validators=[FileExtensionValidator(allowed_extensions=['pdf', 'xls', 'xlsx'])],
                                     help_text='Supported formats : pdf, xls, xlsx')
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
    is_home_collection_enabled = models.BooleanField(default=False)
    home_pickup_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    is_live = models.BooleanField(verbose_name='Is Live', default=False)
    live_at = models.DateTimeField(null=True, blank=True)
    is_test_lab = models.BooleanField(verbose_name='Is Test Lab', default=False)
    billing_merchant = GenericRelation(BillingAccount)
    home_collection_charges = GenericRelation(HomePickupCharges)
    entity = GenericRelation(location_models.EntityLocationRelationship)
    rating = GenericRelation(ratings_models.RatingsReview)
    enabled = models.BooleanField(verbose_name='Is Enabled', default=True, blank=True)
    booking_closing_hours_from_dayend = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    order_priority = models.PositiveIntegerField(blank=True, null=True, default=0)
    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab"

    def get_ratings(self):
        return self.rating.all()

    def get_thumbnail(self):
        all_documents = self.lab_documents.all()
        for document in all_documents:
            if document.document_type == LabDocument.LOGO:
                return document.get_thumbnail_path(document.name.url, '90x60')
        return None
        # return static('lab_images/lab_default.png')

    def get_lab_address(self):
        address = []

        if self.building:
            address.append(self.ad_str(self.building))
        if self.sublocality:
            address.append(self.ad_str(self.sublocality))
        if self.locality:
            address.append(self.ad_str(self.locality))
        if self.city:
            address.append(self.ad_str(self.city))
        # if self.state:
        #     address.append(self.ad_str(self.state))
        # if self.country:
        #     address.append(self.ad_str(self.country))
        result = []
        ad_uinq = set()
        for ad in address:
            ad_lc = ad.lower()
            if ad_lc not in ad_uinq:
                ad_uinq.add(ad_lc)
                result.append(ad)

        return ", ".join(result)

    def ad_str(self, string):
        return str(string).strip().replace(',', '')

    def update_live_status(self):

        if not self.is_live and (self.onboarding_status == self.ONBOARDED and self.data_status == self.QC_APPROVED and self.enabled == True):
            self.is_live = True
            if not self.live_at:
                self.live_at = datetime.datetime.now()

        if self.is_live and (self.onboarding_status != self.ONBOARDED or self.data_status != self.QC_APPROVED or self.enabled == False):
            self.is_live = False

    def save(self, *args, **kwargs):
        self.clean()

        edit_instance = None
        if self.id is not None:
            edit_instance = 1
            original = Lab.objects.get(pk=self.id)

        self.update_live_status()
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
        return self.name

    class Meta:
        db_table = "lab_certification"


class LabAccreditation(TimeStampedModel):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

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
    OTHER =1
    SPOC = 2
    MANAGER = 3
    OWNER = 4
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    CONTACT_TYPE_CHOICES = [(OTHER, "Other"), (SPOC, "Single Point of Contact"), (MANAGER, "Manager"), (OWNER, "Owner")]
    contact_type = models.PositiveSmallIntegerField(
        choices=CONTACT_TYPE_CHOICES)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_manager"


class LabImage(TimeStampedModel, Image):
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='lab_image')
    name = models.ImageField(upload_to='lab/images', height_field='height', width_field='width')

    class Meta:
        db_table = "lab_image"


class LabBookingClosingManager(models.Manager):

    def lab_booking_slots(self, *args, **kwargs):

        is_home_pickup = kwargs.get("for_home_pickup", False)

        if is_home_pickup:
            kwargs["lab__is_home_collection_enabled"] = is_home_pickup
        lab_timing_queryset = LabTiming.timing_manager.filter(**kwargs)

        if not lab_timing_queryset or (is_home_pickup and not lab_timing_queryset[0].lab.is_home_collection_enabled):
            return {
                "time_slots": [],
                "today_min": None,
                "tomorrow_min": None,
                "today_max": None
            }

        else:
            obj = TimeSlotExtraction()
            threshold = lab_timing_queryset[0].lab.booking_closing_hours_from_dayend

            if not is_home_pickup and lab_timing_queryset[0].lab.always_open:
                for day in range(0, 7):
                    obj.form_time_slots(day, 0.0, 23.75, None, True)

            else:
                for data in lab_timing_queryset:
                    obj.form_time_slots(data.day, data.start, data.end, None, True)
                # daywise_data_array = sorted(lab_timing_queryset, key=lambda k: [k.day, k.start], reverse=True)
                # day, end = daywise_data_array[0].day, daywise_data_array[0].end
                # end = end - threshold
                # for data in daywise_data_array:
                #     if data.day != day:
                #         day = data.day
                #         end = data.end - threshold
                #     if not end <= data.start <= data.end:
                #         if data.start <= end <= data.end:
                #             data.end = end
                #         obj.form_time_slots(data.day, data.start, data.end, None, True)

            resp_list = obj.get_timing_list()
            is_thyrocare = False
            lab_id = kwargs.get("lab__id", None)
            if lab_id and settings.THYROCARE_NETWORK_ID:
                if Lab.objects.filter(id=lab_id, network_id=settings.THYROCARE_NETWORK_ID).exists():
                    is_thyrocare = True

            today_min, tomorrow_min, today_max = obj.initial_start_times(is_thyrocare=is_thyrocare, is_home_pickup=is_home_pickup, time_slots=resp_list)
            res_data = {
                "time_slots": resp_list,
                "today_min": today_min,
                "tomorrow_min": tomorrow_min,
                "today_max": today_max
            }

            return res_data


class LabTiming(TimeStampedModel):

    TIME_CHOICES = [(5.0, "5 AM"), (5.5, "5:30 AM"),
                    (6.0, "6 AM"), (6.5, "6:30 AM"),
                    (7.0, "7 AM"), (7.5, "7:30 AM"),
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
                    (22.0, "10 PM"), (22.5, "10:30 PM"),
                    (23.0, "11 PM"), (23.5, "11:30 PM")]

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='lab_timings')

    for_home_pickup = models.BooleanField(default=False)
    day = models.PositiveSmallIntegerField(blank=False, null=False,
                                           choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
                                                    (4, "Friday"), (5, "Saturday"), (6, "Sunday")])
    start = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    end = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)

    objects = models.Manager()  #default manager
    timing_manager = LabBookingClosingManager()

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
    billing_merchant = GenericRelation(BillingAccount)
    home_collection_charges = GenericRelation(HomePickupCharges)
    spoc_details = GenericRelation(auth_model.SPOCDetails)


    def all_associated_labs(self):
        if self.id:
            return self.lab_set.all()
        return None


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


class TestParameter(TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)
    # lab_test = models.ForeignKey('LabTest', on_delete=models.DO_NOTHING, null=True, blank=True)

    class Meta:
        db_table = "test_parameter"

    def __str__(self):
        return "{}".format(self.name)


class ParameterLabTest(TimeStampedModel):
    parameter = models.ForeignKey(TestParameter, on_delete=models.CASCADE, related_name='test_parameters')
    lab_test = models.ForeignKey('LabTest', on_delete=models.CASCADE, related_name='labtests')

    class Meta:
        db_table = 'parameter_lab_test'
        unique_together = (("parameter", "lab_test"), )

    def __str__(self):
        return "{}".format(self.parameter.name)


class LabTest(TimeStampedModel, SearchKey):
    RADIOLOGY = 1
    PATHOLOGY = 2
    OTHER = 3
    TEST_TYPE_CHOICES = (
        (RADIOLOGY, "Radiology"),
        (PATHOLOGY, "Pathology"),
        (OTHER, 'Other')
    )
    name = models.CharField(max_length=200, unique=True)
    synonyms = models.CharField(max_length=4000, null=True, blank=True)
    test_type = models.PositiveIntegerField(choices=TEST_TYPE_CHOICES, blank=True, null=True)
    is_package = models.BooleanField(verbose_name= 'Is this test package type?')
    number_of_tests = models.PositiveIntegerField(blank=True, null=True)
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
    test = models.ManyToManyField('self', through='LabTestPackage', symmetrical=False,
                                  through_fields=('package', 'lab_test'))  # self reference
    parameter = models.ManyToManyField(
        'TestParameter', through=ParameterLabTest,
        through_fields=('lab_test', 'parameter')
    )
    approximate_duration = models.CharField(max_length=50, default='15 mins', verbose_name='What is the approximate duration for the test?')
    report_schedule = models.CharField(max_length=150, default='After 2 days of test.', verbose_name='What is the report schedule for the test?')
    enable_for_ppc = models.BooleanField(default=False)
    enable_for_retail = models.BooleanField(default=False)
    hide_price = models.BooleanField(default=False)
    searchable = models.BooleanField(default=True)

    # test_sub_type = models.ManyToManyField(
    #     LabTestSubType,
    #     through='LabTestSubTypeMapping',
    #     through_fields=("lab_test", "test_sub_type", )
    # )

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_test"


class LabTestPackage(TimeStampedModel):
    package = models.ForeignKey(LabTest, related_name='packages', on_delete=models.CASCADE)
    lab_test = models.ForeignKey(LabTest, related_name='lab_tests', on_delete=models.CASCADE)

    def __str__(self):
        return "{}-{}".format(self.package.name, self.lab_test.name)

    class Meta:
        db_table = 'labtest_package'
        unique_together = (("package", "lab_test"))


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
    rating = GenericRelation(ratings_models.RatingsReview)


    def get_testid(self):
        return self.test.id

    def get_type(self):
        return self.test.test_type

    def save(self, *args, **kwargs):
        if self.mrp:
            self.computed_agreed_price = self.get_computed_agreed_price()
            # self.computed_deal_price = self.get_computed_deal_price()
            self.computed_deal_price = self.computed_agreed_price

        super(AvailableLabTest, self).save(*args, **kwargs)

    def get_computed_deal_price(self):
        if self.test.test_type == LabTest.RADIOLOGY:
            deal_percent = self.lab_pricing_group.radiology_deal_price_percentage if self.lab_pricing_group.radiology_deal_price_percentage else None
        else:
            deal_percent = self.lab_pricing_group.pathology_deal_price_percentage if self.lab_pricing_group.pathology_deal_price_percentage else None
        mrp = decimal.Decimal(self.mrp)
        computed_agreed_price = self.computed_agreed_price
        if deal_percent is not None:
            price = math.ceil(mrp * (deal_percent / 100))
            # ceil to next 10 and subtract 1 so it end with a 9
            price = math.ceil(price / 10.0) * 10 - 1
            if price > mrp:
                price = mrp
            if computed_agreed_price is not None:
                if price < computed_agreed_price:
                    price = computed_agreed_price
            return price
        else:
            return None

    def get_computed_agreed_price(self):
        if self.test.test_type == LabTest.RADIOLOGY:
            agreed_percent = self.lab_pricing_group.radiology_agreed_price_percentage if self.lab_pricing_group.radiology_agreed_price_percentage else None
        else:
            agreed_percent = self.lab_pricing_group.pathology_agreed_price_percentage if self.lab_pricing_group.pathology_agreed_price_percentage else None
        mrp = decimal.Decimal(self.mrp)

        if agreed_percent is not None:
            price = math.ceil(mrp * (agreed_percent / 100))
            if price > mrp:
                price = mrp
            return price
        else:
            return None

    # def __str__(self):
    #     return "{}".format(self.test.name)

    class Meta:
        unique_together = (("test", "lab_pricing_group"))
        db_table = "available_lab_test"

@reversion.register()
class LabAppointment(TimeStampedModel, CouponsMixin):
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_LAB = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7
    ACTIVE_APPOINTMENT_STATUS = [BOOKED, ACCEPTED, RESCHEDULED_PATIENT, RESCHEDULED_LAB]
    STATUS_CHOICES = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                      (RESCHEDULED_LAB, 'Rescheduled by lab'),
                      (RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                      (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                      (COMPLETED, 'Completed')]
    PATIENT_CANCELLED = 1
    AGENT_CANCELLED = 2
    AUTO_CANCELLED = 3
    CANCELLATION_TYPE_CHOICES = [(PATIENT_CANCELLED, 'Patient Cancelled'), (AGENT_CANCELLED, 'Agent Cancelled'),
                                 (AUTO_CANCELLED, 'Auto Cancelled')]

    lab = models.ForeignKey(Lab, on_delete=models.SET_NULL, related_name='labappointment', null=True)
    lab_test = models.ManyToManyField(AvailableLabTest)
    profile = models.ForeignKey(UserProfile, related_name="labappointments", on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='lab_appointments')
    profile_detail = JSONField(blank=True, null=True)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)
    cancellation_type = models.PositiveSmallIntegerField(choices=CANCELLATION_TYPE_CHOICES, blank=True, null=True)
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
    home_pickup_charges = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    matrix_lead_id = models.IntegerField(null=True)
    is_rated = models.BooleanField(default=False)
    rating_declined = models.BooleanField(default=False)
    coupon = models.ManyToManyField(Coupon, blank=True, null=True, related_name="lab_appointment_coupon")
    discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cancellation_reason = models.ForeignKey(CancellationReason, on_delete=models.SET_NULL, null=True, blank=True)
    cancellation_comments = models.CharField(max_length=5000, null=True, blank=True)

    def get_reports(self):
        return self.reports.all()

    def allowed_action(self, user_type, request):
        allowed = []
        current_datetime = timezone.now()
        if user_type == User.CONSUMER and current_datetime <= self.time_slot_start:
            if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_LAB, self.RESCHEDULED_PATIENT):
                allowed = [self.RESCHEDULED_PATIENT, self.CANCELLED]
        if user_type == User.DOCTOR and self.time_slot_start.date() >= current_datetime.date():
            perm_queryset = auth_model.GenericLabAdmin.objects.filter(is_disabled=False, user=request.user)
            if perm_queryset.first():
                doc_permission = perm_queryset.first()
                if doc_permission.write_permission or doc_permission.super_user_permission:
                    if self.status in [self.BOOKED, self.RESCHEDULED_PATIENT]:
                        allowed = [self.ACCEPTED, self.RESCHEDULED_LAB]
                    elif self.status == self.ACCEPTED:
                        allowed = [self.RESCHEDULED_LAB, self.COMPLETED]
                    elif self.status == self.RESCHEDULED_LAB:
                        allowed = [self.ACCEPTED]

            # if self.status in [self.BOOKED]:
            #     allowed = [self.COMPLETED]
        return allowed

    def is_to_send_notification(self, database_instance):
        if not database_instance:
            return True
        if database_instance.status != self.status:
            return True
        if (database_instance.status == self.status
                and database_instance.time_slot_start != self.time_slot_start
                and database_instance.status in [LabAppointment.RESCHEDULED_LAB, LabAppointment.RESCHEDULED_PATIENT]
                and self.status in [LabAppointment.RESCHEDULED_LAB, LabAppointment.RESCHEDULED_PATIENT]):
            return True
        return False

    def get_lab_admins(self):
        if self.lab.network and self.lab.network.manageable_lab_network_admins.filter(is_disabled=False).exists():
            return [admin.user for admin in self.lab.network.manageable_lab_network_admins.filter(is_disabled=False)
                    if admin.user]
        else:
            return [admin.user for admin in self.lab.manageable_lab_admins.filter(is_disabled=False)
                    if admin.user]

    def app_commit_tasks(self, old_instance, push_to_matrix):
        if push_to_matrix:
            # Push the appointment data to the matrix
            push_appointment_to_matrix.apply_async(({'type': 'LAB_APPOINTMENT', 'appointment_id': self.id, 'product_id':5,
                                                     'sub_product_id': 2}, ), countdown=5)

        if self.is_to_send_notification(old_instance):
            notification_tasks.send_lab_notifications.apply_async(kwargs={'appointment_id': self.id}, countdown=1)

        if not old_instance or old_instance.status != self.status:
            notification_models.EmailNotification.ops_notification_alert(self, email_list=settings.OPS_EMAIL_ID,
                                                                         product=account_model.Order.LAB_PRODUCT_ID,
                                                                         alert_type=notification_models.EmailNotification.OPS_APPOINTMENT_NOTIFICATION)
        if self.status == self.COMPLETED and not self.is_rated:
            notification_tasks.send_opd_rating_message.apply_async(kwargs={'appointment_id': self.id, 'type': 'lab'}, countdown=int(settings.RATING_SMS_NOTIF))
        # Do not delete below commented code
        # try:
        #     prev_app_dict = {'id': self.id,
        #                      'status': self.status,
        #                      "updated_at": int(self.updated_at.timestamp())}
        #     if prev_app_dict['status'] not in [LabAppointment.COMPLETED, LabAppointment.CANCELLED, LabAppointment.ACCEPTED]:
        #         countdown = self.get_auto_cancel_delay(self)
        #         tasks.lab_app_auto_cancel.apply_async((prev_app_dict, ), countdown=countdown)
        # except Exception as e:
        #     logger.error("Error in auto cancel flow - " + str(e))
        print('all lab appointment tasks completed')

    def get_pickup_address(self):
        if not self.address:
            return ""
        address_string = ""
        address_dict = dict()
        if not isinstance(self.address, dict):
            address_dict = vars(address_dict)
        else:
            address_dict = self.address

        if address_dict.get("address"):
            if address_string:
                address_string += ", "
            address_string += str(address_dict["address"])
        if address_dict.get("land_mark"):
            if address_string:
                address_string += ", "
            address_string += str(address_dict["land_mark"])
        if address_dict.get("locality"):
            if address_string:
                address_string += ", "
            address_string += str(address_dict["locality"])
        if address_dict.get("pincode"):
            if address_string:
                address_string += ", "
            address_string += str(address_dict["pincode"])
        return address_string

    def save(self, *args, **kwargs):
        database_instance = LabAppointment.objects.filter(pk=self.id).first()
        if database_instance and (database_instance.status == self.COMPLETED or database_instance.status == self.CANCELLED):
            raise Exception('Cancelled or Completed appointment cannot be saved')

        try:
            if (self.payment_type != OpdAppointment.INSURANCE and self.status == self.COMPLETED and
                    (not database_instance or database_instance.status != self.status) and not self.outstanding):
                out_obj = self.outstanding_create()
                self.outstanding = out_obj
        except:
            pass

        push_to_matrix = kwargs.get('push_again_to_matrix', True)
        if 'push_again_to_matrix' in kwargs.keys():
            kwargs.pop('push_again_to_matrix')

        super().save(*args, **kwargs)

        transaction.on_commit(lambda: self.app_commit_tasks(database_instance, push_to_matrix))

    def get_auto_cancel_delay(self, app_obj):
        delay = settings.AUTO_CANCEL_LAB_DELAY * 60
        to_zone = tz.gettz(settings.TIME_ZONE)
        app_updated_time = app_obj.updated_at.astimezone(to_zone)
        if app_obj.is_home_pickup:
            morning_time = "10:00:00"  # In IST
            evening_time = "17:00:00"  # In IST
        else:
            morning_time = "09:00:00"  # In IST
            evening_time = "18:00:00"  # In IST
        present_day_end = custom_form_datetime(evening_time, to_zone)
        next_day_start = custom_form_datetime(morning_time, to_zone, diff_days=1)
        time_diff = next_day_start - app_updated_time

        if present_day_end - timedelta(minutes=settings.AUTO_CANCEL_LAB_DELAY) < app_updated_time < next_day_start:
            return time_diff.seconds
        else:
            return delay

    @classmethod
    def create_appointment(cls, appointment_data):
        otp = random.randint(1000, 9999)
        appointment_data["payment_status"] = OpdAppointment.PAYMENT_ACCEPTED
        appointment_data["status"] = OpdAppointment.BOOKED
        appointment_data["otp"] = otp
        lab_ids = appointment_data.pop("lab_test")
        coupon_list = appointment_data.pop("coupon", None)
        appointment_data.pop("extra_details", None)
        app_obj = cls.objects.create(**appointment_data)
        app_obj.lab_test.add(*lab_ids)
        if coupon_list:
            app_obj.coupon.add(*coupon_list)
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

    @transaction.atomic
    def action_cancelled(self, refund_flag=1):

        # Taking Lock first
        consumer_account = None
        if self.payment_type == OpdAppointment.PREPAID:
            temp_list = account_model.ConsumerAccount.objects.get_or_create(user=self.user)
            consumer_account = account_model.ConsumerAccount.objects.select_for_update().get(user=self.user)

        old_instance = LabAppointment.objects.get(pk=self.id)
        if old_instance.status != self.CANCELLED:
            self.status = self.CANCELLED
            self.save()
            product_id = account_model.Order.LAB_PRODUCT_ID

            if self.payment_type == OpdAppointment.PREPAID and account_model.ConsumerTransaction.valid_appointment_for_cancellation(
                    self.id, product_id):
                cancel_amount = self.effective_price
                consumer_account.credit_cancellation(self, account_model.Order.LAB_PRODUCT_ID, cancel_amount)
                if refund_flag:
                    ctx_obj = consumer_account.debit_refund()
                    account_model.ConsumerRefund.initiate_refund(self.user, ctx_obj)

    def action_completed(self):
        self.status = self.COMPLETED
        out_obj = None
        if self.payment_type != OpdAppointment.INSURANCE:
            if not self.outstanding:
                out_obj = self.outstanding_create()
                self.outstanding = out_obj
        self.save()

    def outstanding_create(self):
        admin_obj, out_level = self.get_billable_admin_level()
        app_outstanding_fees = self.lab_payout_amount()
        out_obj = Outstanding.create_outstanding(admin_obj, out_level, app_outstanding_fees)
        return out_obj

        # self.status = self.COMPLETED
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
            amount = (-1)*(self.effective_price - self.agreed_price - self.home_pickup_charges)
        elif self.payment_type == OpdAppointment.PREPAID:
            amount = self.agreed_price + self.home_pickup_charges
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

        if payment_type in [OpdAppointment.COD, OpdAppointment.PREPAID]:
            payment_type = [OpdAppointment.COD, OpdAppointment.PREPAID]
        elif payment_type in [OpdAppointment.INSURANCE]:
            payment_type = [OpdAppointment.INSURANCE]

        queryset = (LabAppointment.objects.filter(outstanding=out_obj, status=cls.COMPLETED,
                                                  time_slot_start__gte=start_date_time,
                                                  time_slot_start__lte=end_date_time,
                                                  payment_type__in=payment_type))
        if payment_type != OpdAppointment.INSURANCE:
            tcp_condition = Case(When(payment_type=OpdAppointment.COD, then=F("effective_price")),
                                 When(~Q(payment_type=OpdAppointment.COD), then=0))
            tcs_condition = Case(When(payment_type=OpdAppointment.COD, then=F("agreed_price")+F("home_pickup_charges")),
                                 When(~Q(payment_type=OpdAppointment.COD), then=0))
            tpf_condition = Case(When(payment_type=OpdAppointment.PREPAID, then=F("agreed_price")+F("home_pickup_charges")),
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
        return "{}, {}".format(self.profile.name if self.profile else "", self.lab.name)

    class Meta:
        db_table = "lab_appointment"


class CommonTest(TimeStampedModel):
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='commontest')
    icon = models.ImageField(upload_to='diagnostic/common_test_icons', null=True)

    def __str__(self):
        return "{}-{}".format(self.test.name, self.id)


class CommonPackage(TimeStampedModel):
    package = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='commonpackage')
    icon = models.ImageField(upload_to='diagnostic/common_package_icons', null=True)

    def __str__(self):
        return "{}-{}".format(self.package.name, self.id)

    class Meta:
        db_table = 'common_package'


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

    # def __str__(self):
    #     return self.lab.name

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
    image_sizes = [(90, 60), ]
    image_base_path = 'lab/images'
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (REGISTRATION, "Registration Certificate"), (CHEQUE, "Cancel Cheque Copy"), (LOGO, "LOGO"),
               (EMAIL_CONFIRMATION, "Email Confirmation")]
    lab = models.ForeignKey(Lab, null=True, blank=True, default=None, on_delete=models.CASCADE,
                            related_name='lab_documents')
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='lab/images', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def __str__(self):
        if self.document_type:
            return '{}'.format(dict(LabDocument.CHOICES)[self.document_type])
        return None

    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')

    def resize_image(self, width, height):
        default_storage_class = get_storage_class()
        storage_instance = default_storage_class()

        path = self.get_thumbnail_path(self.name.name,"{}x{}".format(width, height))
        if storage_instance.exists(path):
            return
        if self.name.closed:
            self.name.open()

        with Img.open(self.name) as img:
            img = img.copy()


                #path = "{}/{}/{}x{}/".format(settings.MEDIA_ROOT, LabDocument.image_base_path, height, width)
                # if os.path.exists(path+os.path.basename(self.name.name)):
                #     return
                # if not os.path.exists(path):
                #     os.mkdir(path)
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
                #storage_instance.save(path + os.path.basename(self.name.name), in_memory_file)
                # img.save(path + os.path.basename(self.name.name), 'JPEG')

    def create_all_images(self):
        if not self.name:
            return
        for size in LabDocument.image_sizes:
            width = size[0]
            height = size[1]
            self.resize_image(width, height)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.document_type == LabDocument.LOGO:
            self.create_all_images()


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


class LabReport(auth_model.TimeStampedModel):
    appointment = models.ForeignKey(LabAppointment, related_name='reports', on_delete=models.CASCADE)
    report_details = models.TextField(max_length=300, blank=True, null=True)

    def __str__(self):
        return "{}-{}".format(self.id, self.appointment.id)

    class Meta:
        db_table = "lab_report"


class LabReportFile(auth_model.TimeStampedModel, auth_model.Document):
    report = models.ForeignKey(LabReport, related_name='files', on_delete=models.SET_NULL, null=True, blank=True)
    name = models.FileField(upload_to='lab_reports/', blank=False, null=False, validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def __str__(self):
        return "{}-{}".format(self.id, self.report.id)

    def send_notification(self, database_instance):
        appointment = self.report.appointment
        if not appointment.user:
            return
        if not database_instance:
            LabNotificationAction.trigger(
                instance=appointment,
                user=appointment.user,
                notification_type=notification_models.NotificationAction.LAB_REPORT_UPLOADED,
            )

    def save(self, *args, **kwargs):
        database_instance = LabReportFile.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        #self.send_notification(database_instance)

    class Meta:
        db_table = "lab_report_file"


class LabTestGroup(auth_model.TimeStampedModel):
    TEST_TYPE_CHOICES = LabTest.TEST_TYPE_CHOICES
    name = models.CharField(max_length=200)
    tests = models.ManyToManyField(LabTest)
    type = models.PositiveSmallIntegerField(choices=TEST_TYPE_CHOICES)

    class Meta:
        db_table = 'lab_test_group'

