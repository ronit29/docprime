from collections import OrderedDict
from copy import deepcopy

import pytz
from django.contrib.gis.db import models
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.template.loader import render_to_string
# from hardcopy import bytestring_to_pdf

from ondoc.account.models import MerchantPayout, ConsumerAccount, Order, UserReferred, MoneyPool, Invoice
from ondoc.authentication.models import (TimeStampedModel, CreatedByModel, Image, Document, QCModel, UserProfile, User,
                                         UserPermission, GenericAdmin, LabUserPermission, GenericLabAdmin,
                                         BillingAccount, SPOCDetails, RefundMixin, WelcomeCallingDone,
                                         MerchantTdsDeduction, PaymentMixin, TransactionMixin)
from ondoc.bookinganalytics.models import DP_OpdConsultsAndTests
from ondoc.doctor.models import Hospital, SearchKey, CancellationReason, Doctor
from ondoc.crm.constants import constants
from ondoc.coupon.models import Coupon
from ondoc.location.models import EntityUrls, UrlsModel
from ondoc.notification import models as notification_models
from ondoc.notification import tasks as notification_tasks
from ondoc.notification.labnotificationaction import LabNotificationAction
from django.core.files.storage import get_storage_class
from ondoc.api.v1.utils import AgreedPriceCalculate, DealPriceCalculate, TimeSlotExtraction, CouponsMixin, \
    form_time_slot, util_absolute_url, html_to_pdf, RawSql, resolve_address
from ondoc.account import models as account_model
from django.utils import timezone
from datetime import timedelta
from django.db.models import F, Sum, When, Case, Q, Avg
from django.db import transaction
from django.contrib.postgres.fields import JSONField
from ondoc.doctor.models import OpdAppointment
from ondoc.notification.models import EmailNotification, NotificationAction
from ondoc.payout.models import Outstanding
from ondoc.authentication import models as auth_model
from django.core.files.uploadedfile import InMemoryUploadedFile, TemporaryUploadedFile
from io import BytesIO
import datetime
from datetime import date
from ondoc.api.v1.utils import get_start_end_datetime, custom_form_datetime
from ondoc.diagnostic import tasks
from ondoc.authentication.models import UserProfile, Address
from dateutil import tz, relativedelta
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
from ondoc.matrix.tasks import push_appointment_to_matrix, push_onboarding_qcstatus_to_matrix, \
    create_ipd_lead_from_lab_appointment, create_or_update_lead_on_matrix
from ondoc.integrations.task import push_lab_appointment_to_integrator, get_integrator_order_status, \
    push_appointment_to_spo
from ondoc.location import models as location_models
from ondoc.plus.enums import UtilizationCriteria
from ondoc.plus.models import PlusAppointmentMapping, PlusPlans
from ondoc.plus.usage_criteria import get_class_reference, get_price_reference
from ondoc.ratings_review import models as ratings_models
# from ondoc.api.v1.common import serializers as common_serializers
from ondoc.common.models import AppointmentHistory, AppointmentMaskNumber, Remark, GlobalNonBookable, \
    SyncBookingAnalytics, CompletedBreakupMixin, RefundDetails, MatrixMappedState, \
    MatrixMappedCity, TdsDeductionMixin, MatrixDataMixin, MerchantPayoutMixin, Fraud, SearchCriteria, Certifications, GenericPrescriptionFile
import reversion
from decimal import Decimal
from django.utils.text import slugify
from django.utils.functional import cached_property
#from ondoc.api.v1.diagnostic import serializers as diagnostic_serializers
from ondoc.common.helper import Choices
from ondoc.plus import models as plus_model

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


class Lab(TimeStampedModel, CreatedByModel, QCModel, SearchKey, WelcomeCallingDone, auth_model.SoftDelete, UrlsModel):
    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"),
                         (ONBOARDED, "Onboarded")]
    INCORRECT_CONTACT_DETAILS = 1
    MOU_AGREEMENT_NEEDED = 2
    LAB_NOT_INTERESTED = 3
    CHARGES_ISSUES = 4
    DUPLICATE = 5
    OTHERS = 9
    PHONE_RINGING_BUT_COULD_NOT_CONNECT = 10
    DISABLED_REASONS_CHOICES = (
        ("", "Select"), (INCORRECT_CONTACT_DETAILS, "Incorrect contact details"),
        (MOU_AGREEMENT_NEEDED, "MoU agreement needed"), (LAB_NOT_INTERESTED, "Lab not interested for tie-up"),
        (CHARGES_ISSUES, "Issue in discount % / charges"),
        (PHONE_RINGING_BUT_COULD_NOT_CONNECT, "Phone ringing but could not connect"),
        (DUPLICATE, "Duplicate"), (OTHERS, "Others (please specify)"))
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
    network = models.ForeignKey('LabNetwork', null=True, blank=True, on_delete=models.SET_NULL, related_name='lab')
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    matrix_state = models.ForeignKey(MatrixMappedState, null=True, blank=False, on_delete=models.DO_NOTHING,
                                     related_name='labs_in_state', verbose_name='State')
    matrix_city = models.ForeignKey(MatrixMappedCity, null=True, blank=False, on_delete=models.DO_NOTHING,
                                    related_name='labs_in_city', verbose_name='City')
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
    rating = GenericRelation(ratings_models.RatingsReview, related_query_name='lab_ratings')
    enabled = models.BooleanField(verbose_name='Is Enabled', default=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_after = models.PositiveIntegerField(null=True, blank=True, choices=Hospital.DISABLED_AFTER_CHOICES)
    disable_reason = models.PositiveIntegerField(null=True, blank=True, choices=DISABLED_REASONS_CHOICES)
    disable_comments = models.CharField(max_length=500, blank=True)
    disabled_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="disabled_lab", null=True,
                                    editable=False,
                                    on_delete=models.SET_NULL)
    booking_closing_hours_from_dayend = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0.00'))])
    order_priority = models.PositiveIntegerField(blank=True, null=True, default=0)
    merchant = GenericRelation(auth_model.AssociatedMerchant)
    merchant_payout = GenericRelation(account_model.MerchantPayout)
    avg_rating = models.DecimalField(max_digits=5, decimal_places=2, null=True, editable=False)
    lab_priority = models.PositiveIntegerField(blank=False, null=False, default=1)
    open_for_communication = models.BooleanField(default=True)
    remark = GenericRelation(Remark)
    rating_data = JSONField(blank=True, null=True)
    is_location_verified = models.BooleanField(verbose_name='Location Verified', default=False)
    auto_ivr_enabled = models.BooleanField(default=True)
    search_distance = models.FloatField(default=20000)
    is_ipd_lab = models.BooleanField(default=False)
    related_hospital = models.ForeignKey(Hospital, null=True, blank=True, on_delete=models.SET_NULL, related_name='ipd_hospital')
    enabled_for_plus_plans = models.NullBooleanField()
    is_b2b = models.BooleanField(default=False)
    center_visit = models.NullBooleanField()
    search_url_locality_radius = models.FloatField(blank=True, null=True)
    search_url_sublocality_radius = models.FloatField(blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab"

    @classmethod
    def update_labs_seo_urls(cls):
        from ondoc.location.management.commands import lab_page_urls, map_lab_search_urls

        # create lab page urls
        lab_page_urls.map_lab_location_urls()

        # create lab search urls
        map_lab_search_urls.map_lab_search_urls()

    @cached_property
    def is_enabled_for_insurance(self):
        return self.is_insurance_enabled

    @classmethod
    def update_insured_labs(cls):

        delete_query = RawSql(''' delete from insurance_covered_entity where type='lab' ''', []).execute()

        query = '''
                    insert into insurance_covered_entity(entity_id,name ,location, type, search_key, data,created_at,updated_at)
                    select lab_id as entity_id, lab_name as name, location ,'lab' as type,search_key,
                    json_build_object('id', lab_id, 'type','lab','name', lab_name, 'city', city,'url', url), now(), now() from
                    (select distinct lb.id lab_id, lb.name lab_name, lb.city, eu.url,
                    lb.location, lb.search_key
                    from lab lb inner join available_lab_test avlt on
                    lb.lab_pricing_group_id = avlt.lab_pricing_group_id  and avlt.enabled = True and avlt.mrp<=1500
                    and lb.is_test_lab = False and lb.is_live = True and lb.lab_pricing_group_id is not null 
                    inner join lab_test lt on lt.id = avlt.test_id and lt.enable_for_retail=True 
                    inner join entity_urls eu on eu.entity_id = lb.id and sitemap_identifier = 'LAB_PAGE' and eu.is_valid=true
                    )x '''
        update_insured_labs = RawSql(query, []).execute()

    # Check lab or lab network is open for communication or not.
    def open_for_communications(self):
        if (self.network and self.network.open_for_communication) or (not self.network and self.open_for_communication):
            return True

        return False

    # Check lab or lab network is enable for VIP plans.
    def is_enabled_for_plus_plans(self):
        if (self.network and self.network.enabled_for_plus_plans) or (not self.network and self.enabled_for_plus_plans):
            return True

        return False

    # Check if lab or lab network can accept appointment through ivr or not.
    def is_auto_ivr_enabled(self):
        if (self.network and self.network.auto_ivr_enabled) or (not self.network and self.auto_ivr_enabled):
            return True

        return False

    # This method is use to get user insurance related data.
    @classmethod
    def get_insurance_details(cls, user, ins_threshold_amt=None):

        from ondoc.insurance.models import InsuranceThreshold
        if not ins_threshold_amt:
            insurance_threshold_obj = InsuranceThreshold.objects.all().order_by('-opd_amount_limit').first()
            insurance_threshold_amount = insurance_threshold_obj.opd_amount_limit if insurance_threshold_obj else 1500
        else:
            insurance_threshold_amount = ins_threshold_amt
        resp = {
            'is_insurance_covered': False,
            'insurance_threshold_amount': insurance_threshold_amount,
            'is_user_insured': False
        }

        if user.is_authenticated and not user.is_anonymous:
            user_insurance = user.active_insurance
            if user_insurance:
                insurance_threshold = user_insurance.insurance_threshold
                if insurance_threshold:
                    resp['insurance_threshold_amount'] = 0 if insurance_threshold.lab_amount_limit is None else \
                        insurance_threshold.lab_amount_limit
                    resp['is_user_insured'] = True

        return resp

    # This method is use to get user vip plan details.
    @classmethod
    def get_vip_details(cls, user, search_criteria_query=None):

        if not search_criteria_query:
            search_criteria = SearchCriteria.objects.filter(search_key='is_gold').first()
        else:
            search_criteria = search_criteria_query

        hosp_is_gold = False
        if search_criteria:
            hosp_is_gold = search_criteria.search_value

        resp = {
            'is_vip_member': False,
            'covered_under_vip': False,
            'vip_amount': 0,
            'vip_convenience_amount': 0,
            'vip_gold_price': 0,
            'is_gold_member': False,
            'is_gold': hosp_is_gold
        }

        if user.is_authenticated and not user.is_anonymous:
            is_user_vip = user.active_plus_user and not user.inactive_plus_user
            if is_user_vip:
                resp['is_vip_member'] = True

        return resp

    def convert_min(self, min):
        min_str = str(min)
        if min/10 < 1:
            min_str = '0' + str(min)
        return min_str

    def convert_time(self, time):
        hour = int(time)
        min = int((time - hour) * 60)
        am_pm = ''
        if time < 12:
            am_pm = 'AM'
        else:
            am_pm = 'PM'
            if not hour == 12:
                hour -= 12
        min_str = self.convert_min(min)
        return str(hour) + ":" + min_str + " " + am_pm

    # To get formatted lab timing for lab listing page.
    def get_lab_timing(self, queryset):
        lab_timing = ''
        lab_timing_data = list()
        temp_list = list()

        for qdata in queryset:
            temp_list.append({"start": qdata.start, "end": qdata.end})

        temp_list = sorted(temp_list, key=lambda k: k["start"])

        index = 0
        while index < len(temp_list):
            temp_dict = dict()
            x = index
            if not lab_timing:
                lab_timing += self.convert_time(temp_list[index]["start"]) + " - "
            else:
                lab_timing += " | " + self.convert_time(temp_list[index]["start"]) + " - "
            temp_dict["start"] = temp_list[index]["start"]
            while x + 1 < len(temp_list) and temp_list[x]["end"] >= temp_list[x+1]["start"]:
                x += 1
            index = x
            lab_timing += self.convert_time(temp_list[index]["end"])
            temp_dict["end"] = temp_list[index]["end"]
            lab_timing_data.append(temp_dict)
            index += 1

        return {'lab_timing': lab_timing, 'lab_timing_data': lab_timing_data}

    # def lab_timings_today(self, day_now=timezone.now().weekday()):
    #     lab_timing = list()
    #     lab_timing_data = list()
    #     time_choices = {item[0]: item[1] for item in LabTiming.TIME_CHOICES}
    #     if self.always_open:
    #         lab_timing.append("12:00 AM - 11:45 PM")
    #         lab_timing_data.append({
    #             "start": str(0.0),
    #             "end": str(23.75)
    #         })
    #     else:
    #         timing_queryset = self.lab_timings.all()
    #         for data in timing_queryset:
    #             if data.day == day_now:
    #                 lab_timing, lab_timing_data = self.get_lab_timing(data)
    #                 # lab_timing.append('{} - {}'.format(time_choices[data.start], time_choices[data.end]))
    #                 # lab_timing_data.append({"start": str(data.start), "end": str(data.end)})
    #    return lab_timing, lab_timing_data

    # Lab.lab_timings_today = get_lab_timings_today

    # Get lab timings for current and next day for lab listing page.
    def lab_timings_today_and_next(self, day_now=timezone.now().weekday(), test_obj=None):
        lab_timing = ""
        lab_timing_data = list()
        next_lab_timing_dict = {}
        next_lab_timing_data_dict = {}
        data_array = [list() for i in range(7)]
        days_array = [i for i in range(7)]
        rotated_days_array = days_array[day_now:] + days_array[:day_now]
        if self.always_open:
            lab_timing = "12:00 AM - 11:45 PM"
            lab_timing_data = [{
                "start": 0.0,
                "end": 23.75
            }]
            next_lab_timing_dict = {day_now+1: "12:00 AM - 11:45 PM"}
            next_lab_timing_data_dict = {day_now+1: {
                "start": 0.0,
                "end": 23.75
            }}
        else:
            if test_obj and test_obj.test_type == 1:
                lab_test_group_mapping = LabTestGroupMapping.objects.filter(test=test_obj).first()
                if lab_test_group_mapping:
                    lab_test_group = LabTestGroup.objects.filter(id=lab_test_group_mapping.lab_test_group_id).first()
                    if lab_test_group:
                        timing_queryset = self.test_group_timings.filter(lab_test_group=lab_test_group)
                        if not timing_queryset.exists():
                            timing_queryset = self.lab_timings.all()
                    else:
                        timing_queryset = self.lab_timings.all()
                else:
                    timing_queryset = self.lab_timings.all()
            else:
                timing_queryset = self.lab_timings.all()

            for data in timing_queryset:
                data_array[data.day].append(data)
            rotated_data_array = data_array[day_now:] + data_array[:day_now]

            for count, timing_data in enumerate(rotated_data_array):
                day = rotated_days_array[count]
                if count == 0:
                    # {'lab_timing': lab_timing, 'lab_timing_data': lab_timing_data}
                    timing_dict = self.get_lab_timing(timing_data)
                    lab_timing, lab_timing_data = timing_dict['lab_timing'], timing_dict['lab_timing_data']
                    lab_timing_data = sorted(lab_timing_data, key=lambda k: k["start"])
                elif timing_data:
                    next_timing_dict = self.get_lab_timing(timing_data)
                    next_lab_timing, next_lab_timing_data = next_timing_dict['lab_timing'], next_timing_dict['lab_timing_data']
                    # next_lab_timing, next_lab_timing_data = self.get_lab_timing(timing_data)
                    next_lab_timing_data = sorted(next_lab_timing_data, key=lambda k: k["start"])
                    next_lab_timing_dict[day] = next_lab_timing
                    next_lab_timing_data_dict[day] = next_lab_timing_data
                    break

        return {'lab_timing': lab_timing, 'lab_timing_data': lab_timing_data,
                'next_lab_timing_dict': next_lab_timing_dict,
                'next_lab_timing_data_dict': next_lab_timing_data_dict}

    # This method provides ratings of a lab.
    def get_ratings(self):
        return self.rating.all()

    # To get lab logo.
    def get_thumbnail(self):
        all_documents = self.lab_documents.all()
        for document in all_documents:
            if document.document_type == LabDocument.LOGO:
                return document.get_thumbnail_path(document.name.url, '90x60')
        return None
        # return static('lab_images/lab_default.png')

    # To get lab's full address.
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

    # To change is_live status of a lab as per onboarding and qc status.
    def update_live_status(self):

        if not self.is_live and (self.onboarding_status == self.ONBOARDED and self.data_status == self.QC_APPROVED and self.enabled == True):
            self.is_live = True
            if not self.live_at:
                self.live_at = datetime.datetime.now()

        if self.is_live and (self.onboarding_status != self.ONBOARDED or self.data_status != self.QC_APPROVED or self.enabled == False):
            self.is_live = False

    # To check if we need to display rating or not.
    def display_rating_on_list(self):
        if self.rating_data and ((self.rating_data.get('rating_count') and self.rating_data['rating_count'] > 5) or \
                                 (self.rating_data.get('avg_rating') and self.rating_data['avg_rating'] > 4)):
            return True
        return False

    # To create SEO urls
    def create_entity_url(self):
        if not self.is_live:
            return

        entity = EntityUrls.objects.filter(entity_id=self.id, is_valid=True, sitemap_identifier='LAB_PAGE')
        if not entity:
            url = self.name
            url = slugify(url)
            new_url = url

            exists = EntityUrls.objects.filter(url=new_url+'-lpp', sitemap_identifier='LAB_PAGE').first()
            if exists:
                if exists.id == self.id:
                    exists.is_valid = True
                    exists.save()
                    new_url = new_url + '-lpp'
                    return
                else:
                    new_url = url+'-'+str(self.id)

            new_url = new_url + '-lpp'
            EntityUrls.objects.create(url=new_url, sitemap_identifier='LAB_PAGE', entity_type='Lab', url_type='PAGEURL',
                                  is_valid=True, sequence=0, entity_id=self.id)
            self.url = new_url

    def save(self, *args, **kwargs):
        self.clean()

        edit_instance = None
        if self.id is not None:
            edit_instance = 1
            original = Lab.objects.get(pk=self.id)

        self.update_live_status()

        # On every update of onboarding status or Qcstatus push to matrix
        push_to_matrix = False
        if self.id:
            lab_obj = Lab.objects.filter(pk=self.id).first()
            if lab_obj and (self.onboarding_status != lab_obj.onboarding_status or
                            self.data_status != lab_obj.data_status):
                # Push to matrix
                push_to_matrix = True

        self.create_entity_url()
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

        # transaction.on_commit(lambda: self.app_commit_tasks(push_to_matrix))
    #
    # def app_commit_tasks(self, push_to_matrix):
    #     if push_to_matrix:
    #         push_onboarding_qcstatus_to_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
    #                                                         ,), countdown=5)

    # To get SPOC details for notifications.
    def get_managers_for_communication(self):
        result = []
        result.extend(list(self.labmanager_set.filter(contact_type__in=[LabManager.SPOC, LabManager.MANAGER])))
        if not result:
            result.extend(list(self.labmanager_set.filter(contact_type=LabManager.OWNER)))
        return result

    @classmethod
    def update_avg_rating(cls):
        from django.db import connection
        cursor = connection.cursor()
        content_type = ContentType.objects.get_for_model(Lab)
        if content_type:
            cid = content_type.id
            query = '''update lab l set rating_data = 
                        (select rating_data from
                        (select max(l.id) lab_id,max(l.network_id) network_id,
                        json_build_object('avg_rating', round(avg(ratings),1),'rating_count' ,count(ratings)) rating_data
                        from ratings_review rr
                        inner join lab l on rr.object_id = l.id 
                        and rr.content_type_id={}
                        where rr.is_live='true'
                        group by case when l.network_id is null then l.id else l.network_id end
                        )x where case when l.network_id is null then l.id=x.lab_id else l.network_id=x.network_id end
                        )
                     '''.format(cid)
            cursor.execute(query)

    # To get lab available slots - Old
    def get_timing(self, is_home_pickup):
        from ondoc.api.v1.common import serializers as common_serializers
        date = datetime.datetime.today().strftime('%Y-%m-%d')
        lab_timing_queryset = self.lab_timings.filter(for_home_pickup=is_home_pickup)
        lab_slots = []
        if not lab_timing_queryset or (is_home_pickup and not lab_timing_queryset[0].lab.is_home_collection_enabled):
            res_data = OrderedDict()
            for i in range(30):
                converted_date = (datetime.datetime.now() + datetime.timedelta(days=i))
                readable_date = converted_date.strftime("%Y-%m-%d")
                res_data[readable_date] = list()

            res_data = {"time_slots": res_data, "upcoming_slots": [], "is_thyrocare": False}
            return res_data
        else:
            global_leave_serializer = common_serializers.GlobalNonBookableSerializer(
                GlobalNonBookable.objects.filter(deleted_at__isnull=True, booking_type=GlobalNonBookable.LAB), many=True)
            total_leaves = dict()
            total_leaves['global'] = global_leave_serializer.data

        obj = TimeSlotExtraction()

        if not is_home_pickup and lab_timing_queryset[0].lab.always_open:
            for day in range(0, 7):
                obj.form_time_slots(day=day, start=0.0, end=23.75, price=None, is_available=True,
                                    deal_price=None, mrp=None, cod_deal_price=None, is_doctor=False, on_call=0)

        else:
            for data in lab_timing_queryset:
                obj.form_time_slots(day=data.day, start=data.start, end=data.end, price=None, is_available=True,
                                    deal_price=None, mrp=None, cod_deal_price=None, is_doctor=False, on_call=0)

        global_leave_serializer = common_serializers.GlobalNonBookableSerializer(
            GlobalNonBookable.objects.filter(deleted_at__isnull=True,
                                             booking_type=GlobalNonBookable.LAB), many=True)

        booking_details = {"type": "lab", "is_home_pickup": is_home_pickup}
        resp_list = obj.get_timing_slots(date, global_leave_serializer.data, booking_details)
        is_thyrocare = False
        lab_id = self.id
        if lab_id and settings.THYROCARE_NETWORK_ID:
            if Lab.objects.filter(id=lab_id, network_id=settings.THYROCARE_NETWORK_ID).exists():
                is_thyrocare = True

        # today_min, tomorrow_min, today_max = obj.initial_start_times(is_thyrocare=is_thyrocare,
        #                                                              is_home_pickup=is_home_pickup,
        #                                                              time_slots=resp_list)
        # res_data = {
        #     "time_slots": resp_list,
        #     "today_min": today_min,
        #     "tomorrow_min": tomorrow_min,
        #     "today_max": today_max
        # }

        upcoming_slots = obj.get_upcoming_slots(time_slots=resp_list)
        res_data = {"time_slots": resp_list, "upcoming_slots": upcoming_slots, "is_thyrocare": False}
        return res_data

    # To get pathology test available slots
    def get_timing_v2(self, is_home_pickup, total_leaves=None):
        is_thyrocare = False
        if not is_home_pickup and self.always_open:
            lab_timing_queryset = list()
            for day in range(0, 7):
                lab_timing = {'day': day, 'start': 0.0, 'end': 23.75}
                lab_timing_queryset.append(lab_timing)
        else:
            lab_timing_queryset = self.lab_timings.filter(for_home_pickup=is_home_pickup)

        if not total_leaves:
            global_non_bookables = GlobalNonBookable.get_non_bookables(GlobalNonBookable.LAB)
            total_leaves = global_non_bookables

        booking_details = {"type": "lab", "is_home_pickup": is_home_pickup}
        timeslot_object = TimeSlotExtraction()
        timeslots = timeslot_object.format_timing_to_datetime_v2(lab_timing_queryset, total_leaves, booking_details, is_thyrocare)
        upcoming_slots = timeslot_object.get_upcoming_slots(time_slots=timeslots)
        timing_response = {"time_slots": timeslots, "upcoming_slots": upcoming_slots, "is_thyrocare": is_thyrocare}
        return timing_response

    # To get time slots of radiology tests
    def get_radiology_timing(self, test, total_leaves=None):
        is_thyrocare = False
        lab_test_group_timing = []
        lab_test_group_mapping = LabTestGroupMapping.objects.filter(test=test).first()
        if lab_test_group_mapping:
            lab_test_group = LabTestGroup.objects.filter(id=lab_test_group_mapping.lab_test_group_id).first()

            if lab_test_group:
                lab_test_group_timing = LabTestGroupTiming.objects.filter(lab=self, lab_test_group=lab_test_group)

        if not total_leaves:
            global_non_bookables = GlobalNonBookable.get_non_bookables(GlobalNonBookable.LAB)
            total_leaves = global_non_bookables

        booking_details = {"type": "lab", "is_home_pickup": False}
        timeslot_object = TimeSlotExtraction()
        timeslots = timeslot_object.format_timing_to_datetime_v2(lab_test_group_timing, total_leaves, booking_details,
                                                                 is_thyrocare)
        upcoming_slots = timeslot_object.get_upcoming_slots(time_slots=timeslots)
        timing_response = {"time_slots": timeslots, "upcoming_slots": upcoming_slots, "is_thyrocare": is_thyrocare}
        return timing_response

    # Pathology test available slots
    def get_available_slots(self, is_home_pickup, pincode, date):
        from ondoc.integrations.models import IntegratorTestMapping
        from ondoc.integrations import service

        integration_dict = None
        lab = Lab.objects.filter(id=self.id).first()
        if lab:
            if lab.network and lab.network.id:
                integration_dict = IntegratorTestMapping.get_if_third_party_integration(network_id=lab.network.id)

                if lab.network.id == settings.THYROCARE_NETWORK_ID and settings.THYROCARE_INTEGRATION_ENABLED:
                    pass
                else:
                    integration_dict = None

        if not integration_dict:
            available_slots = lab.get_timing_v2(is_home_pickup)
        else:
            class_name = integration_dict['class_name']
            integrator_obj = service.create_integrator_obj(class_name)
            available_slots = integrator_obj.get_appointment_slots(pincode, date,
                                                                   is_home_pickup=is_home_pickup)

        return available_slots

    # Radiology test available slots
    def get_radiology_available_slots(self, test, is_home_pickup, pincode, date):
        from ondoc.integrations.models import IntegratorTestMapping
        from ondoc.integrations import service

        integration_dict = None
        lab = Lab.objects.filter(id=self.id).first()
        if lab:
            if lab.network and lab.network.id:
                integration_dict = IntegratorTestMapping.get_if_third_party_integration(network_id=lab.network.id)

                if lab.network.id == settings.THYROCARE_NETWORK_ID and settings.THYROCARE_INTEGRATION_ENABLED:
                    pass
                else:
                    integration_dict = None

        if not integration_dict:
            available_slots = lab.get_radiology_timing(test)
        else:
            class_name = integration_dict['class_name']
            integrator_obj = service.create_integrator_obj(class_name)
            available_slots = integrator_obj.get_appointment_slots(pincode, date,
                                                                   is_home_pickup=is_home_pickup)

        return available_slots

    # To check if lab is integrated or not
    def is_integrated(self):
        from ondoc.integrations.models import IntegratorTestMapping

        integration_dict = None
        if self.network and self.network.id:
            integration_dict = IntegratorTestMapping.get_if_third_party_integration(network_id=self.network.id)
        if not integration_dict:
            return False
        else:
            return True


class LabCertification(TimeStampedModel):
    lab = models.ForeignKey(Lab, related_name = 'lab_certificate', on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    certification = models.ForeignKey(Certifications, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='lab_certifications')

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

    # def lab_booking_slots_new(self, *args, **kwargs):
    #
    #     is_home_pickup = kwargs.get("for_home_pickup", False)
    #
    #     if is_home_pickup:
    #         kwargs["lab__is_home_collection_enabled"] = is_home_pickup
    #     lab_timing_queryset = LabTiming.timing_manager.filter(**kwargs)
    #
    #     if not lab_timing_queryset or (is_home_pickup and not lab_timing_queryset[0].lab.is_home_collection_enabled):
    #         return {
    #             "time_slots": [],
    #             "today_min": None,
    #             "tomorrow_min": None,
    #             "today_max": None
    #         }
    #
    #     else:
    #         obj = TimeSlotExtraction()
    #         threshold = lab_timing_queryset[0].lab.booking_closing_hours_from_dayend
    #
    #         if not is_home_pickup and lab_timing_queryset[0].lab.always_open:
    #             for day in range(0, 7):
    #                 obj.form_time_slots(day, 0.0, 23.75, None, True)
    #
    #         else:
    #             for data in lab_timing_queryset:
    #                 obj.form_time_slots(data.day, data.start, data.end, None, True)
    #             # daywise_data_array = sorted(lab_timing_queryset, key=lambda k: [k.day, k.start], reverse=True)
    #             # day, end = daywise_data_array[0].day, daywise_data_array[0].end
    #             # end = end - threshold
    #             # for data in daywise_data_array:
    #             #     if data.day != day:
    #             #         day = data.day
    #             #         end = data.end - threshold
    #             #     if not end <= data.start <= data.end:
    #             #         if data.start <= end <= data.end:
    #             #             data.end = end
    #             #         obj.form_time_slots(data.day, data.start, data.end, None, True)
    #         global_leave_serializer = common_serializers.GlobalNonBookableSerializer(
    #                             GlobalNonBookable.objects.filter(deleted_at__isnull=True,
    #                                                              booking_type=GlobalNonBookable.DOCTOR), many=True)
    #         date = datetime.datetime.today().strftime('%Y-%m-%d')
    #         # resp_list = obj.get_timing_list()
    #         resp_list = obj.get_timing_slots(date, global_leave_serializer.data, "lab")
    #         is_thyrocare = False
    #         lab_id = kwargs.get("lab__id", None)
    #         if lab_id and settings.THYROCARE_NETWORK_ID:
    #             if Lab.objects.filter(id=lab_id, network_id=settings.THYROCARE_NETWORK_ID).exists():
    #                 is_thyrocare = True
    #
    #         today_min, tomorrow_min, today_max = obj.initial_start_times(is_thyrocare=is_thyrocare, is_home_pickup=is_home_pickup, time_slots=resp_list)
    #         res_data = {
    #             "time_slots": resp_list,
    #             "today_min": today_min,
    #             "tomorrow_min": tomorrow_min,
    #             "today_max": today_max
    #         }
    #
    #         return res_data

    # To get time slots for lab - Not in use
    def lab_booking_slots(self, *args, **kwargs):
        is_home_pickup = kwargs.get("for_home_pickup", False)

        if is_home_pickup:
            kwargs["lab__is_home_collection_enabled"] = is_home_pickup
        lab_timing_queryset = LabTiming.timing_manager.filter(**kwargs)

        if not lab_timing_queryset or (
                is_home_pickup and not lab_timing_queryset[0].lab.is_home_collection_enabled):
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
                    obj.form_time_slots(day=day, start=0.0, end=23.75, price=None, is_available=True,
                                        deal_price=None, mrp=None, cod_deal_price=None, is_doctor=False, on_call=0)

            else:
                for data in lab_timing_queryset:
                    obj.form_time_slots(day=data.day, start=data.start, end=data.end, price=None, is_available=True,
                                        deal_price=None, mrp=None, cod_deal_price=None, is_doctor=False, on_call=0)

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

            today_min, tomorrow_min, today_max = obj.initial_start_times(is_thyrocare=is_thyrocare,
                                                                         is_home_pickup=is_home_pickup,
                                                                         time_slots=resp_list)
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
    matrix_state = models.ForeignKey(MatrixMappedState, null=True, blank=False, on_delete=models.DO_NOTHING,
                                     related_name='lab_networks_in_state', verbose_name='State')
    matrix_city = models.ForeignKey(MatrixMappedCity, null=True, blank=False, on_delete=models.DO_NOTHING,
                                    related_name='lab_networks_in_city', verbose_name='City')
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)

    # generic_lab_network_admins = GenericRelation(GenericAdmin, related_query_name='manageable_lab_networks')
    assigned_to = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_lab_networks')
    billing_merchant = GenericRelation(BillingAccount)
    home_collection_charges = GenericRelation(HomePickupCharges)
    spoc_details = GenericRelation(auth_model.SPOCDetails)
    merchant = GenericRelation(auth_model.AssociatedMerchant)
    merchant_payout = GenericRelation(account_model.MerchantPayout)
    is_mask_number_required = models.BooleanField(default=True)
    open_for_communication = models.BooleanField(default=True)
    remark = GenericRelation(Remark)
    auto_ivr_enabled = models.BooleanField(default=True)
    enabled_for_plus_plans = models.NullBooleanField()
    center_visit = models.NullBooleanField()

    # Get all vip plus enabled lab networks
    @classmethod
    def get_plus_enabled(cls):
        return cls.objects.filter(enabled_for_plus_plans=True)

    # Get all labs in the network - Not in use
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
    certification = models.ForeignKey(Certifications, on_delete=models.DO_NOTHING, null=True, blank=True, related_name='lab_network_certifications')

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
    details = models.CharField(max_length=10000, null=True, blank=True)
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



class FrequentlyAddedTogetherTests(TimeStampedModel):
    original_test = models.ForeignKey('diagnostic.LabTest', related_name='base_test' ,null =True, blank =False, on_delete=models.CASCADE)
    booked_together_test = models.ForeignKey('diagnostic.LabTest', related_name='booked_together' ,null=True, blank=False, on_delete=models.CASCADE)

    class Meta:
        db_table = "frequently_added_tests"


class LabTestCategory(auth_model.TimeStampedModel, SearchKey):
    name = models.CharField(max_length=500, unique=True)
    preferred_lab_test = models.ForeignKey('LabTest', on_delete=models.SET_NULL,
                                            related_name='preferred_in_lab_test_category', null=True, blank=True)
    is_live = models.BooleanField(default=False)
    is_package_category = models.BooleanField(verbose_name='Is this a test package category?')
    show_on_recommended_screen = models.BooleanField(default=False)
    priority = models.PositiveIntegerField(default=0)
    # icon = models.ImageField(upload_to='test/image', null=True, blank=True)
    icon = models.FileField(upload_to='test/image', blank=True, null=True, validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg'])])
    svg_icon = models.FileField(upload_to='test/image', blank=True, null=True,
                                validators=[FileExtensionValidator(allowed_extensions=['svg'])])

    def __str__(self):
        return self.name

    class Meta:
        db_table = "lab_test_category"


class LabTestCategoryMapping(models.Model):
    lab_test = models.ForeignKey('LabTest', on_delete=models.CASCADE,
                                 related_name='parent_lab_test_category_mappings')
    parent_category = models.ForeignKey(LabTestCategory, on_delete=models.CASCADE,
                                 related_name='lab_test_mappings')
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return '({}){}'.format(self.lab_test, self.parent_category)

    class Meta:
        db_table = "lab_test_to_category_mapping"
        unique_together = (('lab_test', 'parent_category'),)


class LabTestRecommendedCategoryMapping(models.Model):
    lab_test = models.ForeignKey('LabTest', on_delete=models.CASCADE,
                                 related_name='recommended_lab_test_category_mappings')
    parent_category = models.ForeignKey(LabTestCategory, on_delete=models.CASCADE,
                                        related_name='recommended_lab_test_mappings')
    show_on_recommended_screen = models.BooleanField(default=False)

    def __str__(self):
        return '({}){}'.format(self.lab_test, self.parent_category)

    class Meta:
        db_table = "lab_test_recommended_category_mapping"
        unique_together = (('lab_test', 'parent_category'),)


class LabtestNameMaster(auth_model.TimeStampedModel, auth_model.SoftDelete):
    name = models.CharField(max_length=256, blank=False, null=False)

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = "labtest_master"


class LabTest(TimeStampedModel, SearchKey):
    LAB_TEST_SITEMAP_IDENTIFIER = 'LAB_TEST'
    URL_SUFFIX = 'tpp'
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
    why = models.TextField(blank=True, verbose_name='Why get tested?')
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
    test = models.ManyToManyField('self', through='LabTestPackage', symmetrical=False, related_name= 'package_test',
                                  through_fields=('package', 'lab_test'))  # self reference
    parameter = models.ManyToManyField(
        'TestParameter', through=ParameterLabTest,
        through_fields=('lab_test', 'parameter')
    )
    frequently_booked_together = models.ManyToManyField('self', symmetrical=False, through=FrequentlyAddedTogetherTests,
                                                        related_name= 'frequent_test',
                                                        through_fields=('original_test','booked_together_test'))
    approximate_duration = models.CharField(max_length=50, default='15 mins', verbose_name='What is the approximate duration for the test?')
    report_schedule = models.CharField(max_length=150, default='After 2 days of test.', verbose_name='What is the report schedule for the test?')
    enable_for_ppc = models.BooleanField(default=False)
    enable_for_retail = models.BooleanField(default=False)
    about_test = models.TextField(blank=True, verbose_name='About the test')
    show_details = models.BooleanField(default=False)
    preparations = models.TextField(blank=True, verbose_name='Preparations for the test')
    priority = models.IntegerField(default=1, null=False, blank=False)
    hide_price = models.BooleanField(default=False)
    searchable = models.BooleanField(default=True)
    categories = models.ManyToManyField(LabTestCategory,
                                        through=LabTestCategoryMapping,
                                        through_fields=('lab_test', 'parent_category'),
                                        related_name='lab_tests')
    url = models.CharField(max_length=500, blank=True, editable=False)
    custom_url = models.CharField(max_length=500, blank=True)
    min_age = models.PositiveSmallIntegerField(default=None, blank=True, null=True, validators=[MaxValueValidator(120), MinValueValidator(1)])
    max_age = models.PositiveSmallIntegerField(default=None, blank=True, null=True, validators=[MaxValueValidator(120), MinValueValidator(1)])
    MALE = 1
    FEMALE = 2
    ALL = 3
    GENDER_TYPE_CHOICES = (
        ('', 'Select'),
        (MALE, 'male'),
        (FEMALE, 'female'),
        (ALL, 'all')
    )
    gender_type = models.PositiveIntegerField(choices=GENDER_TYPE_CHOICES, blank=True, null=True)
    recommended_categories = models.ManyToManyField(LabTestCategory,
                                        through=LabTestRecommendedCategoryMapping,
                                        through_fields=('lab_test', 'parent_category'),
                                        related_name='recommended_lab_tests')
    reference_code = models.CharField(max_length=150, blank=True, default='')

    author = models.ForeignKey(Doctor, null=True, blank=True, related_name='published_tests',
                               on_delete=models.SET_NULL)
    is_cancellable = models.BooleanField(default=True)
    insurance_cutoff_price = models.PositiveIntegerField(default=None, null=True, blank=True)
    search_name = models.ForeignKey(LabtestNameMaster, null=True, blank=True, on_delete=models.SET_NULL)

    # test_sub_type = models.ManyToManyField(
    #     LabTestSubType,
    #     through='LabTestSubTypeMapping',
    #     through_fields=("lab_test", "test_sub_type", )
    # )

    def __str__(self):
        return '{} ({})'.format(self.name, "PACKAGE" if self.is_package else "TEST")

    def save(self, *args, **kwargs):

        url = slugify(self.custom_url)
        #self.url = slugify(self.url)

        if not url:
            url = slugify(self.name)+'-'+self.URL_SUFFIX

        generated_url = self.generate_url(url)
        if generated_url!=url:
            url = generated_url


        self.url = url
        super().save(*args, **kwargs)
        
        self.create_url(url)

    # This method is use to add id in duplicate url
    def generate_url(self, url):
        duplicate_urls = EntityUrls.objects.filter(~Q(entity_id=self.id), url__iexact=url, sitemap_identifier=LabTest.LAB_TEST_SITEMAP_IDENTIFIER)
        if duplicate_urls.exists():
            url = url.rstrip(self.URL_SUFFIX)
            url = url.rstrip('-')
            url = url+'-'+str(id)+'-'+self.URL_SUFFIX

        return url

    # To create new entity urls
    def create_url(self, url):
        existings_urls = EntityUrls.objects.filter(url__iexact=url, \
                                                sitemap_identifier=LabTest.LAB_TEST_SITEMAP_IDENTIFIER, entity_id=self.id).all()

        if not existings_urls.exists():
            url_entry = EntityUrls.objects.create(url=url, entity_id=self.id, sitemap_identifier=self.LAB_TEST_SITEMAP_IDENTIFIER,\
                                                  is_valid=True, url_type='PAGEURL', entity_type='LabTest')
            EntityUrls.objects.filter(entity_id=self.id).filter(~Q(id=url_entry.id)).update(is_valid=False)
        else:
            if not existings_urls.filter(is_valid=True).exists():
                eu = existings_urls.first()
                eu.is_valid = True
                eu.save()
                EntityUrls.objects.filter(entity_id=self.id).filter(~Q(id=eu.id)).update(is_valid=False)

    class Meta:
        db_table = "lab_test"

#
#
# class FrequentlyAddedTogetherTests(TimeStampedModel):
#     test = models.ForeignKey(LabTest, related_name='base_test' ,null =True, blank =False, on_delete=models.CASCADE)
#     booked_together_test = models.ForeignKey(LabTest, related_name='booked_together' ,null=True, blank=False, on_delete=models.CASCADE)
#
#     class Meta:
#         db_table = "related_tests"

    # Returns test related categories details
    def get_all_categories_detail(self):
        all_categories = self.categories.all()
        res = []
        for item in all_categories:
            if item.is_live == True:
                resp = {}
                resp['name'] = item.name if item.name else None
                resp['id'] = item.id if item.id else None
                resp['icon'] = item.icon.url if item.icon and item.icon.url else None
                res.append(resp)
        return res


class QuestionAnswer(TimeStampedModel):
    test_question = models.TextField(null=False, verbose_name='Question')
    test_answer = models.TextField(null=True, verbose_name='Answer')
    lab_test = models.ForeignKey(LabTest, related_name='faq', null=True, blank=False, on_delete=models.CASCADE)

    class Meta:
        db_table = "question_answer"


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
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='availabletests', null=True, blank=True)  # Don't use
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='availablelabs')
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    computed_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    custom_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    computed_deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    custom_deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    enabled = models.BooleanField(default=False)
    lab_pricing_group = models.ForeignKey(LabPricingGroup, blank=True, null=True, on_delete=models.SET_NULL,
                                          related_name='available_lab_tests')
    supplier_name = models.CharField(null=True, blank=True, max_length=40, default=None)
    supplier_price = models.DecimalField(default=None, max_digits=10, decimal_places=2, null=True, blank=True)
    desired_docprime_price = models.DecimalField(default=None, max_digits=10, decimal_places=2, null=True, blank=True)
    rating = GenericRelation(ratings_models.RatingsReview)
    insurance_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    convenience_pricing = JSONField(null=True, blank=True)

    def __str__(self):
        return "{}-{}".format(self.lab, self.test)

    # Get lab test deal price
    def get_deal_price(self):
        return self.custom_deal_price if self.custom_deal_price else self.computed_deal_price

    # Calculate convenience charge for a VIP plan
    def calculate_convenience_charge(self, plan):
        if not plan:
            plan = PlusPlans.objects.filter(is_gold=True, is_selected=True).first()
            if not plan:
                plan = PlusPlans.objects.filter(is_gold=True).first()
                if not plan:
                    return 0

        if not self.convenience_pricing:
            return 0

        return self.convenience_pricing.get(str(plan.id), 0)

    # Deal Price update - test specific
    def update_deal_price(self):
        # will update only this available lab test prices and will be called on save
        query = '''update available_lab_test set computed_deal_price = (case when custom_deal_price is null then mrp else custom_deal_price end )::integer where id = %s'''
        update_available_lab_test_deal_price = RawSql(query, [self.pk]).execute()

        # query = '''update available_lab_test set computed_deal_price = least(greatest( floor(GREATEST
        #         ((case when custom_agreed_price is not null
        #         then custom_agreed_price else computed_agreed_price end)*1.2,mrp*.8)/5)*5,case when custom_agreed_price
        #         is not null then custom_agreed_price
        #         else computed_agreed_price end), mrp) where id = %s '''

        # query = '''update available_lab_test set computed_deal_price = (select deal_price from
        #         (select * from
        #         (select id, mrp, agreed_price,
        #         case
        #         when mrp <=300 then  least( case when mrp>2000 then
        #         (least(agreed_price*1.5, agreed_price+ 0.5*	(mrp-agreed_price)))
        #         else
        #         (greatest(agreed_price+60, greatest(0.7*mrp, mrp-200))) end /0.75, mrp)
        #         else
			# 	least( case when mrp>2000 then least(agreed_price*1.5, agreed_price+0.5*(mrp-agreed_price))
			# 	else greatest(agreed_price+60, greatest(0.7*mrp, mrp-200))end +75, mrp) end as deal_price
        #         from
        #         (select case when custom_agreed_price is null then computed_agreed_price else custom_agreed_price end as agreed_price,
        #         mrp, id from available_lab_test)x)y where y.id = available_lab_test.id )z) where available_lab_test.enabled=true and id=%s '''
        #
        # update_available_lab_test_deal_price = RawSql(query, [self.pk, self.pk]).execute()
        # deal_price = RawSql(query, [self.pk]).fetch_all()
        # if deal_price:
        #    self.computed_deal_price = deepcopy(deal_price[0].get('computed_deal_price'))

    # Deal Price update - all tests
    @classmethod
    def update_all_deal_price(cls):
        # will update all lab prices
        # query = '''update available_lab_test set computed_deal_price = (select deal_price from
        #         (select * from
        #         (select id, mrp, agreed_price,
        #         case
        #         when mrp <=300 then  least( case when mrp>2000 then
        #         (least(agreed_price*1.5, agreed_price+ 0.5*	(mrp-agreed_price)))
        #         else
        #         (greatest(agreed_price+60, greatest(0.7*mrp, mrp-200))) end /0.75, mrp)
        #         else
			# 	least( case when mrp>2000 then least(agreed_price*1.5, agreed_price+0.5*(mrp-agreed_price))
			# 	else greatest(agreed_price+60, greatest(0.7*mrp, mrp-200))end +75, mrp) end as deal_price
        #         from
        #         (select case when custom_agreed_price is null then computed_agreed_price else custom_agreed_price end as agreed_price,
        #         mrp, id from available_lab_test)x)y where y.id = available_lab_test.id )z) where available_lab_test.enabled=true'''

        query = '''update available_lab_test set computed_deal_price = (case when custom_deal_price is null then mrp else custom_deal_price end )::integer '''

        update_all_available_lab_test_deal_price = RawSql(query, []).execute()

    # Get lab test id
    def get_testid(self):
        return self.test.id

    # Get lab test type (Radiology or Pathology)
    def get_type(self):
        return self.test.test_type

    def save(self, *args, **kwargs):
        if self.mrp:
            self.computed_agreed_price = self.get_computed_agreed_price()
            # self.computed_deal_price = self.get_computed_deal_price()
            self.computed_deal_price = self.computed_agreed_price
        super(AvailableLabTest, self).save(*args, **kwargs)

        transaction.on_commit(lambda: self.app_commit_tasks())

    def app_commit_tasks(self):
        self.update_deal_price()

    # This methodd is use to send emails to internal members when test prices change.
    def send_pricing_alert_email(self, responsible_user):
        from ondoc.communications.models import EMAILNotification
        try:
            emails = settings.DEAL_AGREED_PRICE_CHANGE_EMAILS
            user_and_email = [{'user': None, 'email': email} for email in emails]
            email_notification = EMAILNotification(notification_type=NotificationAction.PRICING_ALERT_EMAIL,
                                                   context={'instance': self, 'responsible_user': responsible_user})
            email_notification.send(user_and_email)
        except Exception as e:
            logger.error(str(e))

    # This method is use to get computed deal price
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

    # This method is use to get computed agreed price
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

    def __str__(self):
        return "{} | {}".format(self.test.name, self.lab_pricing_group.group_name)

    class Meta:
        unique_together = (("test", "lab_pricing_group"))
        db_table = "available_lab_test"
        indexes = [
            models.Index(fields=['test_id', 'lab_pricing_group_id']),
        ]


class LabAppointmentInvoiceMixin(object):
    # Generate appointment invoice
    def generate_invoice(self, context=None):
        invoices = self.get_invoice_objects()
        if not invoices:
            if not context:
                from ondoc.communications.models import LabNotification
                lab_notification = LabNotification(self)
                context = lab_notification.get_context()
            invoice = Invoice.objects.create(reference_id=context.get("instance").id,
                                             product_id=Order.LAB_PRODUCT_ID)
            context = deepcopy(context)
            context['invoice'] = invoice
            html_body = render_to_string("email/lab_invoice/invoice_template.html", context=context)
            # filename = "invoice_{}_{}.pdf".format(str(timezone.now().strftime("%I%M_%d%m%Y")),
            #                                       random.randint(1111111111, 9999999999))
            filename = "payment_receipt_{}.pdf".format(context.get('instance').id)
            file = html_to_pdf(html_body, filename)
            if not file:
                logger.error("Got error while creating pdf for lab invoice.")
                return []
            invoice.file = file
            invoice.save()
            invoices = [invoice]
        return invoices


@reversion.register()
class LabAppointment(TimeStampedModel, CouponsMixin, LabAppointmentInvoiceMixin, RefundMixin, CompletedBreakupMixin, MatrixDataMixin, TdsDeductionMixin, PaymentMixin, MerchantPayoutMixin, TransactionMixin):
    from ondoc.integrations.models import IntegratorResponse
    PRODUCT_ID = Order.LAB_PRODUCT_ID
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
    MAX_FREE_BOOKINGS_ALLOWED = 3

    lab = models.ForeignKey(Lab, on_delete=models.SET_NULL, related_name='labappointment', null=True)
    lab_test = models.ManyToManyField(AvailableLabTest)  # Not to be used
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
    insurance = models.ForeignKey(insurance_model.UserInsurance, blank=True, null=True, default=None,
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
    cashback = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cancellation_reason = models.ForeignKey(CancellationReason, on_delete=models.SET_NULL, null=True, blank=True)
    cancellation_comments = models.CharField(max_length=5000, null=True, blank=True)
    merchant_payout = models.ForeignKey(MerchantPayout, related_name="lab_appointment", on_delete=models.SET_NULL, null=True)
    price_data = JSONField(blank=True, null=True)
    tests = models.ManyToManyField(LabTest, through='LabAppointmentTestMapping', through_fields=('appointment', 'test'))
    money_pool = models.ForeignKey(MoneyPool, on_delete=models.SET_NULL, null=True, related_name='lab_apps')
    mask_number = GenericRelation(AppointmentMaskNumber)
    email_notification = GenericRelation(EmailNotification, related_name="lab_notification")
    user_plan_used = models.ForeignKey('subscription_plan.UserPlanMapping', null=True, on_delete=models.DO_NOTHING,
                                       related_name='appointment_using')
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="lab_booking_analytics")
    integrator_response = GenericRelation(IntegratorResponse)
    spo_data = JSONField(blank=True, null=True)
    auto_ivr_data = JSONField(default=list(), null=True)
    history = GenericRelation(AppointmentHistory)
    refund_details = GenericRelation(RefundDetails, related_query_name="lab_appointment_detail")
    coupon_data = JSONField(blank=True, null=True)
    status_change_comments = models.CharField(max_length=5000, null=True, blank=True)
    appointment_prescriptions = GenericRelation("prescription.AppointmentPrescription", related_query_name="appointment_prescriptions")
    hospital_reference_id = models.CharField(max_length=1000, null=True, blank=True)
    reports_physically_collected = models.NullBooleanField()
    spo_lead_id = models.IntegerField(null=True, blank=True)
    action_data = JSONField(blank=True, null=True)
    plus_plan = models.ForeignKey(plus_model.PlusUser, blank=True, null=True, default=None,
                                  on_delete=models.DO_NOTHING)
    plus_plan_data = GenericRelation(PlusAppointmentMapping)
    revenue_transferred = models.NullBooleanField()

    # # Calculate appointment revenue
    # def get_revenue(self):
    #     paid_by_user = None
    #     if self.price_data and self.price_data.get('wallet_amount'):
    #         paid_by_user = self.price_data.get('wallet_amount')
    #     else:
    #         order = Order.objects.filter(reference_id=self.id, product_id=Order.LAB_PRODUCT_ID).first()
    #         if order and order.is_parent():
    #             paid_by_pg = order.amount if order.amount else 0
    #             paid_by_wallet = order.wallet_amount if order.wallet_amount else 0
    #             paid_by_user = paid_by_pg + paid_by_wallet
    #         else:
    #             order = Order.objects.filter(id=order.parent_id).first()
    #             if order:
    #                 paid_by_pg = order.amount if order.amount else 0
    #                 paid_by_wallet = order.wallet_amount if order.wallet_amount else 0
    #                 paid_by_user = paid_by_pg + paid_by_wallet
    #
    #     paid_to_provider = self.agreed_price
    #     revenue = paid_by_user - paid_to_provider
    #     return revenue

    # Check appointment provider is thyrocare or not
    @cached_property
    def is_thyrocare(self):
        lab = self.lab
        if not lab:
            return None

        if self.lab.network and self.lab.network.id == settings.THYROCARE_NETWORK_ID:
            return True

        return False

    # Get all uploaded prescriptions
    def get_all_uploaded_prescriptions(self, date=None):
        from ondoc.prescription.models import AppointmentPrescription
        qs = LabAppointment.objects.filter(user=self.user).values_list('id', flat=True)
        prescriptions = AppointmentPrescription.objects.filter(content_type=ContentType.objects.get_for_model(self), object_id__in=qs).order_by('-id')
        return prescriptions

    # Get corporate deal id from coupon used in appointment
    def get_corporate_deal_id(self):
        coupon = self.coupon.first()
        if coupon and coupon.corporate_deal:
            return coupon.corporate_deal.id

        return None

    # Get city of the lab
    def get_city(self):
        if self.lab and self.lab.matrix_city:
            return self.lab.matrix_city.id
        else:
            return None

    # Get state of the lab
    def get_state(self):
        if self.lab and self.lab.matrix_state:
            return self.lab.matrix_state.id
        else:
            return None

    # Appointment analytics data.
    def get_booking_analytics_data(self):
        data = dict()

        category = None
        for t in self.tests.all():
            if t.is_package == True:
                category = 1
                break
            else:
                category = 0

        promo_cost = self.deal_price - self.effective_price if self.deal_price and self.effective_price else 0

        data['Appointment_Id'] = self.id
        data['CityId'] = self.get_city()
        data['StateId'] = self.get_state()
        data['ProviderId'] = self.lab.id
        data['TypeId'] = 2
        data['PaymentType'] = self.payment_type if self.payment_type else None
        data['Payout'] = self.agreed_price
        data['BookingDate'] = self.created_at
        data['CorporateDealId'] = self.get_corporate_deal_id()
        data['PromoCost'] = max(0, promo_cost)
        data['GMValue'] = self.deal_price
        data['Category'] = category
        data['StatusId'] = self.status

        return data

    # Sync analytics data with optimus
    def sync_with_booking_analytics(self):
        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(LabAppointment),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            print(str(e))
            pass

        # category = None
        # for t in self.tests.all():
        #     if t.is_package == True:
        #         category = 1
        #         break
        #     else:
        #         category = 0
        #
        # promo_cost = self.deal_price - self.effective_price if self.deal_price and self.effective_price else 0
        #
        # obj = DP_OpdConsultsAndTests.objects.filter(Appointment_Id=self.id, TypeId=2).first()
        # if not obj:
        #     obj = DP_OpdConsultsAndTests()
        #     obj.Appointment_Id = self.id
        #     obj.CityId = self.get_city()
        #     obj.StateId = self.get_state()
        #     obj.ProviderId = self.lab.id
        #     obj.TypeId = 2
        #     obj.PaymentType = self.payment_type if self.payment_type else None
        #     obj.Payout = self.agreed_price
        #     obj.BookingDate = self.created_at
        # obj.CorporateDealId = self.get_corporate_deal_id()
        # obj.PromoCost = max(0, promo_cost)
        # obj.GMValue = self.deal_price
        # obj.Category = category
        # obj.StatusId = self.status
        # obj.save()
        #
        # try:
        #     SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
        #                                                   content_type=ContentType.objects.get_for_model(LabAppointment),
        #                                                   defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        # except Exception as e:
        #     pass
        #
        # return obj

    # Get booked tests price data
    def get_tests_and_prices(self):
        test_price = []
        if self.payment_type == OpdAppointment.INSURANCE:
            for test in self.test_mappings.all():
                test_price.append({'name': test.test.name, 'mrp': test.mrp, 'deal_price': "0.00",
                                   'discount': test.mrp})

            if self.is_home_pickup:
                test_price.append(
                    {'name': 'Home Pick Up Charges', 'mrp': self.home_pickup_charges, 'deal_price': "0.00",
                     'discount': self.home_pickup_charges})
        else:
            for test in self.test_mappings.all():
                test_price.append({'name': test.test.name, 'mrp': test.mrp, 'deal_price': (
                    test.custom_deal_price if test.custom_deal_price else test.computed_deal_price),
                                   'discount': test.mrp - (
                                       test.custom_deal_price if test.custom_deal_price else test.computed_deal_price)})

            if self.is_home_pickup:
                test_price.append(
                    {'name': 'Home Pick Up Charges', 'mrp': self.home_pickup_charges, 'deal_price': self.home_pickup_charges,
                     'discount': '0.00'})

        return test_price

    # This method returns invoice object.
    def get_invoice_objects(self):
        return Invoice.objects.filter(reference_id=self.id, product_id=Order.LAB_PRODUCT_ID)

    # Get url of invoice
    def get_invoice_urls(self):
        invoices_urls = []
        if self.id:
            invoices = self.get_invoice_objects()
            for invoice in invoices:
                if invoice.file:
                    invoices_urls.append(util_absolute_url(invoice.file.url))
        return invoices_urls

    # This method returns all cancellation reasons list
    def get_cancellation_reason(self):
        return CancellationReason.objects.filter(Q(type=Order.LAB_PRODUCT_ID) | Q(type__isnull=True),
                                                 visible_on_front_end=True)
    # @staticmethod
    # def get_upcoming_appointment_serialized(user_id):
    #     response_appointment = LabAppointment.get_upcoming_appointment(user_id)
    #     appointment = diagnostic_serializers.LabAppointmentUpcoming(response_appointment, many=True)
    #     return appointment.data

    # Get upcoming lab appointments of a user
    @classmethod
    def get_upcoming_appointment(cls, user_id):
        current_time = timezone.now()
        appointments = LabAppointment.objects.filter(time_slot_start__gte=current_time, user_id=user_id).exclude(
            status__in=[LabAppointment.CANCELLED, LabAppointment.COMPLETED]).prefetch_related('tests', 'lab', 'profile')
        return appointments

    # Get cancellation reason data
    def get_serialized_cancellation_reason(self):
        res = []
        for cr in self.get_cancellation_reason():
            res.append({'id': cr.id, 'name': cr.name, 'is_comment_needed': cr.is_comment_needed})
        return res

    # Get lab appointment report urls
    def get_report_urls(self):
        reports = self.reports.all()
        report_file_links = set()
        for report in reports:
            report_file_links = report_file_links.union(
                set([report_file.name.url for report_file in report.files.all() if report_file.name.url.rsplit('.',1)[1].lower() != 'xml']))
        report_file_links = [util_absolute_url(report_file_link) for report_file_link in report_file_links]
        return list(report_file_links)

    # Get file type and url of report
    def get_report_type(self):
        from ondoc.common.utils import get_file_mime_type
        resp = []
        for pres in self.reports.all():
            for pf in pres.files.all():
                file = pf.name
                mime_type = get_file_mime_type(file)
                if not mime_type == None:
                    file_url = pf.name.url
                    resp.append({"url": file_url, "type": mime_type})
        return resp

    # Get all uploaded reports of lab appointment
    def get_reports(self):
        return self.reports.all()

    # This method provides allowed actions of an appointment
    def allowed_action(self, user_type, request):
        allowed = []
        if self.status == self.CREATED:
            return [self.CANCELLED]
            # if user_type == User.CONSUMER:
            #     return [self.CANCELLED]
            # return []

        current_datetime = timezone.now()
        first_time_slot = None

        if self.time_slot_start:
            first_time_slot = self.time_slot_start
        # else:
        #     first_time_slot_test = self.test_mappings.order_by('time_slot_start').first()
        #     if first_time_slot_test:
        #         first_time_slot = first_time_slot_test.time_slot_start

        if first_time_slot:
            if user_type == User.CONSUMER and current_datetime <= first_time_slot:
                if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_LAB, self.RESCHEDULED_PATIENT):
                    allowed = [self.RESCHEDULED_PATIENT]
                    if all([x.is_cancellable for x in self.tests.all()]):
                        allowed += [self.CANCELLED]
            if user_type == User.DOCTOR and first_time_slot.date() >= current_datetime.date():
                if self.status in [self.BOOKED, self.RESCHEDULED_PATIENT]:
                    allowed = [self.ACCEPTED, self.RESCHEDULED_LAB]
                elif self.status == self.ACCEPTED:
                    allowed = [self.RESCHEDULED_LAB, self.COMPLETED]
                elif self.status == self.RESCHEDULED_LAB:
                    allowed = [self.ACCEPTED]

        return allowed

    # Check if notification needs to be send or not
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

    # Get lab admin users
    def get_lab_admins(self):
        if self.lab.network and self.lab.network.manageable_lab_network_admins.filter(is_disabled=False).exists():
            return [admin.user for admin in self.lab.network.manageable_lab_network_admins.filter(is_disabled=False)
                    if admin.user]
        else:
            return [admin.user for admin in self.lab.manageable_lab_admins.filter(is_disabled=False)
                    if admin.user]

    # Check if appointment booked by mobile app
    def created_by_native(self):
        from packaging.version import parse
        child_order = Order.objects.filter(reference_id=self.id).first()
        parent_order = None
        from_app = False

        if child_order:
            parent_order = child_order.parent

        if parent_order and parent_order.visitor_info:
            from_app = parent_order.visitor_info.get('from_app', False)
            app_version = parent_order.visitor_info.get('app_version', None)

        if from_app and app_version and parse(app_version) < parse('1.2'):
            return True
        else:
            return False

    # Check if appointment booked through salespoint
    def booked_by_spo(self):
        if self.spo_data:
            return True

        return False

    # Check if appointment is for integrated lab
    def is_part_of_integration(self):
        network_id = None
        if self.lab and self.lab.network and self.lab.network.id:
            network_id = self.lab.network.id

        if network_id == settings.THYROCARE_NETWORK_ID:
            return True
        elif network_id == settings.LAL_PATH_NETWORK_ID:
            return True

        return False

    # Check if appointment can be pushed to integrator
    def can_push_to_integrator(self):
        network_id = None
        if self.lab and self.lab.network and self.lab.network.id:
            network_id = self.lab.network.id

        if network_id == settings.THYROCARE_NETWORK_ID and settings.THYROCARE_INTEGRATION_ENABLED:
            return True
        elif network_id == settings.LAL_PATH_NETWORK_ID and settings.LAL_PATH_INTEGRATION_ENABLED:
            return True

        return False

    # Check notification can be sent to provider or not
    def is_provider_notification_allowed(self, old_instance):
        if old_instance.status == OpdAppointment.CREATED and self.status == OpdAppointment.CANCELLED:
            return False
        else:
            return True

    def app_commit_tasks(self, old_instance, push_to_matrix, push_to_integrator):
        if old_instance is None:
            try:
                create_ipd_lead_from_lab_appointment.apply_async(({'obj_id': self.id},),)
            except Exception as e:
                logger.error(str(e))

        if push_to_matrix:
            # Push the appointment data to the matrix
            try:
                push_appointment_to_matrix.apply_async(
                    ({'type': 'LAB_APPOINTMENT', 'appointment_id': self.id, 'product_id': 5,
                      'sub_product_id': 2},), countdown=5)
            except Exception as e:
                logger.error(str(e))

        if push_to_matrix and self.booked_by_spo():
            try:
                push_appointment_to_spo.apply_async(({'type': 'LAB_APPOINTMENT', 'appointment_id': self.id, 'product_id': 5,
                                                    'sub_product_id': 2},), countdown=5)
            except Exception as e:
                logger.error(str(e))

        if not self.created_by_native():
            if self.is_part_of_integration() and self.can_push_to_integrator():
                try:
                    if old_instance:
                        if (old_instance.status != self.CANCELLED and old_instance.status != self.CREATED and self.status == self.CANCELLED) or (old_instance.status == self.CREATED and self.status == self.BOOKED):
                            push_lab_appointment_to_integrator.apply_async(({'appointment_id': self.id},), countdown=5)
                    else:
                        push_lab_appointment_to_integrator.apply_async(({'appointment_id': self.id},), countdown=5)
                except Exception as e:
                    logger.error(str(e))

        # if push_for_mask_number:
        #     try:
        #         generate_appointment_masknumber.apply_async(({'type': 'LAB_APPOINTMENT', 'appointment_id': self.id},),
        #                                             countdown=5)
        #     except Exception as e:
        #         logger.error(str(e))

        if  ((self.status == self.BOOKED and old_instance and old_instance.status != self.BOOKED) or (not old_instance and self.status == self.BOOKED) or (self.is_to_send_notification(old_instance))):
        # if self.is_to_send_notification(old_instance):
            sent_to_provider = True
            if old_instance:
                sent_to_provider = self.is_provider_notification_allowed(old_instance)
            try:
                notification_tasks.send_lab_notifications_refactored.apply_async(({'appointment_id': self.id,
                                                                                         'is_valid_for_provider':
                                                                                             sent_to_provider},),
                                                                                countdown=1)
                # notification_tasks.send_lab_notifications_refactored(self.id)
                # notification_tasks.send_lab_notifications.apply_async(kwargs={'appointment_id': self.id}, countdown=1)
            except Exception as e:
                logger.error(str(e))

        if not old_instance or old_instance.status != self.status:
            try:
                notification_models.EmailNotification.ops_notification_alert(self, email_list=settings.OPS_EMAIL_ID,
                                                                             product=account_model.Order.LAB_PRODUCT_ID,
                                                                             alert_type=notification_models.EmailNotification.OPS_APPOINTMENT_NOTIFICATION)
            except Exception as e:
                logger.error(str(e))

        if not old_instance or self.status == self.CANCELLED:
            try:
                notification_tasks.update_coupon_used_count.apply_async()
            except Exception as e:
                logger.error(str(e))

        if self.status == self.COMPLETED and not self.is_rated:
            try:
                notification_tasks.send_opd_rating_message.apply_async(
                    kwargs={'appointment_id': self.id, 'type': 'lab'}, countdown=int(settings.RATING_SMS_NOTIF))
            except Exception as e:
                logger.error(str(e))

        if old_instance and old_instance.status != self.ACCEPTED and self.status == self.ACCEPTED:
            try:
                notification_tasks.lab_send_otp_before_appointment.apply_async(
                    (self.id, str(math.floor(self.time_slot_start.timestamp()))),
                    eta=self.time_slot_start - datetime.timedelta(
                        minutes=settings.TIME_BEFORE_APPOINTMENT_TO_SEND_OTP), )
                #notification_tasks.lab_send_after_appointment_confirmation.apply_async(
                #    (self.id, str(math.floor(self.time_slot_start.timestamp()))),
                #    eta=self.time_slot_start + datetime.timedelta(
                #        minutes=settings.TIME_AFTER_APPOINTMENT_TO_SEND_CONFIRMATION), )
                #notification_tasks.lab_send_after_appointment_confirmation.apply_async(
                #    (self.id, str(math.floor(self.time_slot_start.timestamp())), True),
                #    eta=self.time_slot_start + datetime.timedelta(
                #        minutes=settings.TIME_AFTER_APPOINTMENT_TO_SEND_SECOND_CONFIRMATION), )
                #notification_tasks.lab_send_after_appointment_confirmation.apply_async(
                #    (self.id, str(math.floor(self.time_slot_start.timestamp())), True),
                #    eta=self.time_slot_start + datetime.timedelta(
                #        minutes=settings.TIME_AFTER_APPOINTMENT_TO_SEND_THIRD_CONFIRMATION), )
                # notification_tasks.lab_send_otp_before_appointment(self.id, self.time_slot_start)
            except Exception as e:
                logger.error(str(e))

        if not old_instance:
            try:
                txn_obj = self.get_transaction()
                if txn_obj and txn_obj.is_preauth():
                    notification_tasks.send_capture_payment_request.apply_async(
                        (Order.LAB_PRODUCT_ID, self.id), eta=timezone.localtime() + datetime.timedelta(hours=int(settings.PAYMENT_AUTO_CAPTURE_DURATION)), )
            except Exception as e:
                logger.error(str(e))

        if old_instance and old_instance.status != self.COMPLETED and self.status == self.COMPLETED:
            self.check_merchant_payout_action()

        # if (self.status == self.BOOKED and old_instance and old_instance.status != self.BOOKED) or (old_instance and self.status==self.BOOKED):
        #     try:
        #         notification_tasks.lab_send_notification_before_appointment.apply_async((self.id, self.time_slot_start.timestamp(),),
        #             eta=self.time_slot_start - datetime.timedelta(minutes=settings.TIME_BEFORE_APPOINTMENT_TO_SEND_NOTIFICATION), )
        #     except Exception as e:
        #         logger.error(str(e))
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

    # Check appointment is fraud or not when booked using insurance
    @property
    def is_fraud_appointment(self):
        if not self.insurance:
            return False
        content_type = ContentType.objects.get_for_model(LabAppointment)
        appointment = Fraud.objects.filter(content_type=content_type, object_id=self.id).first()
        if appointment:
            return True
        else:
            return False

    # Get home pickup address of patient if lab test is home pickup
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
        if database_instance and (database_instance.status == self.COMPLETED or database_instance.status == self.CANCELLED) \
                and (self.status != database_instance.status):
            raise Exception('Cancelled or Completed appointment cannot be saved')

        try:
            if (self.payment_type != OpdAppointment.INSURANCE and self.status == self.COMPLETED and
                    (not database_instance or database_instance.status != self.status) and not self.outstanding):
                out_obj = self.outstanding_create()
                self.outstanding = out_obj
        except Exception as e:
            logger.error("Error while creating outstanding for lab- " + str(e))

        try:
            # while completing appointment
            if database_instance and database_instance.status != self.status and self.status == self.COMPLETED:
                # add a merchant_payout entry
                if self.merchant_payout is None and self.payment_type not in [OpdAppointment.COD] and \
                        not self.is_fraud_appointment:
                    self.save_merchant_payout()
                # credit cashback if any
                if self.cashback is not None and self.cashback > 0:
                    ConsumerAccount.credit_cashback(self.user, self.cashback, database_instance,
                                                        Order.LAB_PRODUCT_ID)
                # credit referral cashback if any
                UserReferred.credit_after_completion(self.user, database_instance, Order.LAB_PRODUCT_ID)

        except Exception as e:
            logger.error("Error while saving payout mercahnt for lab- " + str(e))

        push_to_matrix = True
        if database_instance and self.status == database_instance.status and self.time_slot_start == database_instance.time_slot_start:
            push_to_matrix = False
        else:
            push_to_matrix = True

        # push_for_mask_number = True
        # if self.time_slot_start != LabAppointment.objects.get(pk=self.id).time_slot_start:
        #     push_for_mask_number = True
        # else:
        #     push_for_mask_number = False

        # push_to_matrix = kwargs.get('push_again_to_matrix', True)
        # if 'push_again_to_matrix' in kwargs.keys():
        #     kwargs.pop('push_again_to_matrix')

        # Pushing every status to the Appointment history
        push_to_history = False
        if self.id and self.status != LabAppointment.objects.get(pk=self.id).status:
            push_to_history = True
        elif self.id is None:
            push_to_history = True

        responsible_user=None
        source=None
        if kwargs.get('source'):
            source = kwargs.pop('source')
        if kwargs.get('responsible_user'):
            responsible_user = kwargs.pop('responsible_user')

        super().save(*args, **kwargs)

        if push_to_history:
            if responsible_user:
                self._responsible_user = responsible_user
            if source:
                self._source = source
            AppointmentHistory.create(content_object=self)

        # Push the appointment to the integrator.
        push_to_integrator = kwargs.get('push_to_integrator', True)
        if 'push_to_integrator' in kwargs.keys():
            kwargs.pop('push_to_integrator')

        transaction.on_commit(lambda: self.app_commit_tasks(database_instance, push_to_matrix, push_to_integrator))

    # This method creates payout for provider when appointment is complete
    def save_merchant_payout(self):
        if self.payment_type in [OpdAppointment.COD]:
            raise Exception("Cannot create payout for COD appointments")

        payout_amount = self.agreed_price
        if self.is_home_pickup:
            payout_amount += self.home_pickup_charges

        tds = self.get_tds_amount()
        # Update Net Revenue
        self.update_net_revenues(tds)

        payout_data = {
            "charged_amount" : self.effective_price,
            "payable_amount" : payout_amount,
            "booking_type": Order.LAB_PRODUCT_ID,
            "tds_amount": tds
        }

        merchant_payout = MerchantPayout(**payout_data)
        merchant_payout.paid_to = self.get_merchant
        merchant_payout.content_object = self.get_billed_to
        merchant_payout.save()
        self.merchant_payout = merchant_payout

        # TDS Deduction
        if tds > 0:
            merchant = self.get_merchant
            MerchantTdsDeduction.objects.create(merchant=merchant, tds_deducted=tds,
                                                financial_year=settings.CURRENT_FINANCIAL_YEAR,
                                                merchant_payout=merchant_payout)

    # This method is use to check if settlement amount is already paid(advance payment) to provider
    # This method is a part of advance merchant payout and create dummy txn if appointment's payment type is insurance
    def check_merchant_payout_action(self):
        from ondoc.notification.tasks import set_order_dummy_transaction
        # check for advance payment
        merchant_payout = self.merchant_payout
        if merchant_payout:
            if self.payment_type == 1 and merchant_payout.merchant_has_advance_payment():
                merchant_payout.update_payout_for_advance_available()

            if self.insurance and merchant_payout.id and not merchant_payout.is_insurance_premium_payout() and merchant_payout.status == merchant_payout.PENDING:
                try:
                    has_txn, order_data, appointment = merchant_payout.has_transaction()
                    if not has_txn:
                        transaction.on_commit(lambda: set_order_dummy_transaction.apply_async((order_data.id, appointment.user_id,)))
                except Exception as e:
                    logger.error(str(e))

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

    # This method is use to create appointment
    @classmethod
    def create_appointment(cls, appointment_data, responsible_user=None, source=None):
        from ondoc.prescription.models import AppointmentPrescription
        insurance = appointment_data.get('insurance')
        plus_user = appointment_data.get('plus_plan')
        appointment_status = OpdAppointment.BOOKED

        if insurance and insurance.is_valid():
            mrp = Decimal(0)

            for extras in appointment_data.get('extra_details',[]):
                agreed_price = extras.get('custom_agreed_price') if extras.get('custom_agreed_price') != 'None' else extras.get('computed_agreed_price', 0)
                if agreed_price == 'None':
                    agreed_price = 0
                mrp = mrp + Decimal(agreed_price)

            insurance_limit_usage_data = insurance.validate_limit_usages(mrp)
            appointment_status = OpdAppointment.CREATED
            # if insurance_limit_usage_data.get('created_state'):
            #     appointment_status = OpdAppointment.CREATED

        if plus_user and plus_user.plan and plus_user.plan.is_prescription_required:
            appointment_status = OpdAppointment.CREATED

        otp = random.randint(1000, 9999)
        appointment_data["payment_status"] = OpdAppointment.PAYMENT_ACCEPTED
        appointment_data["status"] = appointment_status
        appointment_data["otp"] = otp
        appointment_data["user_plan_used"] = appointment_data.pop("user_plan", None)
        appointment_data["action_data"] = dict()
        appointment_data["action_data"]["selected_timings_type"] = appointment_data.pop('selected_timings_type', 'separate')
        lab_ids = appointment_data.pop("lab_test")
        # test_timeslots = appointment_data.pop('test_time_slots') if appointment_data.get('test_time_slots', []) else []
        coupon_list = appointment_data.pop("coupon", None)
        coupon_data = {
            "random_coupons": appointment_data.pop("coupon_data", [])
        }
        extra_details = deepcopy(appointment_data.pop("extra_details", None))

        prescription_objects = deepcopy(appointment_data.pop("prescription_list", []))
        prescription_id_list = []
        for prescription in prescription_objects:
            prescription_id_list.append(prescription.get('prescription').id)

        # app_obj = cls.objects.create(**appointment_data)
        _responsible_user = None
        if responsible_user:
            _responsible_user = auth_model.User.objects.filter(id=responsible_user).first()
        app_obj = cls(**appointment_data)
        if _responsible_user and source:
            app_obj.save(responsible_user=_responsible_user, source=source)
        else:
            app_obj.save()
        AppointmentPrescription.update_with_appointment(app_obj, prescription_id_list)
        test_mappings = []
        for test in extra_details:
            test.pop('name', None)
            test['test_id'] = test.pop('id')
            test['appointment_id'] = app_obj.id
            test['mrp'] = Decimal(test['mrp']) if test['mrp'] != 'None' else None
            test['custom_deal_price'] = Decimal(test['custom_deal_price']) if test['custom_deal_price'] != 'None' else None
            test['computed_deal_price'] = Decimal(test['computed_deal_price']) if test['computed_deal_price'] != 'None' else None
            test['custom_agreed_price'] = Decimal(test['custom_agreed_price']) if test['custom_agreed_price'] != 'None' else None
            test['computed_agreed_price'] = Decimal(test['computed_agreed_price']) if test['computed_agreed_price'] != 'None' else None
            # test['time_slot_start'] = test['time_slot_start'] if test['time_slot_start'] != 'None' else None
            # test['is_home_pickup'] = test['is_home_pickup'] if test['is_home_pickup'] != 'None' else False
            test_mappings.append(LabAppointmentTestMapping(**test))
        LabAppointmentTestMapping.objects.bulk_create(test_mappings)
        app_obj.lab_test.add(*lab_ids)
        if coupon_list:
            app_obj.coupon.add(*coupon_list)
        app_obj.coupon_data = coupon_data
        return app_obj

    # Update lab appointment status when reschedule by lab
    def action_rescheduled_lab(self):
        self.status = self.RESCHEDULED_LAB
        self.save()
        return self

    # Update lab appointment when reschedule by patient
    def action_rescheduled_patient(self, data):
        self.status = self.RESCHEDULED_PATIENT
        self.time_slot_start = data.get('time_slot_start')
        self.agreed_price = data.get('agreed_price', self.agreed_price)
        self.price = data.get('price', self.price)
        self.deal_price = data.get('deal_price', self.deal_price)
        self.effective_price = data.get('effective_price', self.effective_price)
        if data.get('selected_timings_type'):
            self.action_data = dict()
            self.action_data['selected_timings_type'] = data.get('selected_timings_type', '')

        self.save()

        if data and data.get('test_time_slots'):
            for test_time_slot in data.get('test_time_slots'):
                appointment_test = self.test_mappings.filter(test_id=test_time_slot.get('test_id')).first()
                appointment_test.time_slot_start = test_time_slot.get('time_slot_start')
                appointment_test.save()

    # Update lab appointment status when appointment accepted
    def action_accepted(self):
        self.status = self.ACCEPTED
        self.save()

    # Update appointment status as per ivr
    def update_ivr_status(self, status):
        if status == self.status:
            return True, ""

        if self.status in [LabAppointment.COMPLETED, LabAppointment.CANCELLED]:
            return False, 'Appointment cannot be accepted as current status is %s' % str(self.status)

        if status == LabAppointment.ACCEPTED:
            # Constraints: Check if appointment can be accepted or not.
            if self.time_slot_start < timezone.now():
                return False, 'Appointment cannot be accepted as time slot has been expired'

            self.action_accepted()

        elif status == LabAppointment.COMPLETED:
            self.action_completed()

        return True, ""

    # This method is called when appointment is cancelled to initiate refund
    @transaction.atomic
    def action_cancelled(self, refund_flag=1):
        old_instance = LabAppointment.objects.get(pk=self.id)
        if old_instance.status != self.CANCELLED:
            self.status = self.CANCELLED
            self.save()
            initiate_refund = old_instance.preauth_process(refund_flag)
            self.action_refund(refund_flag, initiate_refund)

    # Get appointment amount break up.
    def get_cancellation_breakup(self):
        wallet_refund = cashback_refund = 0
        if self.money_pool:
            wallet_refund, cashback_refund = self.money_pool.get_refund_breakup(self.effective_price)
        elif self.price_data:
            wallet_refund = self.price_data["wallet_amount"]
            cashback_refund = self.price_data["cashback_amount"]
        else:
            wallet_refund = self.effective_price

        return wallet_refund, cashback_refund

    # This method is called when appointment is completed
    def action_completed(self):
        self.status = self.COMPLETED
        out_obj = None
        if self.payment_type != OpdAppointment.INSURANCE:
            if not self.outstanding:
                out_obj = self.outstanding_create()
                self.outstanding = out_obj
        self.save()

        try:
            txn_obj = self.get_transaction()
            if txn_obj and txn_obj.is_preauth():
                notification_tasks.send_capture_payment_request.apply_async(
                    (Order.LAB_PRODUCT_ID, self.id), eta=timezone.localtime(), )
        except Exception as e:
            logger.error(str(e))

        if self.has_lensfit_coupon_used():
            notification_tasks.send_lensfit_coupons.apply_async((self.id, self.PRODUCT_ID, NotificationAction.SEND_LENSFIT_COUPON), countdown=5)

    # To create outstanding - Old merchant payout
    def outstanding_create(self):
        admin_obj, out_level = self.get_billable_admin_level()
        app_outstanding_fees = self.lab_payout_amount()
        out_obj = Outstanding.create_outstanding(admin_obj, out_level, app_outstanding_fees)
        return out_obj

        # self.status = self.COMPLETED
        # if self.payment_type != self.INSURANCE:
        #     Outstanding.create_outstanding(self)

    # To check amount to be paid at lab level or network level - Not in use
    def get_billable_admin_level(self):
        if self.lab.network and self.lab.network.is_billing_enabled:
            return self.lab.network, Outstanding.LAB_NETWORK_LEVEL
        else:
            return self.lab, Outstanding.LAB_LEVEL

    # Amount to be paid to provider.
    def lab_payout_amount(self):
        amount = 0
        if self.payment_type == OpdAppointment.COD:
            amount = (-1)*(self.effective_price - self.agreed_price - self.home_pickup_charges)
        elif self.payment_type == OpdAppointment.PREPAID:
            amount = self.agreed_price + self.home_pickup_charges
        return amount

    # Calculate booking revenue
    def get_booking_revenue(self):
        if self.payment_type == 3:
            booking_net_revenue = 0
        else:
            wallet_amount = self.effective_price
            price_data = self.price_data
            if price_data:
                w_amount = price_data.get('wallet_amount', None)
                if w_amount is not None:
                    wallet_amount = w_amount

            agreed_price = self.agreed_price
            if self.is_home_pickup:
                agreed_price += self.home_pickup_charges
            booking_net_revenue = wallet_amount - agreed_price
            if booking_net_revenue < 0:
                booking_net_revenue = 0

        return booking_net_revenue

    # Billing Summary - Old
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

    # Appointment Billing Summary
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

        # if permission:
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

    # Get lab or lab network for payout
    @property
    def get_billed_to(self):
        network = self.lab.network
        if network and network.is_billing_enabled:
            return network
        else:
            return self.lab

    # Get merchant for payout
    @property
    def get_merchant(self):
        billed_to = self.get_billed_to
        if billed_to:
            merchant = billed_to.merchant.first()
            if merchant:
                return merchant.merchant
        return None

    # Get price details of appointment
    @classmethod
    def get_price_details(cls, data, plus_user=None):
        import functools

        deal_price_calculation = Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                      When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
        agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                        When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))
        lab_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"],
                                                            test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab_pricing_group__labs').annotate(total_mrp=Sum("mrp"),
                                                                                     total_deal_price=Sum(
                                                                                         deal_price_calculation),
                                                                                     total_agreed_price=Sum(
                                                                                         agreed_price_calculation),
                                                                                     total_insurance_agreed_price=Sum('insurance_agreed_price'))
        total_convenience_charge = None
        if plus_user:
            convenience_charge_list = list(map(lambda x: x.calculate_convenience_charge(plus_user.plan), lab_test_queryset))
            total_convenience_charge = functools.reduce(lambda a, b: a+b, convenience_charge_list)

        total_insurance_agreed_price = total_agreed = total_deal_price = total_mrp = effective_price = home_pickup_charges = 0
        if temp_lab_test:
            total_mrp = temp_lab_test[0].get("total_mrp", 0)
            total_agreed = temp_lab_test[0].get("total_agreed_price", 0)
            total_deal_price = temp_lab_test[0].get("total_deal_price", 0)
            total_insurance_agreed_price = temp_lab_test[0].get("total_insurance_agreed_price", 0)
            effective_price = total_deal_price
            if data["is_home_pickup"] and data["lab"].is_home_collection_enabled:
                effective_price += data["lab"].home_pickup_charges
                home_pickup_charges = data["lab"].home_pickup_charges

        coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(data, effective_price)

        if data.get("payment_type") in [OpdAppointment.PREPAID]:
            if coupon_discount >= effective_price:
                effective_price = 0
            else:
                effective_price = effective_price - coupon_discount

        if data.get("payment_type") in [OpdAppointment.COD, OpdAppointment.PLAN]:
            effective_price = 0
            coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []

        if data.get("payment_type") in [OpdAppointment.INSURANCE]:
            effective_price = effective_price
            total_agreed = total_insurance_agreed_price if  total_insurance_agreed_price and total_insurance_agreed_price > 0 else total_agreed
            coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []

        if data.get("payment_type") in [OpdAppointment.VIP, OpdAppointment.GOLD]:
            price_data = {"mrp": total_mrp, "fees": total_agreed, "deal_price": total_deal_price, "cod_deal_price": total_deal_price}
            profile = data.get('profile')
            vip_convenience_amount = 0
            if profile:
                plus_membership = profile.get_plus_membership
                price_engine = get_price_reference(plus_membership, "LABTEST")
                if not price_engine:
                    price = effective_price
                else:
                    price = price_engine.get_price(price_data)
                # vip_convenience_amount = plus_membership.plan.get_convenience_charge(price, "LABTEST")
                plus_membership_plan = plus_membership.plan if plus_membership else None
                vip_convenience_amount = total_convenience_charge
                test = data['test_ids']
                entity = "LABTEST" if not test[0].is_package else "PACKAGE"
                engine = get_class_reference(plus_membership, entity)
                if engine:
                    # engine_response = engine.validate_booking_entity(cost=effective_price, id=data['test_ids'][0].id)
                    engine_response = engine.validate_booking_entity(cost=price, id=data['test_ids'][0].id, mrp=effective_price, deal_price=total_deal_price, price_engine_price=price)
                    effective_price = engine_response.get('amount_to_be_paid')
                    # effective_price = effective_price + vip_convenience_amount
                else:
                    effective_price = effective_price
            else:
                effective_price = effective_price

            if vip_convenience_amount:
                effective_price += vip_convenience_amount
            # coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []
            coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(data, effective_price)

            if coupon_discount >= effective_price:
                effective_price = 0
            else:
                effective_price = effective_price - coupon_discount

        return {
            "deal_price" : total_deal_price,
            "mrp" : total_mrp,
            "fees" : total_agreed,
            "effective_price" :effective_price,
            "coupon_discount" : coupon_discount,
            "coupon_cashback" : coupon_cashback,
            "coupon_list" : coupon_list,
            "home_pickup_charges" : home_pickup_charges,
            "coupon_data" : { "random_coupon_list" : random_coupon_list },
            "total_convenience_charge": total_convenience_charge
        }

    # This method is use to create appointment data
    @classmethod
    def create_fulfillment_data(cls, user, data, price_data, request):
        from ondoc.api.v1.auth.serializers import AddressSerializer
        from ondoc.insurance.models import UserInsurance
        from ondoc.salespoint.models import SalespointTestmapping, SalesPoint

        lab_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"], test__in=data['test_ids'])
        test_ids_list = list()
        extra_details = list()
        time_slot_details = ''
        test_time_slots = list()
        is_home_pickup = False
        pathology_home_pickup = False
        radiology_home_pickup = False
        time_slot_dict = dict()

        # if data.get('multi_timings_enabled'):
        #     for test_timing in data.get('test_timings'):
        #         test_id = test_timing.get('test').id
        #         test_data = dict()
        #         test_data['test_id'] = test_id
        #         time_slot_start = form_time_slot(test_timing["start_date"], test_timing["start_time"])
        #         test_data['time_slot_start'] = time_slot_start
        #         time_slot_dict[test_id] = time_slot_start
        #         test_data['is_home_pickup'] = test_timing.get('is_home_pickup')
        #         test_time_slots.append(test_data)
        #         if test_timing.get('type') == LabTest.PATHOLOGY:
        #             if not pathology_home_pickup:
        #                 pathology_home_pickup = test_timing.get('is_home_pickup')
        #         if test_timing.get('type') == LabTest.RADIOLOGY:
        #             if not radiology_home_pickup:
        #                 radiology_home_pickup = test_timing.get('is_home_pickup')
        # else:
        #     time_slot_details = form_time_slot(data["start_date"], data["start_time"])
        #     is_home_pickup = data["is_home_pickup"]

        time_slot_details = form_time_slot(data["start_date"], data["start_time"])
        is_home_pickup = data["is_home_pickup"]

        for obj in lab_test_queryset:
            test_ids_list.append(obj.id)
            home_pickup = False
            if obj.test.test_type == LabTest.PATHOLOGY:
                home_pickup = pathology_home_pickup
            elif obj.test.test_type == LabTest.RADIOLOGY:
                home_pickup = radiology_home_pickup
            extra_details.append({
                "id": str(obj.test.id),
                "name": str(obj.test.name),
                "custom_deal_price": str(obj.custom_deal_price),
                "computed_deal_price": str(obj.computed_deal_price),
                "mrp": str(obj.mrp),
                "computed_agreed_price": str(obj.computed_agreed_price),
                "custom_agreed_price": str(obj.custom_agreed_price),
                # "is_home_pickup": home_pickup,
                # "time_slot_start": str(time_slot_dict.get(obj.test.id)) if time_slot_dict.get(obj.test.id) else None
            })

        profile_detail = {
            "name": data["profile"].name,
            "gender": data["profile"].gender,
            "dob": str(data["profile"].dob),
        }
        payment_type = data.get("payment_type")
        effective_price = price_data.get("effective_price")
        # cart_data = data.get('cart_item') if data.get('cart_item') else None
        cart_data = data.get('cart_item').data if data.get('cart_item') and data.get('cart_item').data else None

        # is_appointment_insured = cart_data.get('is_appointment_insured', None)
        # insurance_id = cart_data.get('insurance_id', None)

        is_appointment_insured = False
        insurance_id = None
        booked_by = 'agent' if hasattr(request, 'agent') else 'user'
        user_insurance = UserInsurance.objects.filter(user=user).order_by('-id').first()
        if user_insurance and user_insurance.is_valid():
            insurance_resp = user_insurance.validate_insurance(data, booked_by=booked_by)
            if insurance_resp.get('is_insured', False):
                is_appointment_insured = True
                insurance_id = insurance_resp.get('insurance_id', None)

        if is_appointment_insured or (cart_data and cart_data.get('is_appointment_insured', None)):
            payment_type = OpdAppointment.INSURANCE
            effective_price = 0.0
        else:
            is_appointment_insured = False
            insurance_id = None
            if data["payment_type"] == OpdAppointment.INSURANCE:
                payment_type = OpdAppointment.PREPAID
            else:
                payment_type = data["payment_type"]

        # check if test mapped with affiliates
        mapped_with_affiliates = None
        source = data["utm_spo_tags"].get("utm_source", None)
        if source:
            mapped_with_affiliates = True
            affiliate = SalesPoint.objects.filter(name=data["utm_spo_tags"]["utm_source"]).first()
            if affiliate:
                for test_id in test_ids_list:
                    spo_mapping = SalespointTestmapping.objects.filter(salespoint_id=affiliate.id,
                                                                       available_tests_id=test_id).first()
                    if not spo_mapping:
                        mapped_with_affiliates = False

        if mapped_with_affiliates:
            spo_data = data["utm_spo_tags"]
        else:
            spo_data = {}

        utm_sbi_tags = data.get("utm_sbi_tags", {})

        cover_under_vip = False
        plus_user_id = None
        plus_user = user.active_plus_user

        if not plus_user and data.get('plus_plan'):
            plus_user = user.get_temp_plus_user

        mrp = price_data.get("mrp")
        convenience_amount = 0
        vip_amount_utilized = 0

        if plus_user:
            plus_user_resp = plus_user.validate_plus_appointment(data)
            cover_under_vip = plus_user_resp.get('cover_under_vip', False)
            vip_amount_utilized = plus_user_resp.get('vip_amount_deducted')
            plus_user_id = plus_user_resp.get('plus_user_id', None)
            convenience_amount = plus_user_resp.get('vip_convenience_amount', 0)

        if cover_under_vip and vip_amount_utilized > 0:
            # payment_type = OpdAppointment.VIP

            if plus_user.plan.is_gold:
                payment_type = OpdAppointment.GOLD
            else:
                payment_type = OpdAppointment.VIP

            plus_user_id = plus_user_resp.get('plus_user_id', None)
            # if cover_under_vip and cart_data and cart_data.get('cover_under_vip', None):
            # convenience_amount = plus_user.plan.get_convenience_charge(plus_user_resp['amount_to_be_paid'], "LABTEST")
            # convenience_amount = PlusPlans.get_default_convenience_amount(price_data, "LABTEST", default_plan_query=plus_user.plan)
            effective_price = plus_user_resp['amount_to_be_paid']
            # if not convenience_amount:
            #     convenience_amount = PlusPlans.get_default_convenience_amount(price_data, "LABTEST",
            #                                                                   default_plan_query=plus_user.plan)
            #     effective_price = plus_user_resp.get('amount_to_be_paid') + convenience_amount
            vip_amount_utilized = plus_user_resp['vip_amount_deducted']

            # utilization = plus_user.get_utilization
            # available_amount = int(utilization.get('available_package_amount', 0))
            # mrp = int(price_data.get('mrp'))

            # final_price = mrp + price_data['home_pickup_charges']

            # utilization_criteria, coverage = plus_user.can_package_be_covered_in_vip(None, mrp=final_price, id=data['test_ids'][0].id)
            #
            # if coverage:
            #     if utilization_criteria == UtilizationCriteria.COUNT:
            #         effective_price = 0
            #         vip_amount_utilized = final_price
            #     else:
            #         effective_price = cart_data.get('amount_to_be_paid', 0)
            #         vip_amount_utilized = available_amount if final_price >= available_amount else final_price

        else:
            plus_user_id = None
            cover_under_vip = False
            if data["payment_type"] == OpdAppointment.VIP:
                payment_type = OpdAppointment.PREPAID
            else:
                payment_type = data["payment_type"]

            vip_amount_utilized = 0

        fulfillment_data = {
            "lab": data["lab"],
            "user": user,
            "profile": data["profile"],
            "price": price_data.get("mrp"),
            "agreed_price": price_data.get("fees"),
            "deal_price": price_data.get("deal_price"),
            "effective_price": effective_price,
            "home_pickup_charges": price_data.get("home_pickup_charges"),
            "time_slot_start": time_slot_details,
            "is_home_pickup": is_home_pickup,
            "profile_detail": profile_detail,
            "status": LabAppointment.BOOKED,
            "payment_type": payment_type,
            "lab_test": test_ids_list,
            "extra_details": extra_details,
            "coupon": price_data.get("coupon_list"),
            "discount": int(price_data.get("coupon_discount")),
            "cashback": int(price_data.get("coupon_cashback")),
            "is_appointment_insured": is_appointment_insured,
            "insurance": insurance_id,
            "spo_data": spo_data,
            "cover_under_vip": cover_under_vip,
            "plus_plan": plus_user_id,
            'plus_amount': int(vip_amount_utilized),
            'vip_convenience_amount': convenience_amount,
            "coupon_data": price_data.get("coupon_data"),
            "prescription_list": data.get('prescription_list', []),
            "_responsible_user": data.get("_responsible_user", None),
            "_source": data.get("_source", None),
            "multi_timings_enabled": data.get('multi_timings_enabled'),
            "selected_timings_type": data.get('selected_timings_type'),
            "utm_sbi_tags": utm_sbi_tags
        }

        if data.get('included_in_user_plan', False):
            fulfillment_data.update({'user_plan': data.get('user_plan', None)})
        else:
            fulfillment_data.update({'user_plan': None})

        if is_home_pickup or pathology_home_pickup or radiology_home_pickup:
            address = Address.objects.filter(pk=data.get("address").id).first()
            address_serialzer = AddressSerializer(address)
            fulfillment_data.update({
                "address": address_serialzer.data,
                "is_home_pickup": True
            })
        return fulfillment_data

    # Save tracking event
    def trigger_created_event(self, visitor_info):
        from ondoc.tracking.models import TrackingEvent
        from ondoc.tracking.mongo_models import TrackingEvent as MongoTrackingEvent
        try:
            with transaction.atomic():
                event_data = TrackingEvent.build_event_data(self.user, TrackingEvent.LabAppointmentBooked, appointmentId=self.id, visitor_info=visitor_info)
                if event_data and visitor_info:
                    # TrackingEvent.save_event(event_name=event_data.get('event'), data=event_data, visit_id=visitor_info.get('visit_id'),
                    #                          user=self.user, triggered_at=datetime.datetime.utcnow())

                    if settings.MONGO_STORE:
                        MongoTrackingEvent.save_event(event_name=event_data.get('event'), data=event_data,
                                                 visit_id=visitor_info.get('visit_id'),
                                                 visitor_id=visitor_info.get('visitor_id'),
                                                 user=self.user, triggered_at=datetime.datetime.utcnow())

        except Exception as e:
            logger.error("Could not save triggered event - " + str(e))

    # This method is use to show appointment status of integrator in CRM if appointment is part of integration
    def integrator_order_status(self):
        from ondoc.integrations.models import IntegratorHistory

        lab_appointment_content_type = ContentType.objects.get_for_model(self)
        integrator_history = IntegratorHistory.objects.filter(object_id=self.id,
                                                              content_type=lab_appointment_content_type).order_by('id').last()
        if not integrator_history:
            return 'Not a part of Integration'

        return IntegratorHistory.STATUS_CHOICES[integrator_history.status - 1][1]

    # Use to show integrator booking number in CRM
    def thyrocare_booking_no(self):
        from ondoc.integrations.models import IntegratorResponse

        lab_appointment_content_type = ContentType.objects.get_for_model(self)
        integrator_response = IntegratorResponse.objects.filter(object_id=self.id,
                                                                content_type=lab_appointment_content_type).order_by('id').last()
        if not integrator_response:
            return 'Not Found'

        return [integrator_response.lead_id, integrator_response.integrator_order_id]

    # Use to show if appointment is accepted by agents or by integrator API
    def accepted_through(self):
        from ondoc.integrations.models import IntegratorHistory

        lab_appointment_content_type = ContentType.objects.get_for_model(self)
        integrator_history = IntegratorHistory.objects.filter(object_id=self.id,
                                                              content_type=lab_appointment_content_type).order_by('id').last()
        if not integrator_history:
            return 'Not Found'

        return integrator_history.accepted_through

    # Use to prepare matrix data of appointment for agents
    def get_matrix_data(self, order, product_id, sub_product_id):
        # policy_details = self.get_matrix_policy_data()
        appointment_details = self.get_matrix_appointment_data(order)

        request_data = {
            'DocPrimeUserId': self.user.id,
            'LeadID': self.matrix_lead_id if self.matrix_lead_id else 0,
            'Name': self.profile.name,
            'PrimaryNo': self.user.phone_number,
            'LeadSource': 'DocPrime',
            'EmailId': self.profile.email,
            'Gender': 1 if self.profile.gender == 'm' else 2 if self.profile.gender == 'f' else 0,
            'CityId': 0,
            'ProductId': product_id,
            'SubProductId': sub_product_id,
            'AppointmentDetails': appointment_details
        }
        return request_data

    def get_matrix_appointment_data(self, order):
        location = ''
        booking_url = '%s/admin/diagnostic/labappointment/%s/change' % (settings.ADMIN_BASE_URL, self.id)
        kyc = 1 if LabDocument.objects.filter(lab=self.lab, document_type__in=[LabDocument.CHEQUE, LabDocument.PAN]).distinct('document_type').count() == 2 else 0
        if self.lab.location:
            location = 'https://www.google.com/maps/search/?api=1&query=%f,%f' % (self.lab.location.y, self.lab.location.x)

        patient_address = ""
        if hasattr(self, 'address') and self.address:
            patient_address = resolve_address(self.address)

        profile_email = ''
        if self.profile:
            profile_email = self.profile.email

        mask_number_instance = self.mask_number.filter(is_deleted=False, is_mask_number=True).first()
        mask_number = ''
        if mask_number_instance:
            mask_number = mask_number_instance.mask_number

        provider_booking_id = ''
        merchant_code = ''
        is_ipd_hospital = '1' if self.lab.is_ipd_lab else '0'
        hospital_name = ''
        if self.lab and self.lab.is_ipd_lab and self.lab.related_hospital:
            hospital_name = self.lab.related_hospital.name
        service_name = ','.join([test_obj.test.name for test_obj in self.test_mappings.all()])
        location_verified = self.lab.is_location_verified
        provider_id = self.lab.id
        merchant = self.lab.merchant.all().last()
        if not merchant:
            merchant = self.lab.network.merchant.all().last()

        if merchant:
            merchant_code = merchant.id

        if self.lab and self.lab.network and self.lab.network.id == settings.THYROCARE_NETWORK_ID:
            integrator_obj = self.integrator_response.all().first()
            if integrator_obj:
                provider_booking_id = integrator_obj.integrator_order_id

        order_id = order.id if order else None
        dob_value = ''
        try:
            dob_value = datetime.datetime.strptime(self.profile_detail.get('dob'), "%Y-%m-%d").strftime("%d-%m-%Y") \
                if self.profile_detail.get('dob', None) else ''
        except Exception as e:
            pass

        appointment_type = 'Lab Visit'
        is_home_pickup = 0
        home_pickup_address = None
        if self.is_home_pickup:
            is_home_pickup = 1
            appointment_type = 'Home Visit'
            home_pickup_address = self.get_pickup_address()

        report_uploaded = 0
        report_sent = None
        reports = self.get_reports()
        if reports:
            report_file = reports.first().files.first()
            if report_file:
                report_uploaded = 1
                report_sent = report_file.created_at.timestamp()

        merchant_payout = self.merchant_payout_data()
        accepted_history = self.appointment_accepted_history()
        user_insurance = self.insurance
        mobile_list = self.get_matrix_spoc_data()
        refund_data = self.refund_details_data()

        from ondoc.ratings_review.models import RatingsReview
        appointment_rating = RatingsReview.objects.filter(appointment_id=self.id).first()
        rating = appointment_rating.ratings if appointment_rating else 0
        if self.lab and self.lab.rating_data:
            avg_rating = self.lab.rating_data.get('avg_rating', 0)
        else:
            avg_rating = 0

        if avg_rating is None:
            avg_rating = 0
        unsatisfied_customer = ""
        if rating and rating > 0:
            if rating < 3:
                unsatisfied_customer = 'Yes'
            else:
                unsatisfied_customer = 'No'

        insurance_link = None
        if user_insurance:
            insurance_link = '%s/admin/insurance/userinsurance/%s/change' % (settings.ADMIN_BASE_URL, user_insurance.id)

        appointment_details = {
            'IPDHospital': is_ipd_hospital,
            'IsInsured': 'yes' if user_insurance else 'no',
            'PolicyLink': str(insurance_link),
            'InsurancePolicyNumber': str(user_insurance.policy_number) if user_insurance else None,
            'AppointmentStatus': self.status,
            'Age': self.calculate_age(),
            'Email': profile_email,
            'VirtualNo': mask_number,
            'OTP': '',
            'KYC': kyc,
            'Location': location,
            'PaymentType': self.payment_type,
            'PaymentTypeId': self.payment_type,
            'PaymentStatus': 300,
            'OrderID': order_id if order_id else 0,
            'DocPrimeBookingID': self.id,
            'BookingDateTime': int(self.created_at.timestamp()),
            'AppointmentDateTime': int(self.time_slot_start.timestamp()),
            'BookingType': 'DC',
            'AppointmentType': appointment_type,
            'IsHomePickUp': is_home_pickup,
            'HomePickupAddress': home_pickup_address,
            'PatientName': self.profile_detail.get("name", ''),
            'PatientAddress': patient_address,
            'ProviderName': getattr(self, 'lab').name,
            'ServiceName': service_name,
            'InsuranceCover': 0,
            'MobileList': mobile_list,
            'BookingUrl': booking_url,
            'Fees': float(self.agreed_price),
            'EffectivePrice': float(self.effective_price),
            'MRP': float(self.price),
            'DealPrice': float(self.deal_price),
            'DOB': dob_value,
            'ProviderAddress': self.lab.get_lab_address(),
            'ProviderID': provider_id,
            'ProviderBookingID': provider_booking_id,
            'MerchantCode': merchant_code,
            'ProviderPaymentStatus': merchant_payout['provider_payment_status'],
            'PaymentURN': merchant_payout['payment_URN'],
            'Amount': float(merchant_payout['amount']) if merchant_payout['amount'] else None,
            'SettlementDate': merchant_payout['settlement_date'],
            'LocationVerified': location_verified,
            'ReportUploaded': report_uploaded,
            'Reportsent': int(report_sent) if report_sent else None,
            'AcceptedBy': accepted_history['source'],
            'AcceptedPhone': accepted_history['accepted_phone'],
            "CustomerStatus": refund_data['customer_status'],
            "RefundPaymentMode": float(refund_data['original_payment_mode_refund']) if refund_data['original_payment_mode_refund'] else None,
            "RefundToWallet": float(refund_data['promotional_wallet_refund']) if refund_data['promotional_wallet_refund'] else None,
            "RefundInitiationDate": int(refund_data['refund_initiated_at']) if refund_data['refund_initiated_at'] else None,
            "RefundURN": refund_data['refund_urn'],
            "HospitalName": hospital_name,
            "Rating": rating,
            "AvgRating": avg_rating,
            "UnsatisfiedCustomer": unsatisfied_customer
        }
        return appointment_details

    def get_matrix_spoc_data(self):
        mobile_list = list()
        # if self.insurance_id:
        #     auto_ivr_enabled = False
        # else:
        #     auto_ivr_enabled = self.lab.is_auto_ivr_enabled()

        auto_ivr_enabled = self.lab.is_auto_ivr_enabled()
        for contact_person in self.lab.labmanager_set.all():
            number = ''
            if contact_person.number:
                number = str(contact_person.number)
            if number:
                number = int(number)

            if number:
                contact_type = dict(contact_person.CONTACT_TYPE_CHOICES)[contact_person.contact_type]
                contact_name = contact_person.name
                mobile_list.append({'MobileNo': number,
                                    'Name': contact_name,
                                    'DesignationID': contact_person.contact_type,
                                    'AutoIVREnable': str(auto_ivr_enabled).lower(),
                                    'Type': 3})

        # Lab mobile number
        mobile_list.append({'MobileNo': self.lab.primary_mobile, 'Name': self.lab.name, 'Type': 3})

        # User mobile number
        mobile_list.append({'MobileNo': self.user.phone_number, 'Name': self.profile.name, 'Type': 1})

        return mobile_list

    # Prepare ipd lead data
    def convert_ipd_lead_data(self):
        result = {}
        result['hospital'] = self.lab.related_hospital
        # result['lab'] = self.lab
        result['user'] = self.user
        result['payment_amount'] = self.deal_price
        if self.user:
            result['name'] = self.user.full_name
            result['phone_number'] = self.user.phone_number
            result['email'] = self.user.email
            default_user_profile = self.user.get_default_profile()
            if default_user_profile:
                result['gender'] = default_user_profile.gender
                result['dob'] = default_user_profile.dob
        result['data'] = {'lab_appointment_id': self.id}
        return result

    # Data for salespoint agents
    def get_spo_data(self, order, product_id, sub_product_id):
        tests = self.test_mappings.all()
        service_id = None
        if tests:
            service_id = tests.first().id
        dob_value = ''
        try:
            dob_value = datetime.datetime.strptime(self.profile_detail.get('dob'), "%Y-%m-%d").strftime("%Y-%m-%d") \
                if self.profile_detail.get('dob', None) else ''
        except Exception as e:
            pass

        appointment_details = self.get_matrix_appointment_data(order)
        appointment_details['DocPrimeUserId'] = self.user.id
        appointment_details['LeadID'] = 0
        appointment_details['Name'] = self.profile.name
        appointment_details['PrimaryNo'] = self.user.phone_number
        appointment_details['LeadSource'] = 'DocPrime'
        appointment_details['EmailId'] = self.profile.email
        appointment_details['Gender'] = 1 if self.profile.gender == 'm' else 2 if self.profile.gender == 'f' else 0
        appointment_details['CityId'] = 0
        appointment_details['ProductId'] = product_id
        appointment_details['SubProductId'] = sub_product_id
        appointment_details['UtmTerm'] = self.spo_data.get('utm_term', '')
        appointment_details['UtmMedium'] = self.spo_data.get('utm_medium', '')
        appointment_details['UtmCampaign'] = self.spo_data.get('utm_campaign', '')
        appointment_details['UtmSource'] = self.spo_data.get('utm_source', '')
        appointment_details['LocationVerified'] = 1 if self.lab.is_location_verified else 0
        appointment_details['IsInsured'] = 1 if self.insurance else 0
        appointment_details['DOB'] = dob_value
        appointment_details['ServiceID'] = service_id

        appointment_details.pop('MobileList', None)
        return appointment_details

    def __str__(self):
        return "{}, {}".format(self.profile.name if self.profile else "", self.lab.name)

    # Get insured completed appointment count
    @classmethod
    def get_insured_completed_appointment(cls, insurance_obj):
        count = cls.objects.filter(user=insurance_obj.user, insurance=insurance_obj, status=cls.COMPLETED).count()
        return count

    # Get insured active appointment count
    @classmethod
    def get_insured_active_appointment(cls, insurance_obj):
        appointments = cls.objects.filter(~Q(status=cls.COMPLETED), ~Q(status=cls.CANCELLED), user=insurance_obj.user,
                                          insurance=insurance_obj)
        return appointments

    # Get insurance usage of a user
    @classmethod
    def get_insurance_usage(cls, insurance_obj, date=None):
        appointments = cls.objects.filter(user=insurance_obj.user, insurance=insurance_obj).exclude(status=cls.CANCELLED)
        if date:
            appointments = appointments.filter(created_at__date=date)

        count = appointments.count()
        data = appointments.aggregate(sum_amount=Sum('agreed_price'))
        sum = data.get('sum_amount', 0)
        sum = sum if sum else 0
        return {'count': count, 'sum': sum}

    # Get user's uploaded prescription
    def get_prescriptions(self, request):
        prescription_dict = {}
        files = []
        upd = None
        for pres in self.appointment_prescriptions.all():
            url = request.build_absolute_uri(pres.prescription_file.url) if pres.prescription_file else None
            files.append(url)
            upd = pres.updated_at
        prescription_dict = {
            "updated_at": upd,
            "files": files
        }
        return prescription_dict

    class Meta:
        db_table = "lab_appointment"


class CommonTest(TimeStampedModel):
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='commontest')
    # icon = models.ImageField(upload_to='diagnostic/common_test_icons', null=True)
    icon = models.FileField(upload_to='diagnostic/common_test_icons', blank=False, null=True, validators=[FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'svg'])])
    priority = models.PositiveIntegerField(default=0)
    svg_icon = models.FileField(upload_to='diagnostic/common_test_icons', blank=False, null=True,
                                validators=[FileExtensionValidator(allowed_extensions=['svg'])])

    def __str__(self):
        return "{}-{}".format(self.test.name, self.id)

    # Get common test for home page
    @classmethod
    def get_tests(cls, count):
        tests = cls.objects.select_related('test').filter(test__enable_for_retail=True, test__searchable=True).order_by('-priority')[:count]
        return tests


class CommonPackage(TimeStampedModel):
    package = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='commonpackage')
    icon = models.ImageField(upload_to='diagnostic/common_package_icons', null=True)
    priority = models.PositiveIntegerField(default=0)
    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, related_name='packagelab', null=True)
    svg_icon = models.FileField(upload_to='diagnostic/common_package_icons', null=True,
                                validators=[FileExtensionValidator(allowed_extensions=['svg'])])

    def __str__(self):
        return "{}-{}".format(self.package.name, self.id)

    class Meta:
        db_table = 'common_package'

    # Get common test for home page
    @classmethod
    def get_packages(cls, count):
        packages = cls.objects.select_related('lab', 'package') \
                              .prefetch_related('lab__lab_documents', 'lab__lab_pricing_group', 'lab__network') \
                              .filter(package__enable_for_retail=True, package__searchable=True).order_by('-priority')[:count]
        return packages


class CommonDiagnosticCondition(TimeStampedModel):
    name = models.CharField(max_length=200)
    lab_test = models.ManyToManyField(
        LabTest,
        through='DiagnosticConditionLabTest',
        through_fields=('diagnostic_condition', 'lab_test'),
    )
    priority = models.PositiveIntegerField(default=0)
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

    # This method is use to resize images
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
        database_instance = LabDocument.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        if self.document_type == LabDocument.LOGO:
            self.create_all_images()

            if database_instance and database_instance.name == self.name:
                pass
            else:
                self.send_change_logo_email()

    # Use to send email to internal members if logo of a lab changed
    def send_change_logo_email(self):
        from ondoc.communications.models import EMAILNotification
        try:
            emails = settings.LOGO_CHANGE_EMAIL_RECIPIENTS
            user_and_email = [{'user': None, 'email': email} for email in emails]
            email_notification = EMAILNotification(notification_type=NotificationAction.LAB_LOGO_CHANGE_MAIL,
                                                   context={'instance': self})
            email_notification.send(user_and_email)
        except Exception as e:
            logger.error(str(e))

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


@reversion.register()
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
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png', 'xml'])])

    def __str__(self):

        return "{}-{}".format(self.id, self.report.id if self.report and self.report.id else None)

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
    name = models.CharField(max_length=200, null=False, blank=False)
    # tests = models.ManyToManyField(LabTest)
    type = models.PositiveSmallIntegerField(choices=TEST_TYPE_CHOICES, null=True, blank=True)

    class Meta:
        db_table = 'lab_test_group'

    def __str__(self):
        return "{}".format(self.name)


@reversion.register()
class LabAppointmentTestMapping(models.Model):
    appointment = models.ForeignKey(LabAppointment, on_delete=models.CASCADE, related_name='test_mappings')
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='lab_appointment_mappings')
    mrp = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    computed_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    custom_agreed_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    computed_deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)
    custom_deal_price = models.DecimalField(max_digits=10, decimal_places=2, default=None, null=True, blank=True)

    def __str__(self):
        return '{}>{}'.format(self.appointment, self.test)

    class Meta:
        db_table = 'lab_appointment_test_mapping'


class LabTestGroupTiming(TimeStampedModel):
    TIME_CHOICES = LabTiming.TIME_CHOICES

    lab = models.ForeignKey(Lab, on_delete=models.CASCADE, null=True, blank=True, related_name='test_group_timings')
    lab_test_group = models.ForeignKey(LabTestGroup, on_delete=models.CASCADE, null=False)
    day = models.PositiveSmallIntegerField(blank=False, null=False,
                                           choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"),
                                                    (4, "Friday"), (5, "Saturday"), (6, "Sunday")])
    start = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    end = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    for_home_pickup = models.BooleanField(default=False)

    class Meta:
        db_table = "lab_test_group_timing"


class LabTestGroupMapping(TimeStampedModel):
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=False)
    lab_test_group = models.ForeignKey(LabTestGroup, on_delete=models.CASCADE, null=False)

    class Meta:
        db_table = "lab_test_group_mapping"


class TestParameterChat(TimeStampedModel):
    test = models.ForeignKey(LabTest, on_delete=models.CASCADE, null=True)
    age_from = models.PositiveIntegerField()
    age_to = models.PositiveIntegerField()
    gender = models.CharField(max_length=30, null=True, blank=True)
    min_range = models.DecimalField(blank=True, null=True, max_digits=10,decimal_places=2)
    max_range = models.DecimalField(blank=True, null=True, max_digits=10,decimal_places=2)
    test_name = models.CharField(blank=False, null=False, max_length=60)

    def __str__(self):
        return self.test_name

    class Meta:
        db_table = 'test_parameter_chat'


class LabTestThresholds(TimeStampedModel):
    class Colour(Choices):
        RED = 'RED'
        GREEN = 'GREEN'
        ORANGE = 'ORANGE'

    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    NULL = ''
    GENDER_CHOICES = [(MALE,"Male"), (FEMALE,"Female"), (OTHER,"Other"), (NULL, "Null")]

    lab_test = models.ForeignKey(LabTest, on_delete=models.CASCADE, related_name='tests_parameter_thresholds')
    test_parameter = models.ForeignKey(TestParameter, on_delete=models.CASCADE, related_name='parameter_thresholds', blank=False, null=True)
    color = models.CharField(max_length=50, null=True, default=None, blank=False, choices=Colour.as_choices())
    details = models.TextField(blank=True, null=True)
    what_to_do = models.TextField(blank=True, null=True)
    min_value = models.FloatField(null=True, default=0)
    max_value = models.FloatField(null=True, default=0)
    min_age = models.PositiveIntegerField(null=True, default=0)
    max_age = models.PositiveIntegerField(null=True, default=0)
    gender = models.CharField(choices=GENDER_CHOICES, max_length=50, default=None, null=True, blank=True)


    class Meta:
        db_table = 'lab_test_thresholds'


class LabTestCategoryUrls(TimeStampedModel):
    url = models.SlugField(blank=False, null=True, max_length=2000, db_index=True, unique=True)
    title = models.CharField(max_length=2000, default='')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    radius = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = 'lab_test_category_urls'

    def save(self, *args, **kwargs):
        self.url = self.url.lower()
        if not self.url.endswith('tpcp'):
            self.url = self.url + '-tpcp'

        super(LabTestCategoryUrls, self).save(*args, **kwargs)


class LabTestCategoryLandingURLS(TimeStampedModel):
    url = models.ForeignKey(LabTestCategoryUrls, related_name="lab_category_url", on_delete=models.CASCADE)
    test = models.ForeignKey(LabTestCategory, related_name="compare_lab", on_delete=models.CASCADE)
    priority = models.IntegerField(default=0)

    class Meta:
        db_table = "lab_test_category_landing_urls"


class IPDMedicinePageLead(auth_model.TimeStampedModel):
    name = models.CharField(max_length=500)
    phone_number = models.BigIntegerField(validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    matrix_city = models.ForeignKey(MatrixMappedCity, on_delete=models.SET_NULL, null=True)
    matrix_lead_id = models.IntegerField(null=True)
    lead_source = models.CharField(null=True, max_length=1000)

    class Meta:
        db_table = "ipd_medicine_lead"

    def __str__(self):
        return self.name

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):

        if not self.id:
            super().save(force_insert, force_update, using, update_fields)

        if not self.matrix_lead_id:
            create_or_update_lead_on_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}, ), countdown=5)


class LabTestPrecsriptions(auth_model.TimeStampedModel):
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE, null=True, blank=True)
    primary_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    file = GenericRelation(GenericPrescriptionFile, related_query_name="labtest_prescription_file", null=True, blank=True)

    class Meta:
        db_table = 'lab_test_prescriptions'


class LabAppointmentFeedback(auth_model.TimeStampedModel):
    appointment = models.ForeignKey(LabAppointment, on_delete=models.DO_NOTHING, null=True)
    ratings = models.PositiveIntegerField(max_length=10)
    comment = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'lab_appointment_feedback'

