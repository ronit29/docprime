from decimal import Decimal

from django.contrib.gis.db.models.functions import Distance
from django.contrib.gis.geos import GEOSGeometry
from django.db.models import Window
from django.db.models.functions import RowNumber
from django.db.models.expressions import RawSQL
from copy import deepcopy
import json
import requests
from PIL.Image import NEAREST, BICUBIC
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.files.storage import default_storage
from PIL import Image, ImageFont, ImageOps
# from bookinganalytics.models import DP_OpdConsultsAndTests

from django.contrib.gis.db import models
from django.db import migrations, transaction, connection
from django.db.models import Count, Sum, When, Case, Q, F, Avg
from django.contrib.postgres.operations import CreateExtension
from django.contrib.staticfiles.templatetags.staticfiles import static
from django.contrib.postgres.fields import JSONField, ArrayField
from django.core.validators import MaxValueValidator, MinValueValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.core.exceptions import NON_FIELD_ERRORS
from django.template.loader import render_to_string
from rest_framework import status
from rest_framework.exceptions import ValidationError as RestFrameworkValidationError
from django.core.files.storage import get_storage_class
from django.conf import settings
from datetime import timedelta
from dateutil import tz
from django.utils import timezone
from ondoc.authentication import models as auth_model
from ondoc.authentication.models import SPOCDetails, RefundMixin, MerchantTdsDeduction
from ondoc.bookinganalytics.models import DP_OpdConsultsAndTests
from ondoc.location import models as location_models
from ondoc.account.models import Order, ConsumerAccount, ConsumerTransaction, PgTransaction, ConsumerRefund, \
    MerchantPayout, UserReferred, MoneyPool, Invoice
from ondoc.location.models import EntityUrls, UrlsModel
from ondoc.notification.models import NotificationAction, EmailNotification
from ondoc.payout.models import Outstanding
from ondoc.coupon.models import Coupon
from ondoc.doctor.tasks import doc_app_auto_cancel
# from ondoc.account import models as account_model
from ondoc.insurance import models as insurance_model
from ondoc.payout import models as payout_model
from ondoc.notification import models as notification_models
from ondoc.notification import tasks as notification_tasks
from django.contrib.contenttypes.fields import GenericRelation
from ondoc.api.v1.utils import get_start_end_datetime, custom_form_datetime, CouponsMixin, aware_time_zone, \
    form_time_slot, util_absolute_url, html_to_pdf, TimeSlotExtraction, resolve_address
from ondoc.common.models import AppointmentHistory, AppointmentMaskNumber, Service, Remark, MatrixMappedState, \
    MatrixMappedCity, GlobalNonBookable, SyncBookingAnalytics, CompletedBreakupMixin, RefundDetails, TdsDeductionMixin, \
    Documents
from ondoc.common.models import QRCode, MatrixDataMixin
from functools import reduce
from operator import or_
import logging
import re, uuid, os, math, random
import datetime
from django.db.models import Q
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.utils.safestring import mark_safe
from PIL import Image as Img, ImageDraw
from io import BytesIO
import hashlib
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from ondoc.matrix.tasks import push_appointment_to_matrix, push_onboarding_qcstatus_to_matrix, \
    update_onboarding_qcstatus_to_matrix, create_or_update_lead_on_matrix, push_signup_lead_to_matrix, \
    create_ipd_lead_from_opd_appointment
# from ondoc.procedure.models import Procedure
from ondoc.ratings_review import models as ratings_models
from django.utils import timezone
from random import randint
import reversion
from ondoc.doctor import models as doctor_models
from django.db.models import Count
from ondoc.api.v1.utils import RawSql
from safedelete import SOFT_DELETE
#from ondoc.api.v1.doctor import serializers as doctor_serializers
import qrcode
from django.utils.functional import cached_property
from ondoc.crm.constants import constants
from django.utils.text import slugify

logger = logging.getLogger(__name__)


def doctor_mobile_otp_validity():
    return timezone.now() + timezone.timedelta(hours=2)


class Migration(migrations.Migration):

    operations = [
        CreateExtension('postgis')
    ]

class UniqueNameModel(models.Model):

    def validate_unique(self, *args, **kwargs):
        super().validate_unique(*args, **kwargs)

        if self.__class__.objects.filter(name__iexact=self.name.lower()).exists():
            raise ValidationError(
                {
                    NON_FIELD_ERRORS: [
                        self.__class__.__name__ + ' with same name already exists',
                    ],
                }
            )

    class Meta:
        abstract = True


class SearchKey(models.Model):
    search_key = models.CharField(max_length=4000, blank=True, null=True)

    class Meta:
        db_table = 'search_key'
        abstract = True

    def save(self, *args, **kwargs):
        name = self.name
        if name:
            search_key = re.findall(r'[a-z0-9A-Z.]+', name)
            search_key = " ".join(search_key).lower()
            search_key = "".join(search_key.split("."))
            self.search_key = search_key
        if hasattr(self, 'synonyms') and self.synonyms:
            synonyms = self.synonyms.split(",")
            if synonyms:
                synonyms = " ".join(synonyms)
            if synonyms:
                self.search_key = self.search_key + " " + synonyms
        super().save(*args, **kwargs)


class MedicalService(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=500)
    description = models.CharField(max_length=500, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "medical_service"


class Hospital(auth_model.TimeStampedModel, auth_model.CreatedByModel, auth_model.QCModel, SearchKey, auth_model.SoftDelete, auth_model.WelcomeCallingDone, UrlsModel):
    PRIVATE = 1
    CLINIC = 2
    HOSPITAL = 3
    NON_NETWORK_HOSPITAL = 1
    NETWORK_HOSPITAL = 2
    NETWORK_CHOICES = [("", "Select"), (NON_NETWORK_HOSPITAL, "Non Network Hospital"), (NETWORK_HOSPITAL, "Network Hospital")]
    HOSPITAL_TYPE_CHOICES = (("", "Select"), (PRIVATE, 'Private'), (CLINIC, "Clinic"), (HOSPITAL, "Hospital"),)
    INCORRECT_CONTACT_DETAILS = 1
    MOU_AGREEMENT_NEEDED = 2
    HOSPITAL_NOT_INTERESTED = 3
    CHARGES_ISSUES = 4
    DUPLICATE = 5
    OTHERS = 9
    PHONE_RINGING_BUT_COULD_NOT_CONNECT = 10
    WELCOME_CALLING = 1
    ESCALATION = 2
    DISABLED_REASONS_CHOICES = (
        ("", "Select"), (INCORRECT_CONTACT_DETAILS, "Incorrect contact details"),
        (MOU_AGREEMENT_NEEDED, "MoU agreement needed"), (HOSPITAL_NOT_INTERESTED, "Hospital not interested for tie-up"),
        (CHARGES_ISSUES, "Issue in discount % / consultation charges"),
        (PHONE_RINGING_BUT_COULD_NOT_CONNECT, "Phone ringing but could not connect"),
        (DUPLICATE, "Duplicate"), (OTHERS, "Others (please specify)"))
    DISABLED_AFTER_CHOICES = (("", "Select"), (WELCOME_CALLING, "Welcome Calling"), (ESCALATION, "Escalation"))
    AGENT = 1
    PROVIDER = 2
    SOURCE_TYPE_CHOICES = ((AGENT, "Agent"), (PROVIDER, "Provider"))
    name = models.CharField(max_length=200)
    location = models.PointField(geography=True, srid=4326, blank=True, null=True)
    location_error = models.PositiveIntegerField(blank=True, null=True)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1800)])
    parking = models.PositiveSmallIntegerField(blank=True, null=True,
                                               choices=[("", "Select"), (1, "Easy"), (2, "Difficult")])
    registration_number = models.CharField(max_length=500, blank=True)
    building = models.CharField(max_length=1000, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100, blank=True)
    matrix_state = models.ForeignKey(MatrixMappedState, null=True, blank=False, on_delete=models.DO_NOTHING, related_name='hospitals_in_state', verbose_name='State')
    matrix_city = models.ForeignKey(MatrixMappedCity, null=True, blank=False, on_delete=models.DO_NOTHING, related_name='hospitals_in_city', verbose_name='City')
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    hospital_type = models.PositiveSmallIntegerField(blank=True, null=True, choices=HOSPITAL_TYPE_CHOICES)
    network_type = models.PositiveSmallIntegerField(blank=True, null=True,
                                                    choices=NETWORK_CHOICES)
    network = models.ForeignKey('HospitalNetwork', null=True, blank=True, on_delete=models.SET_NULL, related_name='assoc_hospitals')
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)
    is_appointment_manager = models.BooleanField(verbose_name='Enabled for Managing Appointments', default=False)
    is_live = models.BooleanField(verbose_name='Is Live', default=False)
    live_at = models.DateTimeField(null=True, blank=True)
    assigned_to = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_hospital')
    billing_merchant = GenericRelation(auth_model.BillingAccount)
    entity = GenericRelation(location_models.EntityLocationRelationship)
    spoc_details = GenericRelation(auth_model.SPOCDetails, related_query_name='hospital_spocs')
    enabled = models.BooleanField(verbose_name='Is Enabled', default=True, blank=True)
    source = models.CharField(max_length=20, blank=True)
    batch = models.CharField(max_length=20, blank=True)
    enabled_for_online_booking = models.BooleanField(verbose_name='enabled_for_online_booking?', default=True)
    merchant = GenericRelation(auth_model.AssociatedMerchant)
    merchant_payout = GenericRelation(MerchantPayout)
    # welcome_calling_done = models.BooleanField(default=False)
    # welcome_calling_done_at = models.DateTimeField(null=True, blank=True)
    physical_agreement_signed = models.BooleanField(default=False)
    physical_agreement_signed_at = models.DateTimeField(null=True, blank=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_after = models.PositiveIntegerField(null=True, blank=True, choices=DISABLED_AFTER_CHOICES)
    disable_reason = models.PositiveIntegerField(null=True, blank=True, choices=DISABLED_REASONS_CHOICES)
    disable_comments = models.CharField(max_length=500, blank=True)
    disabled_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="disabled_hospitals", null=True, editable=False,
                                    on_delete=models.SET_NULL)
    is_mask_number_required = models.BooleanField(default=True)
    source_type = models.IntegerField(choices=SOURCE_TYPE_CHOICES, null=True, editable=False)
    service = models.ManyToManyField(Service, through='HospitalServiceMapping', through_fields=('hospital', 'service'),
                                     related_name='of_hospitals')
    health_insurance_providers = models.ManyToManyField('HealthInsuranceProvider',
                                                        through='HealthInsuranceProviderHospitalMapping',
                                                        through_fields=('hospital', 'provider'),
                                                        related_name='available_in_hospital')
    open_for_communication = models.BooleanField(default=True)
    bed_count = models.PositiveIntegerField(null=True, blank=True, default=None)
    avg_rating = models.DecimalField(max_digits=5, decimal_places=2, null=True, editable=False)

    remark = GenericRelation(Remark)
    matrix_lead_id = models.BigIntegerField(blank=True, null=True, unique=True)
    is_listed_on_docprime = models.NullBooleanField(null=True, blank=True)
    about = models.TextField(blank=True, null=True, default="")
    # use_new_about = models.BooleanField(default=False)
    new_about = models.TextField(blank=True, null=True, default=None)
    opd_timings = models.CharField(max_length=150, blank=True, null=True, default="")
    always_open = models.BooleanField(verbose_name='Is hospital open 24X7', default=False)
    # ratings = GenericRelation(ratings_models.RatingsReview, related_query_name='hospital_ratings')
    city_search_key = models.CharField(db_index=True, editable=False, max_length=100, default="", null=True, blank=True)
    enabled_for_cod = models.BooleanField(default=False)
    enabled_for_prepaid = models.BooleanField(default=True)
    is_location_verified = models.BooleanField(verbose_name='Location Verified', default=False)
    auto_ivr_enabled = models.BooleanField(default=True)
    priority_score = models.IntegerField(default=0, null=False, blank=False)
    search_distance = models.FloatField(default=15000)
    google_avg_rating = models.DecimalField(max_digits=5, decimal_places=2, null=True, editable=False)
    # provider_encrypt = models.NullBooleanField(null=True, blank=True)
    # provider_encrypted_by = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='encrypted_hospitals')
    # encryption_hint = models.CharField(max_length=128, null=True, blank=True)
    # encrypted_hospital_id = models.CharField(max_length=128, null=True, blank=True)
    is_ipd_hospital = models.BooleanField(default=False)
    is_big_hospital = models.BooleanField(default=False)
    has_proper_hospital_page = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "hospital"

    # def update_search_city(self):
    #     search_city = None
    #     if self.city and not self.city_search_key:
    #         search_city = re.findall(r'[a-zA-Z ]+', self.city)
    #         search_city = " ".join(search_city).lower()
    #         self.city_search_key = search_city
    #         return self.city
    #     return None
    @staticmethod
    def get_top_hospitals_data(request, lat=28.450367, long=77.071848):
        from ondoc.api.v1.doctor.serializers import TopHospitalForIpdProcedureSerializer
        result = []
        queryset = CommonHospital.objects.all().values_list('hospital', 'network')
        top_hospital_ids = list(set([x[0] for x in queryset if x[0] is not None]))
        top_network_ids = list(set([x[1] for x in queryset if x[1] is not None]))
        point_string = 'POINT(' + str(long) + ' ' + str(lat) + ')'
        pnt = GEOSGeometry(point_string, srid=4326)
        temp_hosp_queryset = Hospital.objects.filter(is_live=True)

        # if not request.user.is_anonymous and request.user.active_insurance:
        #     for id in top_hospital_ids:
        #         hosp_obj = Hospital.objects.filter(pk=id).first()
        #         if hosp_obj:
        #             if not hosp_obj.is_hospital_doctor_insurance_enabled():
        #                 top_hospital_ids.remove(id)

        if top_network_ids:
            network_hospital_queryset = temp_hosp_queryset.filter(network__in=top_network_ids)
            network_hospitals = network_hospital_queryset.annotate(
                distance=Distance('location', pnt)).annotate(rank=Window(expression=RowNumber(), order_by=F('distance').asc(),
                            partition_by=[RawSQL('Coalesce(network_id, random())', [])])
            )
            for x in network_hospitals:
                if x.rank == 1:
                    top_hospital_ids.append(x.id)
        hosp_queryset = Hospital.objects.prefetch_related('hospitalcertification_set',
                                                          'hospital_documents',
                                                          'hosp_availability',
                                                          'health_insurance_providers',
                                                          'network__hospital_network_documents',
                                                          'hospitalspeciality_set').filter(
            id__in=top_hospital_ids).annotate(
            distance=Distance('location', pnt)).order_by('distance')
        temp_hospital_ids = hosp_queryset.values_list('id', flat=True)
        hosp_entity_dict, hosp_locality_entity_dict = Hospital.get_hosp_and_locality_dict(temp_hospital_ids,
                                                                                          EntityUrls.SitemapIdentifier.HOSPITALS_LOCALITY_CITY)

        result = TopHospitalForIpdProcedureSerializer(hosp_queryset, many=True, context={'request': request,
                                                                                         'hosp_entity_dict': hosp_entity_dict,
                                                                                         'hosp_locality_entity_dict': hosp_locality_entity_dict}).data
        return result


    @classmethod
    def update_hosp_google_avg_rating(cls):
        update_hosp_google_ratings = RawSql('''update hospital h set google_avg_rating = (select (reviews->>'user_avg_rating')::float from hospital_place_details 
                                         where hospital_id=h.id limit 1)''', [] ).execute()

    def get_active_opd_appointments(self, user=None, user_insurance=None, appointment_date=None):

        appointments = OpdAppointment.objects.filter(hospital_id=self.id)\
                           .exclude(status__in=[OpdAppointment.CANCELLED])
        if user and user.is_authenticated:
            appointments = appointments.filter(user=user)
        if user_insurance:
            appointments = appointments.filter(insurance=user_insurance)
        if appointment_date and appointments:
            appointments = appointments.filter(time_slot_start__date=appointment_date)

        return appointments

    # def is_appointment_exist_for_date(self, insurance, appointment_date):
    #     active_appointments = self.get_active_opd_appointments(None, insurance)
    #     if not active_appointments:
    #         return False
    #     for appointment in active_appointments:
    #         if appointment.time_slot_start.date() == appointment_date.date():
    #             return True
    #     return False


    @classmethod
    def get_hosp_and_locality_dict(cls, temp_hospital_ids, required_identifier):
        if not temp_hospital_ids:
            return {}, {}
        from ondoc.location.models import EntityUrls
        hosp_entity_qs = list(EntityUrls.objects.filter(is_valid=True,
                                                        sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE,
                                                        entity_id__in=temp_hospital_ids))
        locality_city_dict = {(x.sublocality_value.lower(), x.locality_value.lower()): None for x in hosp_entity_qs if
                              x.sublocality_value and x.locality_value}
        hosp_locality_entity_qs = []
        if locality_city_dict:
            hosp_locality_entity_qs = list(EntityUrls.objects.filter(is_valid=True,
                                                                     sitemap_identifier=required_identifier,
                                                                     sublocality_value__iregex=r'(' + '|'.join(
                                                                         [x[0] for x in
                                                                          locality_city_dict.keys()]) + ')',
                                                                     locality_value__iregex=r'(' + '|'.join(
                                                                         [x[1] for x in
                                                                          locality_city_dict.keys()]) + ')'))
        for x in hosp_locality_entity_qs:
            if x.sublocality_value and x.locality_value:
                locality_city_dict[(x.sublocality_value.lower(), x.locality_value.lower())] = x.url
        hosp_entity_dict = {x.entity_id: x.url for x in hosp_entity_qs}
        hosp_locality_entity_dict = {
            x.entity_id: locality_city_dict.get((x.sublocality_value.lower(), x.locality_value.lower()), None) for x in
            hosp_entity_qs if x.sublocality_value and x.locality_value}
        return hosp_entity_dict, hosp_locality_entity_dict

    @classmethod
    def update_hospital_seo_urls(cls):

        from ondoc.location.management.commands import map_hospital_geocoding_results, map_entity_address, \
            calculate_centroid, map_hosp_entity_location_relations, hospital_urls
        # map hospital geocoding results
        #map_hospital_geocoding_results.map_hospital_geocoding_results()

        # map entity address
        #map_entity_address.map_entity_address()

        # calculate centroid
        #calculate_centroid.calculate_centroid()

        # map hospital entity location relations
        #map_hosp_entity_location_relations.map_hosp_entity_location_relations()

        # update search and profile urls
        hospital_urls.hospital_urls()

    def is_enabled_for_cod(self):
        if self.enabled_for_cod:
            return True
        else:
            return False

    @classmethod
    def update_city_search(cls):
        query = '''  update hospital set city_search_key = alternative_value
        from 
        (select * from 
        (select h.id,lower(ea.alternative_value) alternative_value,
        row_number() OVER( PARTITION BY h.id ORDER BY  ea.order desc nulls last) rnk from
                hospital h inner join 
                    entity_location_relations elr on h.id = elr.object_id and elr.content_type_id=28
                    inner join entity_address ea on elr.location_id=ea.id  
                    and ea.use_in_url=True and ea.type='LOCALITY' 
        )x where rnk =1 
        )y where hospital.id = y.id'''
        update_alternative_value = RawSql(query, []).execute()

        query1 = '''update hospital set city_search_key = 
                    case when lower(city) in ('bengaluru','bengalooru') then 'bangalore'
                    when lower(city) in ('gurugram','gurugram rural') then 'gurgaon'
                    else lower(city) end
                    where city_search_key is null
                    or city_search_key='' '''
        update_city = RawSql(query1, []).execute()


    def open_for_communications(self):
        if (self.network and self.network.open_for_communication) or (not self.network and self.open_for_communication):
            return True

        return False

    def is_auto_ivr_enabled(self):
        if (self.network and self.network.auto_ivr_enabled) or (not self.network and self.auto_ivr_enabled):
            return True

        return False

    def get_thumbnail(self):
        return None
        # return static("hospital_images/hospital_default.png")

    def get_hos_address(self):
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

    @classmethod
    def update_avg_rating(cls):
        from django.db import connection
        cursor = connection.cursor()
        content_type = ContentType.objects.get_for_model(Hospital)
        if content_type:
            cid = content_type.id
            query = """update hospital h set avg_rating=(select avg(ratings) from ratings_review rr left join opd_appointment oa on rr.appointment_id = oa.id where appointment_type = 2 group by hospital_id having oa.hospital_id = h.id)"""
            cursor.execute(query)

    @classmethod
    def update_is_big_hospital(cls):
        big_hospitals = Hospital.objects.filter(is_live=True, hospital_doctors__enabled=True,
                                                hospital_doctors__doctor__is_live=True).values_list('id', flat=True)
        if big_hospitals:
            Hospital.objects.filter(id__in=big_hospitals).update(is_big_hospital=True)

    def ad_str(self, string):
        return str(string).strip().replace(',', '')

    def get_short_address(self):
        address_items = [value for value in
                         [self.locality, self.city] if value]
        return ", ".join(address_items)

    def update_live_status(self):
        if not self.is_live and ( self.data_status == self.QC_APPROVED and self.enabled == True):
            self.is_live = True
            if not self.live_at:
                self.live_at = datetime.datetime.now()
        if self.is_live and (self.data_status != self.QC_APPROVED or self.enabled == False):
            self.is_live = False

    def update_time_stamps(self):
        from ondoc.api.v1.utils import update_physical_agreement_timestamp
        update_physical_agreement_timestamp(self)

        if not self.enabled and not self.disabled_at:
            self.disabled_at = timezone.now()
        elif self.enabled and self.disabled_at:
            self.disabled_at = None

    def create_entity_url(self):
        if not self.is_live:
            return

        entity = EntityUrls.objects.filter(entity_id=self.id, is_valid=True, sitemap_identifier='HOSPITAL_PAGE')
        if not entity:
            url = self.name
            url = slugify(url)
            new_url = url

            exists = EntityUrls.objects.filter(url=new_url + '-hpp', sitemap_identifier='HOSPITAL_PAGE').first()
            if exists:
                if exists.id == self.id:
                    exists.is_valid = True
                    exists.save()
                    self.url = new_url+'-hpp'
                    return
                else:
                    new_url = url + '-' + str(self.id)

            new_url = new_url + '-hpp'
            EntityUrls.objects.create(url=new_url, sitemap_identifier='HOSPITAL_PAGE', entity_type='Hospital', url_type='PAGEURL',
                                      is_valid=True, sequence=0, entity_id=self.id)
            self.url = new_url

    def save(self, *args, **kwargs):
        self.update_time_stamps()
        self.update_live_status()
        # build_url = True
        # if self.is_live and self.id and self.location:
        #     if Hospital.objects.filter(location__distance_lte=(self.location, 0), id=self.id).exists():
        #         build_url = False

        push_to_matrix = False
        update_status_in_matrix = False
        if self.id:
            hospital_obj = Hospital.objects.filter(pk=self.id).first()
            if hospital_obj and self.data_status != hospital_obj.data_status:
                update_status_in_matrix = True
        if not self.matrix_lead_id and (self.is_listed_on_docprime is None or self.is_listed_on_docprime is True):
            push_to_matrix = True

        self.create_entity_url()
        super(Hospital, self).save(*args, **kwargs)
        if self.is_appointment_manager:
            auth_model.GenericAdmin.objects.filter(hospital=self, entity_type=auth_model.GenericAdmin.DOCTOR, permission_type=auth_model.GenericAdmin.APPOINTMENT)\
                .update(is_disabled=True)
        else:
            auth_model.GenericAdmin.objects.filter(hospital=self, entity_type=auth_model.GenericAdmin.DOCTOR, permission_type=auth_model.GenericAdmin.APPOINTMENT)\
                .update(is_disabled=False)
        # if build_url and self.location and self.is_live:
        #     ea = location_models.EntityLocationRelationship.create(latitude=self.location.y, longitude=self.location.x, content_object=self)
        transaction.on_commit(lambda: self.app_commit_tasks(push_to_matrix=push_to_matrix,
                                                            update_status_in_matrix=update_status_in_matrix))

    def app_commit_tasks(self, push_to_matrix=False, update_status_in_matrix=False):
        if push_to_matrix:
            create_or_update_lead_on_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                         ,), countdown=5)

        if update_status_in_matrix:
            update_onboarding_qcstatus_to_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                              ,), countdown=5)

    def get_spocs_for_communication(self):
        result = []
        result.extend(list(self.spoc_details.filter(contact_type__in=[SPOCDetails.SPOC, SPOCDetails.MANAGER])))
        if not result:
            result.extend(list(self.spoc_details.filter(contact_type=SPOCDetails.OWNER)))
        return result

    def has_ipd_doctors(self):
        result = False
        # for doctor_clinic in self.hospital_doctors.filter(enabled=True):
        #     if doctor_clinic.ipd_procedure_clinic_mappings.filter(enabled=True).exists():
        #         result = True
        #         break
        result = self.is_ipd_hospital
        return result

    def get_specialization_insured_appointments(self, doctor, insurance):
        days = insurance.specialization_days_limit
        n_days_back_datetime = timezone.now() - datetime.timedelta(days=days)

        limit_specialization_ids = json.loads(settings.INSURANCE_SPECIALIZATION_WITH_DAYS_LIMIT)
        limit_specialization_ids_set = set(limit_specialization_ids)
        doctor_specialization_ids = set([x.specialization_id for x in doctor.doctorpracticespecializations.all()])

        if not limit_specialization_ids_set.intersection(doctor_specialization_ids):
            return []

        doctor_with_specialization = DoctorPracticeSpecialization.objects. \
            filter(specialization_id__in=limit_specialization_ids).values_list('doctor_id', flat=True)

        appointments = self.hospital_appointments.filter(insurance=insurance,
                                                         user=insurance.user,
                                                         time_slot_start__gte=n_days_back_datetime,
                                                         doctor_id__in=doctor_with_specialization).\
            exclude(status__in=[OpdAppointment.CANCELLED]).order_by('-time_slot_start')

        return appointments

    def get_blocked_specialization_appointments_slots(self, doctor, insurance):
        blockeds_timeslots = []
        appointments = self.get_specialization_insured_appointments(doctor, insurance)

        if not appointments:
            return blockeds_timeslots

        days = insurance.specialization_days_limit
        for appointment in appointments:
            for n in range(days):
                nth_day_future_timeslot = appointment.time_slot_start.date() + datetime.timedelta(days=n)
                nth_day_past_timeslot = appointment.time_slot_start.date() - datetime.timedelta(days=n)
                blockeds_timeslots.append(str(nth_day_future_timeslot))
                if nth_day_past_timeslot >= timezone.now().date():
                    blockeds_timeslots.append(str(nth_day_past_timeslot))

        return blockeds_timeslots

    def is_hospital_doctor_insurance_enabled(self):
        insured = False
        dc_obj = DoctorClinic.objects.filter(hospital_id=self.id).first()
        if dc_obj:
            doctor = Doctor.objects.filter(pk=dc_obj.doctor_id).first()
            if doctor.is_insurance_enabled:
                insured = True

        return insured


class HospitalPlaceDetails(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='hospital_place_details')
    place_id = models.TextField()
    place_details = JSONField(null=True, blank=True)
    reviews = JSONField(null=True, blank=True)

    class Meta:
        db_table = 'hospital_place_details'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    @classmethod
    def update_hosp_place_with_google_api_details(cls):
        query = RawSql(''' insert into hospital_place_details(place_id, hospital_id, place_details,reviews, created_at,updated_at)
                select (json_array_elements(clinic_place_search::json ->'candidates')->>'place_id') as place_id, hospital_id , clinic_detail::json as place_details,
                json_build_object('user_ratings_total',clinic_detail::json->'result'->'user_ratings_total', 'user_avg_rating',
                clinic_detail::json->'result'->'rating', 'user_reviews', clinic_detail::json->'result'->'reviews' ) as reviews, now(), now() 
                from google_api_details where hospital_id is not null ''', []).execute()

    @classmethod
    def update_place_details(cls):
        hosp_place_id = HospitalPlaceDetails.objects.all()
        for data in hosp_place_id:
            if not data.place_details:
                place_searched_data = None
                params = {'placeid': data.place_id, 'key': settings.REVERSE_GEOCODING_API_KEY}
                place_response = requests.get('https://maps.googleapis.com/maps/api/place/details/json',
                                          params=params)
                if place_response.status_code != status.HTTP_200_OK or not place_response.ok:
                    print('failure  status_code: ' + str(place_response.status_code) + ', reason: ' + str(
                        place_response.reason))
                    continue

                place_searched_data = place_response.json()
                if place_searched_data.get('status') == 'OVER_QUERY_LIMIT':
                    print('OVER_QUERY_LIMIT')
                    continue

                if place_searched_data.get('result'):
                    place_searched_data = place_searched_data.get('result')
                    data.place_details = place_searched_data
                    data.reviews = {'user_avg_rating': place_searched_data.get('rating'), 'user_reviews': place_searched_data.get('reviews'),
                                    'user_ratings_total': place_searched_data.get('user_ratings_total')}
                    data.save()


class HospitalServiceMapping(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE,
                                 related_name='service_mappings')
    service = models.ForeignKey(Service, on_delete=models.CASCADE,
                                related_name='hospital_service_mappings')

    def __str__(self):
        return '{} - {}'.format(self.hospital.name, self.service.name)

    class Meta:
        db_table = "hospital_service_mapping"
        unique_together = (('hospital', 'service'),)


class HospitalAward(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_award"


class HospitalAccreditation(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_accreditation"


class HospitalCertification(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_certification"


class HospitalSpeciality(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.hospital.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_speciality"


# class ClinicalSpeciality(auth_model.TimeStampedModel):
#     name = models.CharField(max_length=1000)

#     def __str__(self):
#         return self.name

#     class Meta:
#         db_table = "clinical_speciality"


# class HospitalClinicalSpeciality(auth_model.TimeStampedModel):
#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
#     speciality = models.ForeignKey(ClinicalSpeciality, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.hospital.name + " (" + self.clinical_speciality.name + ")"

#     class Meta:
#         db_table = "hospital_clinical_speciality"
#         unique_together = (("hospital", "speciality"))


class College(auth_model.TimeStampedModel):
    name = models.CharField(max_length=200, blank=False)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "college"


class Doctor(auth_model.TimeStampedModel, auth_model.QCModel, SearchKey, auth_model.SoftDelete, UrlsModel):
    SOURCE_PRACTO = "pr"
    SOURCE_CRM = 'crm'

    NOT_ONBOARDED = 1
    REQUEST_SENT = 2
    ONBOARDED = 3
    ONBOARDING_STATUS = [(NOT_ONBOARDED, "Not Onboarded"), (REQUEST_SENT, "Onboarding Request Sent"),
                         (ONBOARDED, "Onboarded")]
    GENDER_CHOICES = [("", "Select"), ("m", "Male"), ("f", "Female"), ("o", "Other")]
    DOCTOR_NOT_ASSOCIATED = 1
    DOCTOR_ONLY_FOR_IPD_SERVICES = 2
    DOCTOR_AVAILABLE_ON_CALL = 3
    INCORRECT_CONTACT_DETAILS = 4
    MOU_AGREEMENT_NEEDED = 5
    DOCTOR_NOT_INTERESTED_FOR_TIE_UP = 6
    CHARGES_ISSUES = 7
    DUPLICATE = 8
    OTHERS = 9
    PHONE_RINGING_BUT_COULD_NOT_CONNECT = 10
    DISABLE_REASON_CHOICES = (
        ("", "Select"), (DOCTOR_NOT_ASSOCIATED, "Doctor not associated with the hospital anymore"),
        (DOCTOR_ONLY_FOR_IPD_SERVICES, "Doctor only for IPD services"),
        (DOCTOR_AVAILABLE_ON_CALL, "Doctor available only On-Call"),
        (INCORRECT_CONTACT_DETAILS, "Incorrect contact details"), (MOU_AGREEMENT_NEEDED, "MoU agreement needed"),
        (DOCTOR_NOT_INTERESTED_FOR_TIE_UP, "Doctor not interested for tie-up"),
        (CHARGES_ISSUES, "Issue in discount % / consultation charges"),
        (PHONE_RINGING_BUT_COULD_NOT_CONNECT, "Phone ringing but could not connect"), (DUPLICATE, "Duplicate"),
        (OTHERS, "Others (please specify)"))
    AGENT = 1
    PROVIDER = 2
    SOURCE_TYPE_CHOICES = ((AGENT, "Agent"), (PROVIDER, "Provider"))
    name = models.CharField(max_length=200)
    gender = models.CharField(max_length=2, default=None, blank=True, null=True,
                              choices=GENDER_CHOICES)
    practicing_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])
    raw_about = models.CharField(max_length=2000, blank=True)
    about = models.CharField(max_length=2000, blank=True)
    # primary_mobile = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999),
    #                                                                            MinValueValidator(1000000000)])
    license = models.CharField(max_length=200, blank=True)
    onboarding_status = models.PositiveSmallIntegerField(default=NOT_ONBOARDED, choices=ONBOARDING_STATUS)
    onboarded_at = models.DateTimeField(null=True, blank=True)
    additional_details = models.CharField(max_length=2000, blank=True)
    # email = models.EmailField(max_length=100, blank=True)
    is_email_verified = models.BooleanField(verbose_name='Email Verified', default=False)
    user = models.OneToOneField(settings.AUTH_USER_MODEL, related_name="doctor", on_delete=models.SET_NULL, default=None,
                                blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="created_doctors", null=True, editable=False,
                                   on_delete=models.SET_NULL)

    is_insurance_enabled = models.BooleanField(verbose_name='Enabled for Insurance Customer', default=False)
    is_retail_enabled = models.BooleanField(verbose_name='Enabled for Retail Customer', default=False)
    is_online_consultation_enabled = models.BooleanField(verbose_name='Available for Online Consultation',
                                                         default=False)
    online_consultation_fees = models.PositiveSmallIntegerField(blank=True, null=True)
    is_live = models.BooleanField(verbose_name='Is Live', default=False)
    live_at = models.DateTimeField(null=True, blank=True)
    is_internal = models.BooleanField(verbose_name='Is Staff Doctor', default=False)
    is_test_doctor = models.BooleanField(verbose_name='Is Test Doctor', default=False)
    is_license_verified = models.BooleanField(default=False, blank=True)
    hospitals = models.ManyToManyField(
        Hospital,
        through='DoctorClinic',
        through_fields=('doctor', 'hospital'),
        related_name='assoc_doctors',
    )
    assigned_to = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_doctors')
    matrix_lead_id = models.BigIntegerField(blank=True, null=True, unique=True)
    matrix_reference_id = models.BigIntegerField(blank=True, null=True)
    signature = models.ImageField('Doctor Signature', upload_to='doctor/images', null=True, blank=True)
    billing_merchant = GenericRelation(auth_model.BillingAccount)
    rating = GenericRelation(ratings_models.RatingsReview, related_query_name='doc_ratings')
    enabled = models.BooleanField(verbose_name='Is Enabled', default=True, blank=True)
    source = models.CharField(max_length=20, blank=True)
    batch = models.CharField(max_length=20, blank=True)
    enabled_for_online_booking = models.BooleanField(default=False)
    enabled_for_online_booking_at = models.DateTimeField(null=True, blank=True)
    is_gold = models.BooleanField(verbose_name='Is Gold', default=False)
    merchant = GenericRelation(auth_model.AssociatedMerchant)
    merchant_payout = GenericRelation(MerchantPayout)
    search_score = models.FloatField(default=0, null=True, editable=False)
    disabled_at = models.DateTimeField(null=True, blank=True)
    disabled_after = models.PositiveIntegerField(null=True, blank=True, choices=Hospital.DISABLED_AFTER_CHOICES)
    disable_reason = models.PositiveIntegerField(null=True, blank=True, choices=DISABLE_REASON_CHOICES)
    disable_comments = models.CharField(max_length=500, blank=True)
    disabled_by = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="disabled_doctors", null=True, editable=False,
                                   on_delete=models.SET_NULL)
    source_type = models.IntegerField(choices=SOURCE_TYPE_CHOICES, null=True, editable=False)
    avg_rating = models.DecimalField(max_digits=5, decimal_places=2, null=True, editable=False)
    remark = GenericRelation(Remark)
    rating_data = JSONField(blank=True, null=True)
    qr_code = GenericRelation(QRCode, related_name="qrcode")
    priority_score = models.IntegerField(default=0, null=False, blank=False)

    def __str__(self):
        return '{} ({})'.format(self.name, self.id)

    @classmethod
    def update_doctors_seo_urls(cls):
        from ondoc.location.management.commands import doctor_search_urls_new

        # update search and profile urls
        doctor_search_urls_new.doctor_urls()


    # @property
    @cached_property
    def is_enabled_for_insurance(self):
        return self.is_insurance_enabled

    @classmethod
    def update_insured_doctors(cls):

        delete_query = RawSql(''' delete from insurance_covered_entity where type='doctor' ''', []).execute()

        query =   '''insert into insurance_covered_entity(entity_id,name ,location, type, search_key, data,specialization_search_key, created_at,updated_at)
                 
                 select doc_id as entity_id, doctor_name as name, location ,'doctor' as type,search_key,
                        json_build_object('id',doc_id, 'type','doctor','name', doctor_name,'city', city,'url', entity_url,'hospital_name',hospital_name, 'specializations', specializations),specialization_search_key,  now(), now() from(
                select doc_id ,doctor_name, h.location, doc_search_key as search_key, h.city, h.name as hospital_name , entity_url , specialization_search_key, specializations from 
                (select d.id doc_id, d.name doctor_name,d.search_key as doc_search_key, max(eu.url) as entity_url,
                string_agg(distinct lower(ps.name), ',') specialization_search_key,
                array_agg(distinct ps.name) specializations
                from doctor d 
                 inner join entity_urls eu on eu.entity_id = d.id and sitemap_identifier = 'DOCTOR_PAGE' and eu.is_valid=true
                 inner join doctor_practice_specialization dps on dps.doctor_id = d.id 
                 inner join practice_specialization ps on ps.id = dps.specialization_id and ps.is_insurance_enabled=true
                 inner join doctor_clinic dc on d.id = dc.doctor_id 
                 inner join doctor_clinic_timing dct on dct.doctor_clinic_id = dc.id and dct.mrp<=1500
                 inner join hospital h on h.id = dc.hospital_id
                 where d.is_live=true and  d.enabled_for_online_booking=true and
                 dc.enabled=true and dc.enabled_for_online_booking=true
                 and h.enabled_for_online_booking=true and h.enabled_for_prepaid=true and h.is_live=true
                        and h.location is not null
                  and  d.is_test_doctor=false and d.is_internal=false and d.is_insurance_enabled=true
                group by d.id
                )x inner join doctor_clinic dc on dc.doctor_id=doc_id inner join hospital h on h.id=dc.hospital_id
                 and dc.enabled=true and dc.enabled_for_online_booking=true
                        and h.enabled_for_online_booking=true and h.enabled_for_prepaid=true and h.is_live=true
                        and h.location is not null) y '''

        update_insured_doctors = RawSql(query, []).execute()

    @classmethod
    def get_insurance_details(cls, user):
        from ondoc.insurance.models import InsuranceThreshold
        insurance_threshold_obj = InsuranceThreshold.objects.all().order_by('-opd_amount_limit').first()
        insurance_threshold_amount = insurance_threshold_obj.opd_amount_limit if insurance_threshold_obj else 1500
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
                    resp['insurance_threshold_amount'] = 0 if insurance_threshold.opd_amount_limit is None else \
                        insurance_threshold.lab_amount_limit
                    resp['is_user_insured'] = True

        return resp

    def update_deal_price(self):        
        # will update only this doctor prices and will be called on save    
        query = '''update doctor_clinic_timing set deal_price = least(
                    greatest(floor(
                    case when fees <=0 then mrp*.4 
                    when mrp<=2000 then
                    case when (least(fees*1.5, .8*mrp) - fees) >100 then least(fees*1.5, .8*mrp) 
                    else least(fees+100, mrp) end
                    else 
                    case when (least(fees*1.5, fees+.5*(mrp-fees)) - fees )>100
                    then least(fees*1.5, fees+.5*(mrp-fees))
                    else
                    least(fees+100, mrp) end 	
                    end  /5)*5, fees), mrp) where doctor_clinic_id in (
                    select id from doctor_clinic where doctor_id= %s) '''

        update_doctor_deal_price = RawSql(query, [self.pk]).execute()

    @classmethod
    def update_all_deal_price(cls):
        # will update all doctors prices
        query = '''update doctor_clinic_timing set deal_price = least(
                    greatest(floor(
                    case when fees <=0 then mrp*.4 
                    when mrp<=2000 then
                    case when (least(fees*1.5, .8*mrp) - fees) >100 then least(fees*1.5, .8*mrp) 
                    else least(fees+100, mrp) end
                    else 
                    case when (least(fees*1.5, fees+.5*(mrp-fees)) - fees )>100
                    then least(fees*1.5, fees+.5*(mrp-fees))
                    else
                    least(fees+100, mrp) end 	
                    end  /5)*5, fees), mrp) '''

        update_all_doctor_deal_price = RawSql(query, []).execute()

    def get_display_name(self):
        return "Dr. {}".format(self.name.title()) if self.name else None

    def experience_years(self):
        if not self.practicing_since:
            return None
        current_year = timezone.now().year
        return int(current_year - self.practicing_since)

    def experiences(self):
        return self.experiences.all()

    def hospital_count(self):
        return self.availability.all().values("hospital").distinct().count()

    def get_hospitals(self):
        return self.availability.all()

    def get_thumbnail(self):
        for image in self.images.all():
            if image.cropped_image:
                return image.get_thumbnail_path(image.cropped_image.url,'80x80')
        # if self.images.all():
        #     return self.images.all()[0].name.url
        return None

    def get_ratings(self):
         return self.rating.all()

    def get_avg_rating(self):
        # return self.rating.filter(is_live=True).aggregate(avg_rating=Avg('ratings'))
        if self.rating_data:
            return self.rating_data.get('avg_rating')
        return None

    def get_rating_count(self):
        count = 0
        if self.rating_data and self.rating_data.get('rating_count'):
            count = self.rating_data.get('rating_count')
        return count

    def update_live_status(self):

        if self.source == self.SOURCE_PRACTO or self.source == self.SOURCE_CRM:
            if not self.is_live and self.enabled == True:
                self.is_live = True
                if not self.live_at:
                    self.live_at = timezone.now()
            if self.is_live and self.enabled == False:
                self.is_live = False
        else:
            if not self.is_live and (self.onboarding_status == self.ONBOARDED and self.data_status == self.QC_APPROVED and self.enabled == True):
                # dochospitals = []
                # for hosp in self.hospitals.all():
                #     dochospitals.append(hosp.id)
                # queryset = auth_model.GenericAdmin.objects.filter(Q(is_disabled=False, user__isnull=False, permission_type = auth_model.GenericAdmin.APPOINTMENT),
                #                                (Q(doctor__isnull=False, doctor=self) |
                #                                 Q(doctor__isnull=True, hospital__id__in=dochospitals)))

                self.is_live = True
                if not self.live_at:
                    self.live_at = timezone.now()
            if self.is_live and (self.onboarding_status != self.ONBOARDED or self.data_status != self.QC_APPROVED or self.enabled == False):
                self.is_live = False

        if self.onboarding_status == self.ONBOARDED and self.data_status == self.QC_APPROVED and self.enabled_for_online_booking:
            if not self.enabled_for_online_booking_at:
                self.enabled_for_online_booking_at = timezone.now()

        if not self.onboarding_status == self.ONBOARDED:
            self.enabled_for_online_booking = False

    def update_time_stamps(self):
        if not self.enabled and not self.disabled_at:
            self.disabled_at = timezone.now()
        elif self.enabled and self.disabled_at:
            self.disabled_at = None

    def display_rating_on_list(self):
        if self.rating_data and ((self.rating_data.get('rating_count') and self.rating_data['rating_count'] > 5) or \
                                 (self.rating_data.get('avg_rating') and self.rating_data['avg_rating'] > 4)):
            return True
        return False

    def create_entity_url(self):
        if not self.is_live:
            return

        entity = EntityUrls.objects.filter(entity_id=self.id, is_valid=True, sitemap_identifier='DOCTOR_PAGE')
        if not entity:
            doctor = Doctor.objects.prefetch_related('doctorpracticespecializations', 'doctorpracticespecializations__specialization').filter(id=self.id)[0]
            practice_specializations = doctor.doctorpracticespecializations.all()
            specializations = set()
            for sp in practice_specializations:
                specializations.add(sp.specialization.name)

            if specializations:
                url = "dr-%s-%s" % (self.name, "-".join(specializations))
            else:
                url = "dr-%s" % (self.name)
            url = slugify(url)
            new_url = url
            exists = EntityUrls.objects.filter(url=new_url+'-dpp', sitemap_identifier='DOCTOR_PAGE').first()
            if exists:
                if exists.id == self.id:
                    exists.is_valid=True
                    exists.save()
                    self.url = new_url + '-dpp'
                    return
                else:
                    new_url = url+'-'+str(self.id)
            
            EntityUrls.objects.create(url=new_url+'-dpp', sitemap_identifier='DOCTOR_PAGE', entity_type='Doctor', url_type='PAGEURL',
                                  is_valid=True, sequence=0, entity_id=self.id)
            self.url = new_url + '-dpp'

    def save(self, *args, **kwargs):
        self.update_time_stamps()
        self.update_live_status()
        # On every update of onboarding status or Qcstatus push to matrix
        push_to_matrix = False
        update_status_in_matrix = False
        if self.id:
            doctor_obj = Doctor.objects.filter(pk=self.id).first()
            if doctor_obj and self.data_status != doctor_obj.data_status:
                update_status_in_matrix = True
            elif not doctor_obj:
                push_to_matrix = True
        else:
            push_to_matrix = True

        self.create_entity_url()
        super(Doctor, self).save(*args, **kwargs)

        transaction.on_commit(lambda: self.app_commit_tasks(push_to_matrix=push_to_matrix,
                                                            update_status_in_matrix=update_status_in_matrix))

    def app_commit_tasks(self, push_to_matrix=False, update_status_in_matrix=False):
        self.update_deal_price()
        if push_to_matrix:
            # push_onboarding_qcstatus_to_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
            #                                                 ,), countdown=5)
            create_or_update_lead_on_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                         ,), countdown=5)

        if update_status_in_matrix:
            update_onboarding_qcstatus_to_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                              ,), countdown=5)

    @classmethod
    def update_avg_rating(cls):
        from django.db import connection
        cursor = connection.cursor()
        content_type = ContentType.objects.get_for_model(Doctor)
        if content_type:
            cid = content_type.id

            query = '''update doctor d set rating_data=
                       (
                       select json_build_object('avg_rating', x.avg_rating,'rating_count', x.rating_count) from
                       (select object_id as doctor_id,round(avg(ratings),1) avg_rating, count(*) rating_count from 
                       ratings_review where content_type_id={} AND is_live='true' group by object_id
                       )x where x.doctor_id = d.id				  
                       ) where id in (select object_id from ratings_review where content_type_id={})
                     '''.format(cid, cid)
            cursor.execute(query)

    def enabled_for_cod(self):  # Not to be used
        return False

    def generate_qr_code(self):

        doctor_url = settings.BASE_URL + "/opd/doctor/{}".format(self.id)

        img = qrcode.make(doctor_url)
        # md5_hash = hashlib.md5(img.tobytes()).hexdigest()

        tempfile_io = BytesIO()
        img.save(tempfile_io, format='JPEG')

        filename = "qrcode_{}_{}.jpeg".format('id:' + str(self.id),
                                              random.randint(1111111111, 9999999999))
        # image_file1 = InMemoryUploadedFile(tempfile_io, None, name=filename, content_type='image/jpeg', size=10000,
        #                                    charset=None)

        image_file1 = InMemoryUploadedFile(tempfile_io, None, filename, 'image/jpeg', tempfile_io.tell(), None)

        QRCode_object = QRCode(name=image_file1, content_type=ContentType.objects.get_for_model(Doctor),
                               object_id=self.id, data={"url": doctor_url})
        QRCode_object.save()
        return QRCode_object

    def generate_sticker(self):

        # thumbnail = None
        # for image in self.images.all():
        #     if image.cropped_image:
        #         thumbnail = image.cropped_image

        #         break
        # if not thumbnail:
        #     return

        thumbnail = self.images.exclude(cropped_image__isnull=True).exclude(cropped_image__exact='').first()
        if not thumbnail:
            return
        qrcode = self.qr_code.all().first()
        # for qrcode in self.qr_code.all():
        #     if qrcode:
        #         qrcode = default_storage.path(qrcode.name)
        #         break

        #template_url = staticfiles_storage.path('web/images/qr_image.png')
        template = Image.open(staticfiles_storage.open('web/images/qr_image.png'))
        print(thumbnail)


        #thumbnail = default_storage.path(thumbnail)
        #print(thumbnail)
        doctor_image = Image.open(thumbnail.cropped_image)
        qrcode_image = Image.open(qrcode.name)

        # im = Image.open('avatar.jpg')
        # im = im.resize((120, 120));
        # bigsize = (im.size[0] * 3, im.size[1] * 3)
        # mask = Image.new('L', bigsize, 0)
        # draw = ImageDraw.Draw(mask)
        # draw.ellipse((0, 0) + bigsize, fill=255)
        # mask = mask.resize(im.size, Image.ANTIALIAS)
        # im.putalpha(mask)
        #
        # output = ImageOps.fit(im, mask.size, centering=(0.5, 0.5))
        # output.putalpha(mask)
        # output.save('output.png')
        #
        # background = Image.open('back.jpg')
        # background.paste(im, (150, 10), im)
        # background.save('overlap.png')

        doctor_image = doctor_image.resize((220, 220))
        bigsize = (doctor_image.size[0] * 200, doctor_image.size[1] * 200)

        mask = Image.new('L', bigsize, 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((100,100)+bigsize, fill=255)
        mask = mask.resize(doctor_image.size, Image.ANTIALIAS)
        doctor_image.putalpha(mask)
        output = ImageOps.fit(doctor_image, mask.size, centering=(1, 1))
        output.putalpha(mask)
        # output.save('output.png')
        canvas = Image.new('RGB', (892, 1620))
        canvas.paste(template, (0,0))
        # doctor_image = doctor_image.resize((200, 200), Image.ANTIALIAS)
        canvas.paste(doctor_image, (315, 300), doctor_image)
        #canvas.save('overlap.png')
        qrcode_image = qrcode_image.resize((530, 530), Image.ANTIALIAS)
        canvas.paste(qrcode_image, (165, 760))

        blank_image = Image.new('RGBA', (1000, 1000), 'white') # this new image is created to write text and paste on canvas
        img_draw = ImageDraw.Draw(canvas)
        #font_url = staticfiles_storage.path('web/fonts/ProspectusPro-Desktop-v1-002/ProspectusSBld.otf')

        font = ImageFont.truetype(staticfiles_storage.open('web/fonts/ProspectusPro-Desktop-v1-002/ProspectusSBld.otf'), 40)

        w, h = img_draw.textsize(self.name, font=font)

        img_draw.text(((892-w)/2,530), self.name, fill="black", font=font)
        #img_draw.text((350,530), self.name, fill="black", font=font)
        #im.save("hello.png", "PNG")



        #img_draw.text((350, 530), self.name, fill='black', font=font)
        # md5_hash = hashlib.md5(canvas.tobytes()).hexdigest()

        tempfile_io = BytesIO()
        canvas.save(tempfile_io, format='JPEG')
        filename = "doctor_sticker_{}_{}.jpeg".format(str(self.id),
                                              random.randint(1111111111, 9999999999))

        image_file1 = InMemoryUploadedFile(tempfile_io, None, filename, 'image/jpeg', tempfile_io.tell(), None)

        sticker = DoctorSticker(name=image_file1, doctor=self)
        sticker.save()
        return sticker

    def get_leaves(self):
        leave_range = list()
        doctor_leaves = self.leaves.filter(deleted_at__isnull=True)
        for dl in doctor_leaves:
            start_datetime = datetime.datetime.combine(dl.start_date, dl.start_time)
            end_datetime = datetime.datetime.combine(dl.end_date, dl.end_time)
            leave_range.append({'start_datetime': start_datetime, 'end_datetime': end_datetime})
        return leave_range


    def is_doctor_specialization_insured(self):
        dps = self.doctorpracticespecializations.all()
        if len(dps) == 0:
            return False

        for d in dps:
            if not d.specialization.is_insurance_enabled:
                return False

        # doctor_specializations = DoctorPracticeSpecialization.objects.filter(doctor=self).values_list('specialization_id', flat=True)
        # if not doctor_specializations:
        #     return False
        # for specialization in doctor_specializations:
        #     practice_specialization = PracticeSpecialization.objects.filter(id=specialization).first()
        #     if not practice_specialization:
        #         return False
        #     if not practice_specialization.is_insurance_enabled:
        #         return False
        return True

    class Meta:
        db_table = "doctor"


class DoctorSticker(auth_model.TimeStampedModel):
    image_base_path = 'doctor/stickers'
    doctor = models.ForeignKey(Doctor, related_name="stickers", on_delete=models.CASCADE)
    name = models.ImageField('Original Image Name',upload_to=image_base_path,blank=True, null=True)

    class Meta:
        db_table = "doctor_sticker"


class AboutDoctor(Doctor):

    class Meta:
        proxy = True
        default_permissions = []


class Specialization(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=200)
    human_readable_name = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "specialization"


class Qualification(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "qualification"


class Symptoms(auth_model.TimeStampedModel, auth_model.CreatedByModel, UniqueNameModel):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "symptoms"


class DoctorQualification(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="qualifications", on_delete=models.CASCADE)
    qualification = models.ForeignKey(Qualification, on_delete=models.CASCADE)
    specialization = models.ForeignKey(Specialization, on_delete=models.CASCADE, blank=True, null=True)
    college = models.ForeignKey(College, on_delete=models.CASCADE, blank=True, null=True);
    passing_year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])

    # def __str__(self):
    #     return ''
    #     if self.specialization_id:
    #         return self.qualification.name + " (" + self.specialization.name + ")"
    #     return self.qualification.name

    class Meta:
        db_table = "doctor_qualification"
        unique_together = (("doctor", "qualification", "specialization", "college"),)
        ordering = ('created_at', )


class GeneralSpecialization(auth_model.TimeStampedModel, UniqueNameModel, SearchKey):
    name = models.CharField(max_length=200)
    synonyms = models.CharField(max_length=4000, blank=True, null=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "general_specialization"


class DoctorSpecialization(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="doctorspecializations", on_delete=models.CASCADE)
    specialization = models.ForeignKey(GeneralSpecialization, on_delete=models.CASCADE, blank=False, null=False)

    # def __str__(self):
    #    return self.doctor.name + " (" + self.specialization.name + ")"

    class Meta:
        db_table = "doctor_specialization"
        unique_together = ("doctor", "specialization")


class DoctorClinic(auth_model.TimeStampedModel, auth_model.WelcomeCallingDone):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE, related_name='doctor_clinics')
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='hospital_doctors')
    followup_duration = models.PositiveSmallIntegerField(blank=True, null=True)
    followup_charges = models.PositiveSmallIntegerField(blank=True, null=True)
    enabled_for_online_booking = models.BooleanField(verbose_name='enabled_for_online_booking?', default=False)
    enabled = models.BooleanField(verbose_name='Enabled', default=True)
    priority = models.PositiveSmallIntegerField(blank=True, null=True, default=0)
    merchant = GenericRelation(auth_model.AssociatedMerchant)
    merchant_payout = GenericRelation(MerchantPayout)
    
    class Meta:
        db_table = "doctor_clinic"
        unique_together = (('doctor', 'hospital', ),)

    # def __str__(self):
    #     return '{}-{}'.format(self.doctor, self.hospital)

    def is_enabled_for_cod(self):
        return self.hospital.is_enabled_for_cod()

    def get_timings(self, blocks=[]):
        from ondoc.api.v2.doctor import serializers as v2_serializers
        from ondoc.api.v1.common import serializers as common_serializers
        clinic_timings= self.availability.order_by("start")
        doctor_leave_serializer = v2_serializers.DoctorLeaveSerializer(
            DoctorLeave.objects.filter(doctor=self.doctor_id, deleted_at__isnull=True), many=True)
        global_leave_serializer = common_serializers.GlobalNonBookableSerializer(
           GlobalNonBookable.objects.filter(deleted_at__isnull=True, booking_type=GlobalNonBookable.DOCTOR), many=True)
        total_leaves = dict()
        total_leaves['global'] = global_leave_serializer.data
        total_leaves['doctor'] = doctor_leave_serializer.data
        timeslots = dict()
        obj = TimeSlotExtraction()

        for data in clinic_timings:
            obj.form_time_slots( data.day, data.start, data.end, data.fees, True,
                                data.deal_price, data.mrp, data.dct_cod_deal_price(), True, on_call=data.type)

        date = datetime.datetime.today().strftime('%Y-%m-%d')
        booking_details = {"type": "doctor"}
        slots = obj.get_timing_slots(date, total_leaves, booking_details)
        if slots:
            for b in blocks:
                slots.pop(b, None)

        upcoming_slots = obj.get_upcoming_slots(time_slots=slots)
        res_data = {"time_slots": slots, "upcoming_slots": upcoming_slots}
        return res_data



    def get_timings_v2(self, total_leaves, blocks=[]):
        clinic_timings = self.availability.order_by("start")
        booking_details = dict()
        booking_details['type'] = 'doctor'
        timeslot_object = TimeSlotExtraction()
        clinic_timings = timeslot_object.format_timing_to_datetime_v2(clinic_timings, total_leaves, booking_details)

        if clinic_timings:
            for b in blocks:
                clinic_timings.pop(b, None)

        upcoming_slots = timeslot_object.get_upcoming_slots(time_slots=clinic_timings)
        timing_response = {"timeslots": clinic_timings, "upcoming_slots": upcoming_slots}
        return timing_response



class DoctorClinicTiming(auth_model.TimeStampedModel):
    DAY_CHOICES = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    SHORT_DAY_CHOICES = [(0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri"), (5, "Sat"), (6, "Sun")]
    doctor_clinic = models.ForeignKey(DoctorClinic, on_delete=models.CASCADE, related_name='availability')
    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=DAY_CHOICES)

    TIME_CHOICES = [(5.0, "5 AM"), (5.5, "5:30 AM"),
                    (6.0, "6 AM"), (6.5, "6:30 AM"),
                    (7.0, "7:00 AM"), (7.5, "7:30 AM"),
                    (8.0, "8:00 AM"), (8.5, "8:30 AM"),
                    (9.0, "9:00 AM"), (9.5, "9:30 AM"),
                    (10.0, "10:00 AM"), (10.5, "10:30 AM"),
                    (11.0, "11:00 AM"), (11.5, "11:30 AM"),
                    (12.0, "12:00 PM"), (12.5, "12:30 PM"),
                    (13.0, "1:00 PM"), (13.5, "1:30 PM"),
                    (14.0, "2:00 PM"), (14.5, "2:30 PM"),
                    (15.0, "3:00 PM"), (15.5, "3:30 PM"),
                    (16.0, "4:00 PM"), (16.5, "4:30 PM"),
                    (17.0, "5:00 PM"), (17.5, "5:30 PM"),
                    (18.0, "6:00 PM"), (18.5, "6:30 PM"),
                    (19.0, "7:00 PM"), (19.5, "7:30 PM"),
                    (20.0, "8:00 PM"), (20.5, "8:30 PM"),
                    (21.0, "9:00 PM"), (21.5, "9:30 PM"),
                    (22.0, "10:00 PM"), (22.5, "10:30 PM"),
                    (23.0, "11 PM"), (23.5, "11:30 PM")]

    TYPE_CHOICES = [(1, "Fixed"),
                    (2, "On Call")]

    start = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    end = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    fees = models.PositiveSmallIntegerField(blank=False, null=False)
    deal_price = models.PositiveSmallIntegerField(blank=True, null=True)
    mrp = models.PositiveSmallIntegerField(blank=False, null=True)
    type = models.IntegerField(default=1, choices=TYPE_CHOICES)
    cod_deal_price = models.PositiveSmallIntegerField(blank=True, null=True)
    # followup_duration = models.PositiveSmallIntegerField(blank=False, null=True)
    # followup_charges = models.PositiveSmallIntegerField(blank=False, null=True)

    class Meta:
        db_table = "doctor_clinic_timing"
        # unique_together = (("start", "end", "day", "doctor_clinic",),)

    def is_enabled_for_cod(self):
        return self.doctor_clinic.is_enabled_for_cod()

    def dct_cod_deal_price(self):
        if self.is_enabled_for_cod():
            if self.cod_deal_price:
                return self.cod_deal_price
            else:
                return self.mrp
        return None

    def save(self, *args, **kwargs):
        if self.fees != None:
            # deal_price = math.ceil(self.fees + (self.mrp - self.fees)*.1)
            # deal_price = math.ceil(deal_price/10)*10
            # if deal_price<self.fees:
            #     deal_price = self.fees
            #
            # deal_price = max(deal_price, 100)
            # deal_price = min(self.mrp, deal_price)
            #if deal_price>self.mrp:
            #    deal_price = self.mrp
            self.deal_price = self.fees
        super().save(*args, **kwargs)


class DoctorHospital(auth_model.TimeStampedModel):
    DAY_CHOICES = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    doctor = models.ForeignKey(Doctor, related_name="availability", on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    day = models.PositiveSmallIntegerField(blank=False, null=False, choices=DAY_CHOICES)

    TIME_CHOICES = [(7.0, "7:00 AM"), (7.5, "7:30 AM"),
                    (8.0, "8:00 AM"), (8.5, "8:30 AM"),
                    (9.0, "9:00 AM"), (9.5, "9:30 AM"),
                    (10.0, "10:00 AM"), (10.5, "10:30 AM"),
                    (11.0, "11:00 AM"), (11.5, "11:30 AM"),
                    (12.0, "12:00 PM"), (12.5, "12:30 PM"),
                    (13.0, "1:00 PM"), (13.5, "1:30 PM"),
                    (14.0, "2:00 PM"), (14.5, "2:30 PM"),
                    (15.0, "3:00 PM"), (15.5, "3:30 PM"),
                    (16.0, "4:00 PM"), (16.5, "4:30 PM"),
                    (17.0, "5:00 PM"), (17.5, "5:30 PM"),
                    (18.0, "6:00 PM"), (18.5, "6:30 PM"),
                    (19.0, "7:00 PM"), (19.5, "7:30 PM"),
                    (20.0, "8:00 PM"), (20.5, "8:30 PM"),
                    (21.0, "9:00 PM"), (21.5, "9:30 PM"),
                    (22.0, "10:00 PM"), (22.5, "10:30 PM")]

    start = models.DecimalField(max_digits=3,decimal_places=1, choices = TIME_CHOICES)
    end = models.DecimalField(max_digits=3,decimal_places=1, choices = TIME_CHOICES)
    fees = models.PositiveSmallIntegerField(blank=False, null=False)
    deal_price = models.PositiveSmallIntegerField(blank=True, null=True)
    mrp = models.PositiveSmallIntegerField(blank=False, null=True)
    followup_duration = models.PositiveSmallIntegerField(blank=False, null=True)
    followup_charges = models.PositiveSmallIntegerField(blank=False, null=True)

    # def __str__(self):
    #     return self.doctor.name + " " + self.hospital.name + " ," + str(self.start)+ " " + str(self.end) + " " + str(self.day)

    def discounted_fees(self):
        return self.fees

    class Meta:
        db_table = "doctor_hospital"
        unique_together = (("start", "end", "day", "hospital", "doctor"),)

    def save(self, *args, **kwargs):
        if self.mrp!=None:
            deal_price = math.ceil(self.fees + (self.mrp - self.fees)*.1)
            deal_price = math.ceil(deal_price/10)*10
            if deal_price>self.mrp:
                deal_price = self.mrp
            if deal_price<self.fees:
                deal_price = self.fees
            self.deal_price = deal_price
        super().save(*args, **kwargs)


class DoctorImage(auth_model.TimeStampedModel, auth_model.Image):
    image_sizes = [(80, 80)]
    image_base_path = 'doctor/images'
    doctor = models.ForeignKey(Doctor, related_name="images", on_delete=models.CASCADE)
    name = models.ImageField('Original Image Name',upload_to='doctor/images',height_field='height', width_field='width')
    cropped_image = models.ImageField(upload_to='doctor/images', height_field='height', width_field='width',
                                      blank=True, null=True)

    def __str__(self):
        return '{}'.format(self.doctor)

    def get_image_name(self):
        name = self.doctor.name
        doctor_spec_name = "dr " + name
        selected_spec = None
        for dps in self.doctor.doctorpracticespecializations.all():
            if not selected_spec:
                selected_spec = dps.specialization
            if dps.specialization.doctor_count > selected_spec.doctor_count:
                selected_spec = dps.specialization

        if selected_spec:
            doctor_spec_name += " " + selected_spec.name
        doctor_spec_name = doctor_spec_name.strip()
        return slugify(doctor_spec_name)

    def resize_cropped_image(self, width, height):
        default_storage_class = get_storage_class()
        storage_instance = default_storage_class()

        path = self.get_thumbnail_path(self.cropped_image.name,"{}x{}".format(width, height))
        if storage_instance.exists(path):
            return

        if self.cropped_image.closed:
            self.cropped_image.open()
        with Img.open(self.cropped_image) as img:
            img = img.copy()

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


    def create_all_images(self):
        if not self.cropped_image:
            return
        for size in DoctorImage.image_sizes:
            width = size[0]
            height = size[1]
            self.resize_cropped_image(width, height)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.create_all_images()

    def original_image(self):
        return mark_safe('<div><img crossOrigin="anonymous" style="max-width:300px; max-height:300px;" src="{0}"/></div>'.format(self.name.url))

    def cropped_img(self):
        return mark_safe('<div><img style="max-width:200px; max-height:200px;" src="{0}"/></div>'.format(self.cropped_image.url))

    def crop_image(self):
        if self.cropped_image:
            return
        if self.name:
            img = Img.open(self.name)
            w, h = img.size
            if w > h:
                cropping_area = (w / 2 - h / 2,  0, w / 2 + h / 2, h)
            else:
                cropping_area = (0, h / 2 - w / 2, w, h / 2 + w / 2)
            if h != w:
                img = img.crop(cropping_area)
            new_image_io = BytesIO()
            img.save(new_image_io, format='JPEG')
            #md5_hash = hashlib.md5(img.tobytes()).hexdigest()
            md5_hash = self.get_image_name()

            self.cropped_image = InMemoryUploadedFile(new_image_io, None, md5_hash + ".jpg", 'image/jpeg',
                                                      new_image_io.tell(), None)
            self.save()

    def save_to_cropped_image(self, image_file):
        if image_file:
            img = Img.open(image_file)
            #md5_hash = hashlib.md5(img.tobytes()).hexdigest()
            md5_hash = self.get_image_name()
            self.cropped_image.save(md5_hash + ".jpg", image_file, save=True)
            #self.save()

    @classmethod
    def rename_cropped_images(cls):
        images = cls.objects.prefetch_related('doctor','doctor__doctorpracticespecializations','doctor__doctorpracticespecializations__specialization').filter(cropped_image__isnull=False).order_by('id')[:100]
        for img in images:
            image_name = img.get_image_name()
            if img.cropped_image and not image_name in img.cropped_image.name:
                new_img = Img.open(img.cropped_image)
                if new_img.mode != 'RGB':
                    new_img = new_img.convert('RGB')
                new_image_io = BytesIO()
                new_img.save(new_image_io, format='JPEG')

                img.cropped_image = InMemoryUploadedFile(new_image_io, None, image_name + ".jpg", 'image/jpeg',
                                                          new_image_io.tell(), None)
                img.save()


    class Meta:
        db_table = "doctor_image"


class DoctorDocument(auth_model.TimeStampedModel, auth_model.Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    REGISTRATION = 4
    CHEQUE = 5
    AADHAR = 7
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (REGISTRATION, "MCI Registration Number"), (CHEQUE, "Cancel Cheque Copy"), (AADHAR, "Aadhar Card")]

    doctor = models.ForeignKey(Doctor, related_name="documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='doctor/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def extension(self):
        name, extension = os.path.splitext(self.name.name)
        return extension

    def is_pdf(self):
        return self.name.name.endswith('.pdf')

    class Meta:
        db_table = "doctor_document"


class HospitalImage(auth_model.TimeStampedModel, auth_model.Image):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.ImageField(upload_to='hospital/images', height_field='height', width_field='width')
    cropped_image = models.ImageField(upload_to='hospital/images', height_field='height', width_field='width',
                                      blank=True, null=True)
    cover_image = models.BooleanField(default=False, verbose_name="Can be used as Hospital's cover image?")

    class Meta:
        db_table = "hospital_image"

    def use_image_name(self):
        return True

    def get_image_name(self):
        name = self.hospital.name
        return slugify(name)

    def auto_generate_thumbnails(self):
        return True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.create_thumbnail()



class HospitalDocument(auth_model.TimeStampedModel, auth_model.Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    CHEQUE = 5
    LOGO = 6
    COI = 8
    EMAIL_CONFIRMATION = 9
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (CHEQUE, "Cancel Cheque Copy"), (COI, "COI/Company Registration"),
               (EMAIL_CONFIRMATION, "Email Confirmation"),
               (LOGO, "Logo")]

    hospital = models.ForeignKey(Hospital, related_name="hospital_documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES, default=ADDRESS)
    name = models.FileField(upload_to='hospital/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    class Meta:
        db_table = "hospital_document"

    def use_image_name(self):
        return True

    def get_image_name(self):
        name = self.hospital.name
        return slugify(name)


class Language(auth_model.TimeStampedModel, UniqueNameModel):
    name = models.CharField(max_length=100)
    short_name = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "language"


class DoctorLanguage(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="languages", on_delete=models.CASCADE)
    language = models.ForeignKey(Language, on_delete=models.CASCADE)

    # def __str__(self):
    #     return self.doctor.name + " (" + self.language.name + ")"

    class Meta:
        db_table = "doctor_language"
        unique_together = (("doctor", "language"),)


class DoctorAward(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="awards", on_delete=models.CASCADE)
    name = models.CharField(max_length=2000)
    year = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.name

    class Meta:
        db_table = "doctor_awards"


class DoctorAssociation(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="associations", on_delete=models.CASCADE)
    name = models.CharField(max_length=2000)

    # def __str__(self):
    #     return self.doctor.name + " (" + self.name + ")"

    class Meta:
        db_table = "doctor_association"


class DoctorExperience(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="experiences", on_delete=models.CASCADE)
    hospital = models.CharField(max_length=2000)
    start_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,
                                                  validators=[MinValueValidator(1950)])
    end_year = models.PositiveSmallIntegerField(default=None, blank=True, null=True,
                                                validators=[MinValueValidator(1950)])

    class Meta:
        db_table = "doctor_experience"


class DoctorMedicalService(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="medical_services", on_delete=models.CASCADE)
    service = models.ForeignKey(MedicalService, on_delete=models.CASCADE)

    class Meta:
        db_table = "doctor_medical_service"
        unique_together = (("doctor", "service"),)


class DoctorMobile(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="mobiles", on_delete=models.CASCADE)
    std_code = models.IntegerField(blank=True, null=True)
    number = models.BigIntegerField(blank=True, null=True)
    is_primary = models.BooleanField(verbose_name='Primary Number?', default=False)
    is_phone_number_verified = models.BooleanField(verbose_name='Phone Number Verified?', default=False)
    source = models.CharField(max_length=2000, blank=True)
    otp = models.PositiveIntegerField(null=True, blank=False)
    mark_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "doctor_mobile"
        unique_together = (("doctor", "number","std_code"),)


class DoctorMobileOtpManager(models.Manager):
    def get_queryset(self):
        return super(DoctorMobileOtpManager, self).get_queryset().filter(usable_counter=1, validity__gte=timezone.now())


class DoctorMobileOtp(auth_model.TimeStampedModel):
    doctor_mobile = models.ForeignKey(DoctorMobile, related_name="mobiles_otp", on_delete=models.CASCADE)
    otp = models.PositiveIntegerField()
    validity = models.DateTimeField(default=doctor_mobile_otp_validity)
    usable_counter = models.SmallIntegerField(default=1)

    objects = DoctorMobileOtpManager()

    @classmethod
    def create_otp(cls, doctor_mobile_obj):
        otp = randint(100000,999999)
        dmo = cls(doctor_mobile=doctor_mobile_obj, otp=otp)
        dmo.save()
        print(dmo.otp)
        return dmo

    def is_valid(self):
        if self.validity > timezone.now() and self.usable_counter == 1 :
            return True
        return False

    def consume(self):
        if self.is_valid():
            if self.doctor_mobile.otp == self.otp:
                self.usable_counter = 0
                self.save()
                return True
            else:
                print('OTP not matched')
                return False
        else:
            print('[ERROR] Otp is expired.')
            return False

    class Meta:
        db_table = "doctor_mobile_otp"


class DoctorEmail(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="emails", on_delete=models.CASCADE)
    email = models.EmailField(max_length=100, blank=True)
    is_primary = models.BooleanField(verbose_name='Primary Email?', default=False)
    is_email_verified = models.BooleanField(verbose_name='Phone Number Verified?', default=False)

    class Meta:
        db_table = "doctor_email"
        unique_together = (("doctor", "email"),)


class HospitalNetwork(auth_model.TimeStampedModel, auth_model.CreatedByModel, auth_model.QCModel, auth_model.WelcomeCallingDone, auth_model.PhysicalAgreementSigned):
    name = models.CharField(max_length=100)
    operational_since = models.PositiveSmallIntegerField(blank=True, null=True, validators=[MinValueValidator(1900)])
    about = models.CharField(max_length=2000, blank=True)
    # use_new_about = models.BooleanField(default=False)
    new_about = models.TextField(blank=True, null=True, default=None)
    network_size = models.PositiveSmallIntegerField(blank=True, null=True)
    building = models.CharField(max_length=100, blank=True)
    sublocality = models.CharField(max_length=100, blank=True)
    locality = models.CharField(max_length=100, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    matrix_state = models.ForeignKey(MatrixMappedState, null=True, blank=False, on_delete=models.DO_NOTHING,
                                     related_name='hospital_networks_in_state', verbose_name='State')
    matrix_city = models.ForeignKey(MatrixMappedCity, null=True, blank=False, on_delete=models.DO_NOTHING,
                                    related_name='hospital_networks_in_city', verbose_name='City')
    country = models.CharField(max_length=100)
    pin_code = models.PositiveIntegerField(blank=True, null=True)
    is_billing_enabled = models.BooleanField(verbose_name='Enabled for Billing', default=False)

    # generic_hospital_network_admins = GenericRelation(auth_model.GenericAdmin, related_query_name='manageable_hospital_networks')
    assigned_to = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL, related_name='assigned_hospital_networks')
    billing_merchant = GenericRelation(auth_model.BillingAccount)
    spoc_details = GenericRelation(auth_model.SPOCDetails)
    merchant = GenericRelation(auth_model.AssociatedMerchant)
    open_for_communication = models.BooleanField(default=True)    
    matrix_lead_id = models.BigIntegerField(blank=True, null=True, unique=True)
    remark = GenericRelation(Remark)
    auto_ivr_enabled = models.BooleanField(default=True)
    priority_score = models.IntegerField(default=0, null=False, blank=False)

    def update_time_stamps(self):
        if self.welcome_calling_done and not self.welcome_calling_done_at:
            self.welcome_calling_done_at = timezone.now()
        elif not self.welcome_calling_done and self.welcome_calling_done_at:
            self.welcome_calling_done_at = None

    def save(self, *args, **kwargs):
        self.update_time_stamps()
        push_to_matrix = False
        update_status_in_matrix = False
        if self.id:
            hospital_network_obj = HospitalNetwork.objects.filter(pk=self.id).first()
            if hospital_network_obj and self.data_status != hospital_network_obj.data_status:
                update_status_in_matrix = True
        if not self.matrix_lead_id:
            push_to_matrix = True
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.app_commit_tasks(push_to_matrix=push_to_matrix,
                                                            update_status_in_matrix=update_status_in_matrix))

    def app_commit_tasks(self, push_to_matrix=False, update_status_in_matrix=False):
        if push_to_matrix:
            create_or_update_lead_on_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                         ,), countdown=5)

        if update_status_in_matrix:
            update_onboarding_qcstatus_to_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                              ,), countdown=5)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "hospital_network"


class HospitalNetworkDocument(auth_model.TimeStampedModel, auth_model.Document):
    PAN = 1
    ADDRESS = 2
    GST = 3
    CHEQUE = 5
    LOGO = 6
    COI = 8
    EMAIL_CONFIRMATION = 9
    CHOICES = [(PAN, "PAN Card"), (ADDRESS, "Address Proof"), (GST, "GST Certificate"),
               (CHEQUE, "Cancel Cheque Copy"),(COI, "COI/Company Registration"),
               (EMAIL_CONFIRMATION, "Email Confirmation"),
               (LOGO, "Logo")]

    hospital_network = models.ForeignKey(HospitalNetwork, related_name="hospital_network_documents", on_delete=models.CASCADE)
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='hospital_network/documents', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    class Meta:
        db_table = "hospital_network_document"


class HospitalNetworkCertification(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "hospital_network_certification"


class HospitalNetworkAward(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    year = models.PositiveSmallIntegerField(validators=[MinValueValidator(1900)])

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_award"


class HospitalNetworkAccreditation(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.network.name + " (" + self.name + ")"

    class Meta:
        db_table = "hospital_network_accreditation"


class HospitalNetworkManager(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    number = models.BigIntegerField()
    email = models.EmailField(max_length=100, blank=True)
    details = models.CharField(max_length=200, blank=True)
    contact_type = models.PositiveSmallIntegerField(
        choices=[(1, "Other"), (2, "Single Point of Contact"), (3, "Manager")])

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_manager"


class HospitalNetworkHelpline(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    number = models.BigIntegerField()
    details = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_helpline"


class HospitalNetworkEmail(auth_model.TimeStampedModel):
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
    email = models.EmailField(max_length=100)

    def __str__(self):
        return self.network.name

    class Meta:
        db_table = "hospital_network_email"


class DoctorOnboardingToken(auth_model.TimeStampedModel):
    GENERATED = 1
    REJECTED = 2
    CONSUMED = 3
    STATUS_CHOICES = [(GENERATED, "Generated"), (REJECTED, "Rejected"), (CONSUMED, "Consumed")]
    doctor = models.ForeignKey(Doctor, null=True, on_delete=models.SET_NULL)
    token = models.CharField(max_length=100)
    email = models.EmailField(max_length=100, blank=True)
    mobile = models.BigIntegerField(blank=True, null=True,
                                    validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    verified_token = models.CharField(max_length=100, null=True)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=GENERATED)

    def __str__(self):
        return self.doctor.name + " " + self.email + " " + str(self.mobile)

    class Meta:
        db_table = "doctor_onboarding_token"


# class HospitalNetworkMapping(auth_model.TimeStampedModel):
#     network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE)
#     hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)

#     def __str__(self):
#         return self.network.name + " (" + self.hospital.name + ")"

#     class Meta:
#         db_table = "hospital_network_mapping"

class OpdAppointmentInvoiceMixin(object):
    def generate_invoice(self, context=None):
        invoices = self.get_invoice_objects()
        if not invoices:
            if not context:
                from ondoc.communications.models import OpdNotification
                opd_notification = OpdNotification(self)
                context = opd_notification.get_context()
            invoice = Invoice.objects.create(reference_id=context.get("instance").id,
                                             product_id=Order.DOCTOR_PRODUCT_ID)
            context = deepcopy(context)
            context['invoice'] = invoice
            html_body = render_to_string("email/doctor_invoice/invoice_template.html", context=context)
            # filename = "invoice_{}_{}.pdf".format(str(timezone.now().strftime("%I%M_%d%m%Y")),
            #                                       random.randint(1111111111, 9999999999))
            filename = "payment_receipt_{}.pdf".format(context.get('instance').id)
            file = html_to_pdf(html_body, filename)
            if not file:
                logger.error("Got error while creating pdf for opd invoice.")
                return []
            invoice.file = file
            invoice.save()
            invoices = [invoice]
        return invoices


@reversion.register()
class OpdAppointment(auth_model.TimeStampedModel, CouponsMixin, OpdAppointmentInvoiceMixin, RefundMixin, CompletedBreakupMixin, MatrixDataMixin, TdsDeductionMixin):
    PRODUCT_ID = Order.DOCTOR_PRODUCT_ID
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_DOCTOR = 3
    RESCHEDULED_PATIENT = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7

    PAYMENT_ACCEPTED = 1
    PAYMENT_PENDING = 0
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_ACCEPTED, 'Payment Accepted'),
        (PAYMENT_PENDING, 'Payment Pending'),
    )
    PREPAID = 1
    COD = 2
    INSURANCE = 3
    PLAN = 4
    PAY_CHOICES = ((PREPAID, 'Prepaid'), (COD, 'COD'), (INSURANCE, 'Insurance'), (PLAN, "Subscription Plan"))
    ACTIVE_APPOINTMENT_STATUS = [BOOKED, ACCEPTED, RESCHEDULED_PATIENT, RESCHEDULED_DOCTOR]
    STATUS_CHOICES = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                      (RESCHEDULED_DOCTOR, 'Rescheduled by Doctor'),
                      (RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                      (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                      (COMPLETED, 'Completed')]
    PATIENT_CANCELLED = 1
    AGENT_CANCELLED = 2
    AUTO_CANCELLED = 3
    CANCELLATION_TYPE_CHOICES = [(PATIENT_CANCELLED, 'Patient Cancelled'), (AGENT_CANCELLED, 'Agent Cancelled'),
                                 (AUTO_CANCELLED, 'Auto Cancelled')]

    MAX_FREE_BOOKINGS_ALLOWED = 3
    # PATIENT_SHOW = 1
    # PATIENT_DIDNT_SHOW = 2
    # PATIENT_STATUS_CHOICES = [PATIENT_SHOW, PATIENT_DIDNT_SHOW]
    doctor = models.ForeignKey(Doctor, related_name="appointments", on_delete=models.SET_NULL, null=True)
    hospital = models.ForeignKey(Hospital, related_name="hospital_appointments", on_delete=models.SET_NULL, null=True)
    profile = models.ForeignKey(auth_model.UserProfile, related_name="appointments", on_delete=models.SET_NULL, null=True)
    profile_detail = JSONField(blank=True, null=True)
    user = models.ForeignKey(auth_model.User, related_name="appointments", on_delete=models.SET_NULL, null=True)
    booked_by = models.ForeignKey(auth_model.User, related_name="booked_appointements", on_delete=models.SET_NULL, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2)
    effective_price = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=None)
    mrp = models.DecimalField(max_digits=10, decimal_places=2, blank=False, null=False, default=None)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2, blank=False, default=None, null=False)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)
    cancellation_type = models.PositiveSmallIntegerField(choices=CANCELLATION_TYPE_CHOICES, blank=True, null=True)
    payment_status = models.PositiveSmallIntegerField(choices=PAYMENT_STATUS_CHOICES, default=PAYMENT_PENDING)
    otp = models.PositiveIntegerField(blank=True, null=True)
    # patient_status = models.PositiveSmallIntegerField(blank=True, null=True)
    time_slot_start = models.DateTimeField(blank=True, null=True)
    time_slot_end = models.DateTimeField(blank=True, null=True)
    payment_type = models.PositiveSmallIntegerField(choices=PAY_CHOICES, default=PREPAID)
    insurance = models.ForeignKey(insurance_model.UserInsurance, blank=True, null=True, default=None,
                                  on_delete=models.DO_NOTHING)
    outstanding = models.ForeignKey(Outstanding, blank=True, null=True, on_delete=models.SET_NULL)
    matrix_lead_id = models.IntegerField(null=True)
    is_rated = models.BooleanField(default=False)
    rating_declined = models.BooleanField(default=False)
    coupon = models.ManyToManyField(Coupon, blank=True, null=True, related_name="opd_appointment_coupon")
    discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cashback = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cancellation_reason = models.ForeignKey('CancellationReason', on_delete=models.SET_NULL, null=True, blank=True)
    cancellation_comments = models.CharField(max_length=5000, null=True, blank=True)
    rating = GenericRelation(ratings_models.RatingsReview)
    procedures = models.ManyToManyField('procedure.Procedure', through='OpdAppointmentProcedureMapping',
                                        through_fields=('opd_appointment', 'procedure'), null=True, blank=True)

    merchant_payout = models.ForeignKey(MerchantPayout, related_name="opd_appointment", on_delete=models.SET_NULL, null=True)
    price_data = JSONField(blank=True, null=True)
    money_pool = models.ForeignKey(MoneyPool, on_delete=models.SET_NULL, null=True, related_name="opd_apps")
    mask_number = GenericRelation(AppointmentMaskNumber)
    history = GenericRelation(AppointmentHistory)
    email_notification = GenericRelation(EmailNotification, related_name="enotification")
    auto_ivr_data = JSONField(default=list(), null=True)
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="opd_booking_analytics")
    refund_details = GenericRelation(RefundDetails, related_query_name="opd_appointment_detail")
    appointment_prescriptions = GenericRelation("prescription.AppointmentPrescription", related_query_name="appointment_prescriptions")
    coupon_data = JSONField(blank=True, null=True)
    status_change_comments = models.CharField(max_length=5000, null=True, blank=True)
    is_cod_to_prepaid = models.NullBooleanField(default=False, null=True, blank=True)
    hospital_reference_id = models.CharField(max_length=1000, null=True, blank=True)
    documents = GenericRelation(Documents)

    def __str__(self):
        return self.profile.name + " (" + self.doctor.name + ")"

    def get_cod_amount(self):
        result = int(self.mrp)
        day = self.time_slot_start.weekday()
        if self.doctor:
            aware_dt = timezone.localtime(self.time_slot_start)
            hour_min = aware_dt.hour + aware_dt.minute / 60
            doc_clinic = DoctorClinicTiming.objects.filter(day=day, doctor_clinic__doctor=self.doctor,
                                                           doctor_clinic__hospital=self.hospital, start__lte=hour_min,
                                                           end__gt=hour_min).first()
            if doc_clinic:
                try:
                    result = doc_clinic.dct_cod_deal_price()
                except:
                    pass
        return result

    def allowed_action(self, user_type, request):
        allowed = []
        if self.status == self.CREATED:
            if user_type == auth_model.User.CONSUMER:
                return [self.CANCELLED]
            return []

        current_datetime = timezone.now()
        today = datetime.date.today()
        if user_type == auth_model.User.DOCTOR and self.time_slot_start.date() >= today:
            if self.status in [self.BOOKED, self.RESCHEDULED_PATIENT]:
                allowed = [self.ACCEPTED, self.RESCHEDULED_DOCTOR]
            elif self.status == self.ACCEPTED:
                allowed = [self.RESCHEDULED_DOCTOR, self.COMPLETED]
            elif self.status == self.RESCHEDULED_DOCTOR:
                allowed = [self.ACCEPTED]
        elif user_type == auth_model.User.DOCTOR and self.time_slot_start.date() < today:
            if self.status == self.ACCEPTED:
                allowed = [self.COMPLETED]
        elif user_type == auth_model.User.CONSUMER and current_datetime <= self.time_slot_start:
            if self.status in (self.BOOKED, self.ACCEPTED, self.RESCHEDULED_DOCTOR, self.RESCHEDULED_PATIENT):
                allowed = [self.RESCHEDULED_PATIENT, self.CANCELLED]
        elif user_type == auth_model.User.CONSUMER and current_datetime > self.time_slot_start:
            if self.status in [self.BOOKED, self.RESCHEDULED_DOCTOR, self.RESCHEDULED_PATIENT, self.ACCEPTED]:
                allowed = [self.RESCHEDULED_PATIENT]
            if self.status == self.ACCEPTED:
                allowed.append(self.COMPLETED)

        return allowed

    def get_corporate_deal_id(self):
        coupon = self.coupon.first()
        if coupon and coupon.corporate_deal:
            return coupon.corporate_deal.id

        return None

    def get_all_prescriptions(self):
        from ondoc.common.utils import get_file_mime_type

        resp = []
        for pres in self.prescriptions.all():
            for pf in pres.prescription_file.all():
                file = pf.name
                mime_type = get_file_mime_type(file)
                file_url = pf.name.url
                resp.append({"url": file_url, "type": mime_type})
        return resp


    def get_city(self):
        if self.hospital and self.hospital.matrix_city:
            return self.hospital.matrix_city.id
        else:
            return None

    def get_state(self):
        if self.hospital and self.hospital.matrix_state:
            return self.hospital.matrix_state.id
        else:
            return None

    def sync_with_booking_analytics(self):

        promo_cost = self.deal_price - self.effective_price if self.deal_price and self.effective_price else 0
        department = None
        if self.doctor:
            if self.doctor.doctorpracticespecializations.first():
                if self.doctor.doctorpracticespecializations.first().specialization.department.first():
                    department = self.doctor.doctorpracticespecializations.first().specialization.department.first().id

        wallet, cashback = self.get_completion_breakup()

        obj = DP_OpdConsultsAndTests.objects.filter(Appointment_Id=self.id, TypeId=1).first()
        if not obj:
            obj = DP_OpdConsultsAndTests()
            obj.Appointment_Id = self.id
            obj.CityId = self.get_city()
            obj.StateId = self.get_state()
            obj.SpecialityId = department
            obj.TypeId = 1
            obj.ProviderId = self.hospital.id
            obj.PaymentType = self.payment_type if self.payment_type else None
            obj.Payout = self.fees
            obj.CashbackUsed = cashback
            obj.BookingDate = self.created_at
        obj.CorporateDealId = self.get_corporate_deal_id()
        obj.PromoCost = max(0, promo_cost)
        obj.GMValue = self.deal_price
        obj.StatusId = self.status
        obj.save()

        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(OpdAppointment),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            pass

        return obj

    def get_invoice_objects(self):
        return Invoice.objects.filter(reference_id=self.id, product_id=Order.DOCTOR_PRODUCT_ID)

    def get_document_objects(self, document_type=1, is_valid=True):
        return self.documents.filter(document_type=document_type, is_valid=is_valid).order_by('-created_at')

    def get_cancellation_reason(self):
        return CancellationReason.objects.filter(Q(type=Order.DOCTOR_PRODUCT_ID) | Q(type__isnull=True),
                                                 visible_on_front_end=True)

    def get_serialized_cancellation_reason(self):
        res = []
        for cr in self.get_cancellation_reason():
            res.append({'id': cr.id, 'name': cr.name, 'is_comment_needed': cr.is_comment_needed})
        return res

    def get_invoice_urls(self):
        invoices_urls = []
        if self.id:
            invoices = self.get_invoice_objects()
            for invoice in invoices:
                if invoice.file:
                    invoices_urls.append(util_absolute_url(invoice.file.url))
        return invoices_urls

    def is_credit_letter_required_for_appointment(self):
        hospital_ids_cl_required = list(settings.HOSPITAL_CREDIT_LETTER_REQUIRED.values())
        if self.hospital and self.hospital.id in hospital_ids_cl_required:
            if self.is_medanta_hospital_booking() or self.is_artemis_hospital_booking():
                return True
        return False


    def get_valid_credit_letter(self):
        credit_letter = self.get_document_objects(Documents.CREDIT_LETTER).first()
        return credit_letter

    def get_credit_letter_url(self):
        credit_letter_url = None
        if self.id:
            credit_letter = self.get_document_objects(Documents.CREDIT_LETTER).first()
            if credit_letter:
                if credit_letter.file:
                    credit_letter_url = util_absolute_url(credit_letter.file.url)
        return credit_letter_url

    # @staticmethod
    # def get_upcoming_appointment_serialized(user_id):
    #     response_appointment = OpdAppointment.get_upcoming_appointment(user_id)
    #     appointment = doctor_serializers.OpdAppointmentUpcoming(response_appointment, many=True)
    #     return appointment.data

    def is_payment_type_cod(self):
        return self.payment_type == OpdAppointment.COD

    @classmethod
    def get_upcoming_appointment(cls, user_id):
        current_time = timezone.now()
        appointments = OpdAppointment.objects.filter(time_slot_start__lte=current_time + timedelta(hours=48), user_id=user_id, time_slot_start__gte=current_time).exclude(
            status__in=[OpdAppointment.CANCELLED, OpdAppointment.COMPLETED]).select_related('doctor', 'hospital','profile')
        return appointments

    @classmethod
    def create_appointment(cls, appointment_data):

        insurance = appointment_data.get('insurance')
        appointment_status = OpdAppointment.BOOKED

        # if insurance and insurance.is_valid():
        #     hospital = appointment_data.get('hospital')
        #     if hospital:
        #        is_appointment_exist = hospital.get_active_opd_appointments(insurance.user, insurance, appointment_data.get('time_slot_start').date())
        #        if is_appointment_exist:
        #            raise Exception('Some error occurred. Please try after some time')
        #     mrp = appointment_data.get('fees')
        #     insurance_limit_usage_data = insurance.validate_limit_usages(mrp)
        #     if insurance_limit_usage_data.get('created_state'):
        #         appointment_status = OpdAppointment.CREATED

        otp = random.randint(1000, 9999)
        appointment_data["payment_status"] = OpdAppointment.PAYMENT_ACCEPTED
        appointment_data["status"] = appointment_status
        appointment_data["otp"] = otp
        # if appointment_data["insurance_id"] :
        #     appointment_data["insurance"] = insurance_model.UserInsurance.objects.get(id=appointment_data["insurance_id"].id)
        coupon_list = appointment_data.pop("coupon", None)
        coupon_data = {
            "random_coupons": appointment_data.pop("coupon_data", [])
        }
        procedure_details = appointment_data.pop('extra_details', [])
        app_obj = cls.objects.create(**appointment_data)
        if procedure_details:
            procedure_to_be_added = []
            for procedure in procedure_details:
                procedure['opd_appointment_id'] = app_obj.id
                procedure.pop('procedure_name')
                procedure_to_be_added.append(OpdAppointmentProcedureMapping(**procedure))
            OpdAppointmentProcedureMapping.objects.bulk_create(procedure_to_be_added)
        if coupon_list:
            app_obj.coupon.add(*coupon_list)
        app_obj.coupon_data = coupon_data
        return app_obj

    @transaction.atomic
    def action_rescheduled_doctor(self):
        self.status = self.RESCHEDULED_DOCTOR
        self.save()

    def action_rescheduled_patient(self, data):
        self.status = self.RESCHEDULED_PATIENT
        self.time_slot_start = data.get('time_slot_start')
        self.fees = data.get('fees', self.fees)
        self.mrp = data.get('mrp', self.mrp)
        self.deal_price = data.get('deal_price', self.deal_price)
        self.effective_price = data.get('effective_price', self.effective_price)
        self.save()

        # return self

    def action_accepted(self):
        self.status = self.ACCEPTED
        self.save()

    def update_ivr_status(self, status):
        if status == self.status:
            return True, ""

        if self.status in [OpdAppointment.COMPLETED, OpdAppointment.CANCELLED]:
            return False, 'Appointment cannot be accepted as current status is %s' % str(self.status)

        if status == OpdAppointment.ACCEPTED:
            # Constraints: Check if appointment can be accepted or not.
            if self.time_slot_start < timezone.now():
                return False, 'Appointment cannot be accepted as time slot has been expired'

            self.action_accepted()

        elif status == OpdAppointment.COMPLETED:
            self.action_completed()

        return True, ""

    @transaction.atomic
    def action_cancelled(self, refund_flag=1):
        old_instance = OpdAppointment.objects.get(pk=self.id)
        if old_instance.status != self.CANCELLED:
            self.status = self.CANCELLED
            self.save()
            self.action_refund(refund_flag)

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

    def action_completed(self):
        self.status = self.COMPLETED
        if self.payment_type != self.INSURANCE:
            if not self.outstanding:
                admin_obj, out_level = self.get_billable_admin_level()
                app_outstanding_fees = self.doc_payout_amount()
                out_obj = payout_model.Outstanding.create_outstanding(admin_obj, out_level, app_outstanding_fees)
                self.outstanding = out_obj
        self.save()

    def get_billable_admin_level(self):
        if self.hospital.network and self.hospital.network.is_billing_enabled:
            return self.hospital.network, payout_model.Outstanding.HOSPITAL_NETWORK_LEVEL
        elif self.hospital.is_billing_enabled:
            return self.hospital, payout_model.Outstanding.HOSPITAL_LEVEL
        else:
            return self.doctor, payout_model.Outstanding.DOCTOR_LEVEL

    def get_cancel_amount(self, data):
        consumer_tx = (ConsumerTransaction.objects.filter(user=data["user"],
                                                                        product=data["product"],
                                                                        order=data["order"],
                                                                        type=PgTransaction.DEBIT,
                                                                        action=ConsumerTransaction.SALE).
                       order_by("created_at").last())
        return consumer_tx.amount

    def is_doctor_available(self):
        if DoctorLeave.objects.filter(start_date__lte=self.time_slot_start.date(),
                                      end_date__gte=self.time_slot_start.date(),
                                      start_time__lte=self.time_slot_start.time(),
                                      end_time__gte=self.time_slot_start.time(),
                                      doctor=self.doctor,
                                      deleted_at__isnull=True).exists():
            return False
        return True

    def is_to_send_notification(self, database_instance):
        if not database_instance:
            return True
        if database_instance.status != self.status:
            return True
        if (database_instance.status == self.status
                and database_instance.time_slot_start != self.time_slot_start
                and database_instance.status in [OpdAppointment.RESCHEDULED_DOCTOR, OpdAppointment.RESCHEDULED_PATIENT]
                and self.status in [OpdAppointment.RESCHEDULED_DOCTOR, OpdAppointment.RESCHEDULED_PATIENT]):
            return True
        return False

    def send_cod_to_prepaid_request(self):
        result = False
        if self.payment_type != self.COD:
            return result
        order_obj = Order.objects.filter(reference_id=self.id).first()
        if order_obj:
                parent = order_obj.parent
                if parent:
                    result = parent.is_cod_order
        return result

    def after_commit_tasks(self, old_instance, push_to_matrix):
        if old_instance is None:
            try:
                create_ipd_lead_from_opd_appointment.apply_async(({'obj_id': self.id},),)
                                                                 # eta=timezone.now() + timezone.timedelta(hours=1))
                if self.send_cod_to_prepaid_request():
                    notification_tasks.send_opd_notifications_refactored.apply_async(
                        (self.id, NotificationAction.COD_TO_PREPAID_REQUEST), countdown=5)
            except Exception as e:
                logger.error(str(e))
        if push_to_matrix:
        # Push the appointment data to the matrix .
            try:
                push_appointment_to_matrix.apply_async(({'type': 'OPD_APPOINTMENT', 'appointment_id': self.id,
                                                         'product_id': 5, 'sub_product_id': 2},), countdown=5)

            except Exception as e:
                logger.error(str(e))

        if self.is_to_send_notification(old_instance):
            try:
                notification_tasks.send_opd_notifications_refactored.apply_async((self.id,), countdown=1)
            except Exception as e:
                logger.error(str(e))
            # notification_tasks.send_opd_notifications_refactored(self.id)
            # notification_tasks.send_opd_notifications.apply_async(kwargs={'appointment_id': self.id},
            #                                                                  countdown=1)
        if not old_instance or old_instance.status != self.status:
            notification_models.EmailNotification.ops_notification_alert(self, email_list=settings.OPS_EMAIL_ID,
                                                                         product=Order.DOCTOR_PRODUCT_ID,
                                                                         alert_type=notification_models.EmailNotification.OPS_APPOINTMENT_NOTIFICATION)
        if not old_instance or self.status == self.CANCELLED:
            try:
                notification_tasks.update_coupon_used_count.apply_async()
            except Exception as e:
                logger.error(str(e))

        if old_instance and old_instance.is_cod_to_prepaid != self.is_cod_to_prepaid:
            try:

                notification_tasks.send_opd_notifications_refactored.apply_async((self.id, NotificationAction.COD_TO_PREPAID), countdown=1)
            except Exception as e:
                logger.error(str(e))

        # if self.status == self.COMPLETED and not self.is_rated:
        #     try:
        #         notification_tasks.send_opd_rating_message.apply_async(
        #             kwargs={'appointment_id': self.id, 'type': 'opd'}, countdown=int(settings.RATING_SMS_NOTIF))
        #     except Exception as e:
        #         logger.error(str(e))

        if old_instance and old_instance.status != self.ACCEPTED and self.status == self.ACCEPTED:
            try:
                notification_tasks.appointment_reminder_sms_provider.apply_async(
                    (self.id, str(math.floor(self.updated_at.timestamp()))),
                    eta=self.time_slot_start - datetime.timedelta(
                        minutes=int(settings.PROVIDER_SMS_APPOINTMENT_REMINDER_TIME)), )
                notification_tasks.opd_send_otp_before_appointment.apply_async(
                    (self.id, str(math.floor(self.time_slot_start.timestamp()))),
                    eta=self.time_slot_start - datetime.timedelta(
                        minutes=settings.TIME_BEFORE_APPOINTMENT_TO_SEND_OTP), )
                notification_tasks.opd_send_after_appointment_confirmation.apply_async(
                    (self.id, str(math.floor(self.time_slot_start.timestamp()))),
                    eta=self.time_slot_start + datetime.timedelta(
                        minutes=settings.TIME_AFTER_APPOINTMENT_TO_SEND_CONFIRMATION), )
                notification_tasks.opd_send_after_appointment_confirmation.apply_async(
                    (self.id, str(math.floor(self.time_slot_start.timestamp())), True),
                    eta=self.time_slot_start + datetime.timedelta(
                        minutes=settings.TIME_AFTER_APPOINTMENT_TO_SEND_SECOND_CONFIRMATION), )
                notification_tasks.opd_send_after_appointment_confirmation.apply_async(
                    (self.id, str(math.floor(self.time_slot_start.timestamp())), True),
                    eta=self.time_slot_start + datetime.timedelta(
                        minutes=settings.TIME_AFTER_APPOINTMENT_TO_SEND_THIRD_CONFIRMATION), )
                # notification_tasks.opd_send_otp_before_appointment(self.id, self.time_slot_start)
            except Exception as e:
                logger.error(str(e))

        # try:
        #     if self.status not in [OpdAppointment.COMPLETED, OpdAppointment.CANCELLED, OpdAppointment.ACCEPTED]:
        #         countdown = self.get_auto_cancel_delay(self)
        #         doc_app_auto_cancel.apply_async(({
        #             "id": self.id,
        #             "status": self.status,
        #             "updated_at": int(self.updated_at.timestamp())
        #         }, ), countdown=countdown)
        # except Exception as e:
        #     logger.error("Error in auto cancel flow - " + str(e))
        print('all ops tasks completed')

    def save(self, *args, **kwargs):
        logger.warning("opd save started - " + str(self.id) + " timezone - " + str(timezone.now()))
        database_instance = OpdAppointment.objects.filter(pk=self.id).first()
        if database_instance and (database_instance.status == self.COMPLETED or database_instance.status == self.CANCELLED) \
                and (self.status != database_instance.status):
            raise Exception('Cancelled or Completed appointment cannot be saved')
        # if not self.is_doctor_available():
        #     raise RestFrameworkValidationError("Doctor is on leave.")
        # push_to_matrix = kwargs.get('push_again_to_matrix', True)
        # if 'push_again_to_matrix' in kwargs.keys():
        #     kwargs.pop('push_again_to_matrix')

        push_to_matrix = True
        if database_instance and self.status == database_instance.status and self.time_slot_start == database_instance.time_slot_start:
            push_to_matrix = False

        try:
            # while completing appointment
            if database_instance and database_instance.status != self.status and self.status == self.COMPLETED:
                # add a merchant_payout entry
                if self.merchant_payout is None and self.payment_type not in [OpdAppointment.COD]:
                    self.save_merchant_payout()

                # credit cashback if any
                if self.cashback is not None and self.cashback > 0:
                    ConsumerAccount.credit_cashback(self.user, self.cashback, database_instance, Order.DOCTOR_PRODUCT_ID)

                # credit referral cashback if any
                UserReferred.credit_after_completion(self.user, database_instance, Order.DOCTOR_PRODUCT_ID)

        except Exception as e:
            pass

        # Pushing every status to the Appointment history
        push_to_history = False
        if self.id and self.status != OpdAppointment.objects.get(pk=self.id).status:
            push_to_history = True
        elif self.id is None:
            push_to_history = True

        super().save(*args, **kwargs)

        if push_to_history:
            AppointmentHistory.create(content_object=self)

        transaction.on_commit(lambda: self.after_commit_tasks(database_instance, push_to_matrix))

    def save_merchant_payout(self):
        if self.payment_type in [OpdAppointment.COD]:
            raise Exception("Cannot create payout for COD appointments")

        payout_amount = self.fees
        tds = self.get_tds_amount()

        # Update Net Revenue
        self.update_net_revenues(tds)

        payout_data = {
            "charged_amount" : self.effective_price,
            "payable_amount" : payout_amount,
            "booking_type"  : Order.DOCTOR_PRODUCT_ID,
            "tds_amount" : tds
        }

        merchant_payout = MerchantPayout.objects.create(**payout_data)
        self.merchant_payout = merchant_payout

        # TDS Deduction
        if tds > 0:
            merchant = self.get_merchant
            MerchantTdsDeduction.objects.create(merchant=merchant, tds_deducted=tds, financial_year=settings.CURRENT_FINANCIAL_YEAR,
                                                merchant_payout=merchant_payout)

    def doc_payout_amount(self):
        amount = 0
        if self.payment_type == self.COD:
            amount = (-1)*(self.effective_price - self.fees)
        elif self.payment_type == self.PREPAID:
            amount = self.fees

        return amount

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

            agreed_price = self.fees
            booking_net_revenue = wallet_amount - agreed_price
            if booking_net_revenue < 0:
                booking_net_revenue = 0

        return booking_net_revenue

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
        if payment_type in [cls.COD, cls.PREPAID]:
            payment_type = [cls.COD, cls.PREPAID]
        elif payment_type in [cls.INSURANCE]:
            payment_type = [cls.INSURANCE]
        queryset = (OpdAppointment.objects.filter(outstanding=out_obj).
                    filter(status=OpdAppointment.COMPLETED,
                           time_slot_start__gte=start_date_time,
                           time_slot_start__lte=end_date_time,
                           payment_type__in=payment_type))
        if payment_type != cls.INSURANCE:
            tcp_condition = Case(When(payment_type=cls.COD, then=F("effective_price")),
                                 When(~Q(payment_type=cls.COD), then=0))
            tdcs_condition = Case(When(payment_type=cls.COD, then=F("fees")),
                                  When(~Q(payment_type=cls.COD), then=0))
            tpf_condition = Case(When(payment_type=cls.PREPAID, then=F("fees")),
                                 When(~Q(payment_type=cls.PREPAID), then=0))
            queryset = queryset.values("doctor", "hospital").annotate(total_cash_payment=Sum(tcp_condition),
                                                                      total_cash_share=Sum(tdcs_condition),
                                                                      total_online_payout=Sum(tpf_condition))

        return queryset

    @classmethod
    def get_billing_appointment(cls, user, req_data):
        month = req_data.get("month")
        year = req_data.get("year")
        payment_type = req_data.get("payment_type")
        out_level = req_data.get("level")
        admin_id = req_data.get("admin_id")

        start_date_time, end_date_time = get_start_end_datetime(month, year)
        query_filter = dict()
        opd_filter_query = dict()
        query_filter['user'] = user
        query_filter['write_permission'] = True
        query_filter['permission_type'] = auth_model.GenericAdmin.BILLINNG
        if out_level == Outstanding.HOSPITAL_NETWORK_LEVEL:
            query_filter["hospital_network"] = admin_id
        elif out_level == Outstanding.HOSPITAL_LEVEL:
            query_filter["hospital"] = admin_id
            if req_data.get("doctor_hospital"):
                opd_filter_query["doctor"] = req_data.get("doctor_hospital")
        elif out_level == Outstanding.DOCTOR_LEVEL:
            query_filter["doctor"] = admin_id
            if req_data.get("doctor_hospital"):
                opd_filter_query["hospital"] = req_data.get("doctor_hospital")

        permission = auth_model.GenericAdmin.objects.filter(**query_filter).exists()

        if payment_type in [cls.COD, cls.PREPAID]:
            payment_type = [cls.COD, cls.PREPAID]
        elif payment_type in [cls.INSURANCE]:
            payment_type = [cls.INSURANCE]

        queryset = None
        # if permission:
        out_obj = Outstanding.objects.filter(outstanding_level=out_level, net_hos_doc_id=admin_id,
                                             outstanding_month=month, outstanding_year=year).first()
        queryset = (OpdAppointment.objects.filter(status=OpdAppointment.COMPLETED,
                                                  time_slot_start__gte=start_date_time,
                                                  time_slot_start__lte=end_date_time,
                                                  payment_type__in=payment_type,
                                                  outstanding=out_obj).filter(**opd_filter_query))

        return queryset

    def get_auto_cancel_delay(self, app_obj):
        delay = settings.AUTO_CANCEL_OPD_DELAY * 60
        to_zone = tz.gettz(settings.TIME_ZONE)
        app_updated_time = app_obj.updated_at.astimezone(to_zone)
        morning_time = "09:00:00"  # In IST
        evening_time = "20:00:00"  # In IST
        present_day_end = custom_form_datetime(evening_time, to_zone)
        next_day_start = custom_form_datetime(morning_time, to_zone, diff_days=1)
        time_diff = next_day_start - app_updated_time

        if present_day_end - timedelta(minutes=settings.AUTO_CANCEL_OPD_DELAY) < app_updated_time < next_day_start:
            return time_diff.seconds
        else:
            return delay

    def get_procedures(self):
        procedures = []
        if self.payment_type == OpdAppointment.COD:
            procedures.insert(0, {"name": "Consultation", "mrp": self.mrp,
                                  "deal_price": self.mrp,
                                  "agreed_price": self.mrp,
                                  "discount": 0})
        elif self.payment_type == OpdAppointment.INSURANCE:
            procedures.insert(0, {"name": "Consultation", "mrp": self.mrp,
                                  "deal_price": "0.00",
                                  "agreed_price": self.mrp,
                                  "discount": self.mrp})
        else:
            procedure_mappings = self.procedure_mappings.select_related("procedure").all()
            procedures = [{"name": mapping.procedure.name, "mrp": mapping.mrp, "deal_price": mapping.deal_price,
                           "agreed_price": mapping.agreed_price,
                           "discount": mapping.mrp - mapping.deal_price} for mapping in procedure_mappings]
            procedures_total = {"mrp": sum([procedure["mrp"] for procedure in procedures]),
                                "deal_price": sum([procedure["deal_price"] for procedure in procedures]),
                                "agreed_price": sum([procedure["agreed_price"] for procedure in procedures]),
                                "discount": sum([procedure["discount"] for procedure in procedures])}
            doctor_prices = {"mrp": self.mrp - procedures_total["mrp"],
                             "deal_price": self.deal_price - procedures_total["deal_price"],
                             "agreed_price": self.fees - procedures_total["agreed_price"]}
            doctor_prices["discount"] = doctor_prices["mrp"] - doctor_prices["deal_price"]
            procedures.insert(0, {"name": "Consultation", "mrp": doctor_prices["mrp"],
                                  "deal_price": doctor_prices["deal_price"],
                                  "agreed_price": doctor_prices["agreed_price"],
                                  "discount": doctor_prices["discount"]})
        procedures = [
            {"name": str(procedure["name"]), "mrp": str(procedure["mrp"]),
             "deal_price": str(procedure["deal_price"]),
             "discount": str(procedure["discount"]), "agreed_price": str(procedure["agreed_price"])} for procedure in procedures]

        return procedures

    @property
    def get_billed_to(self):
        doctor_clinic = self.doctor.doctor_clinics.filter(hospital=self.hospital).first()
        if self.hospital.network and self.hospital.network.is_billing_enabled:
            return self.hospital.network
        if self.hospital.is_billing_enabled:
            return self.hospital
        if doctor_clinic and doctor_clinic.merchant.first():
            return doctor_clinic
        return self.doctor

    @property
    def get_merchant(self):
        billed_to = self.get_billed_to
        if billed_to:
            merchant = billed_to.merchant.first()
            if merchant:
                return merchant.merchant
        return None

    @classmethod
    def get_price_details(cls, data):

        procedures = data.get('procedure_ids', [])
        selected_hospital = data.get('hospital')
        doctor = data.get('doctor')
        time_slot_start = form_time_slot(data.get("start_date"), data.get("start_time"))

        doctor_clinic_timing = DoctorClinicTiming.objects.filter(
            doctor_clinic__doctor=data.get('doctor'),
            doctor_clinic__hospital=data.get('hospital'),
            doctor_clinic__doctor__is_live=True, doctor_clinic__hospital__is_live=True,
            day=time_slot_start.weekday(), start__lte=data.get("start_time"),
            end__gte=data.get("start_time")).first()

        effective_price = 0
        if not procedures:
            if data.get("payment_type") == cls.INSURANCE:
                effective_price = doctor_clinic_timing.deal_price
                coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []
            elif data.get("payment_type") in [cls.PREPAID]:
                coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(data,
                                                                                           doctor_clinic_timing.deal_price)
                if coupon_discount >= doctor_clinic_timing.deal_price:
                    effective_price = 0
                else:
                    effective_price = doctor_clinic_timing.deal_price - coupon_discount
            deal_price = doctor_clinic_timing.deal_price
            mrp = doctor_clinic_timing.mrp
            fees = doctor_clinic_timing.fees
        else:
            total_deal_price, total_agreed_price, total_mrp = cls.get_procedure_prices(procedures, doctor,
                                                                                        selected_hospital,
                                                                                        doctor_clinic_timing)
            if data.get("payment_type") == cls.INSURANCE:
                effective_price = total_deal_price
            elif data.get("payment_type") in [cls.PREPAID]:
                coupon_discount, coupon_cashback, coupon_list, random_coupon_list = Coupon.get_total_deduction(data, total_deal_price)
                if coupon_discount >= total_deal_price:
                    effective_price = 0
                else:
                    effective_price = total_deal_price - coupon_discount

            deal_price = total_deal_price
            mrp = total_mrp
            fees = total_agreed_price

        if data.get("payment_type") == cls.COD:
            effective_price = 0
            coupon_discount, coupon_cashback, coupon_list, random_coupon_list = 0, 0, [], []

        return {
            "deal_price": deal_price,
            "mrp": mrp,
            "fees": fees,
            "effective_price": effective_price,
            "coupon_discount": coupon_discount,
            "coupon_cashback": coupon_cashback,
            "coupon_list": coupon_list,
            "consultation" : {
                "deal_price": doctor_clinic_timing.deal_price,
                "mrp": doctor_clinic_timing.mrp
            },
            "coupon_data" : { "random_coupon_list" : random_coupon_list }
        }

    @classmethod
    def create_fulfillment_data(cls, user, data, price_data):
        from ondoc.insurance.models import UserInsurance
        procedures = data.get('procedure_ids', [])
        selected_hospital = data.get('hospital')
        doctor = data.get('doctor')
        time_slot_start = form_time_slot(data.get("start_date"), data.get("start_time"))
        profile_model = data.get("profile")
        profile_detail = {
            "name": profile_model.name,
            "gender": profile_model.gender,
            "dob": str(profile_model.dob)
        }

        extra_details = []
        doctor_clinic = doctor.doctor_clinics.filter(hospital=selected_hospital).first()
        doctor_clinic_procedures = doctor_clinic.procedures_from_doctor_clinic.filter(procedure__in=procedures).order_by(
            'procedure_id')
        for doctor_clinic_procedure in doctor_clinic_procedures:
            temp_extra = {'procedure_id': doctor_clinic_procedure.procedure.id,
                          'procedure_name': doctor_clinic_procedure.procedure.name,
                          'deal_price': doctor_clinic_procedure.deal_price,
                          'agreed_price': doctor_clinic_procedure.agreed_price,
                          'mrp': doctor_clinic_procedure.mrp}
            extra_details.append(temp_extra)

        payment_type = data.get("payment_type")
        effective_price = price_data.get("effective_price")
        cart_data = data.get('cart_item').data
        # is_appointment_insured = cart_data.get('is_appointment_insured', None)
        # insurance_id = cart_data.get('insurance_id', None)

        is_appointment_insured = False
        insurance_id = None
        user_insurance = UserInsurance.objects.filter(user=user).last()
        if user_insurance and user_insurance.is_valid():
            is_appointment_insured, insurance_id, insurance_message = user_insurance.validate_doctor_insurance(data, user_insurance)

        if is_appointment_insured and cart_data.get('is_appointment_insured', None):
            payment_type = OpdAppointment.INSURANCE
            effective_price = 0.0
        else:
            insurance_id = None

        return {
            "doctor": data.get("doctor"),
            "hospital": data.get("hospital"),
            "profile": data.get("profile"),
            "profile_detail": profile_detail,
            "user": user,
            "booked_by": user,
            "fees": price_data.get("fees"),
            "deal_price": price_data.get("deal_price"),
            "effective_price": effective_price,
            "mrp": price_data.get("mrp"),
            "extra_details": extra_details,
            "time_slot_start": time_slot_start,
            "payment_type": payment_type,
            "coupon": price_data.get("coupon_list"),
            "discount": int(price_data.get("coupon_discount")),
            "cashback": int(price_data.get("coupon_cashback")),
            "is_appointment_insured": is_appointment_insured,
            "insurance": insurance_id,
            "coupon_data": price_data.get("coupon_data")
        }

    @staticmethod
    def get_procedure_prices(procedures, doctor, selected_hospital, dct):
        doctor_clinic = doctor.doctor_clinics.filter(hospital=selected_hospital).first()
        doctor_clinic_procedures = doctor_clinic.procedures_from_doctor_clinic.filter(procedure__in=procedures).order_by(
            'procedure_id')
        total_deal_price, total_agreed_price, total_mrp = 0, 0, 0
        for doctor_clinic_procedure in doctor_clinic_procedures:
            total_agreed_price += doctor_clinic_procedure.agreed_price
            total_deal_price += doctor_clinic_procedure.deal_price
            total_mrp += doctor_clinic_procedure.mrp
        return total_deal_price + dct.deal_price, total_agreed_price + dct.fees, total_mrp + dct.mrp

    class Meta:
        db_table = "opd_appointment"

    def get_prescriptions(self, request):
        prescriptions = []
        for pres in self.prescriptions.all():
            files = []
            for file in pres.prescription_file.all():
                url = request.build_absolute_uri(file.name.url) if file.name else None
                files.append(url)
            prescription_dict = {
                                 "updated_at": pres.updated_at,
                                 "details": pres.prescription_details,
                                 "files": files
                                }
            prescriptions.append(prescription_dict)
        return prescriptions

    @classmethod
    def can_book_for_free(cls, request, validated_data, cart_item=None):
        from ondoc.cart.models import Cart

        price_data = cls.get_price_details(validated_data)
        if price_data["deal_price"] > 0:
            return True

        user = request.user
        free_appointment_count = cls.objects.filter(user=user, deal_price=0).exclude(status__in=[cls.COMPLETED,cls.CANCELLED]).count()
        free_cart_count = Cart.get_free_opd_item_count(request, cart_item)

        return (free_appointment_count + free_cart_count) < cls.MAX_FREE_BOOKINGS_ALLOWED

    def trigger_created_event(self, visitor_info):
        from ondoc.tracking.models import TrackingEvent
        from ondoc.tracking.mongo_models import TrackingEvent as MongoTrackingEvent
        try:
            with transaction.atomic():
                event_data = TrackingEvent.build_event_data(self.user, TrackingEvent.DoctorAppointmentBooked, appointmentId=self.id, visitor_info=visitor_info)
                if event_data and visitor_info:
                    TrackingEvent.save_event(event_name=event_data.get('event'), data=event_data, visit_id=visitor_info.get('visit_id'),
                                             user=self.user, triggered_at=datetime.datetime.utcnow())
                    if settings.MONGO_STORE:
                        MongoTrackingEvent.save_event(event_name=event_data.get('event'), data=event_data,
                                                 visit_id=visitor_info.get('visit_id'),
                                                 visitor_id=visitor_info.get('visitor_id'),
                                                 user=self.user, triggered_at=datetime.datetime.utcnow())
        except Exception as e:
            logger.error("Could not save triggered event - " + str(e))

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
        is_home_pickup = 0
        report_uploaded = 0
        report_sent = None
        home_pickup_address = None
        appointment_type = ''
        location = ''
        booking_url = '%s/admin/doctor/opdappointment/%s/change' % (settings.ADMIN_BASE_URL, self.id)
        kyc = 1 if DoctorDocument.objects.filter(doctor=self.doctor, document_type__in=[DoctorDocument.CHEQUE, DoctorDocument.PAN]).distinct('document_type').count() == 2 else 0

        if self.hospital.location:
            location = 'https://www.google.com/maps/search/?api=1&query=%f,%f' % (self.hospital.location.y, self.hospital.location.x)

        patient_address = ""
        if hasattr(self, 'address') and self.address:
            patient_address = resolve_address(self.address)

        service_name = ""
        profile_email = ''
        if self.profile:
            profile_email = self.profile.email

        mask_number_instance = self.mask_number.filter(is_deleted=False, is_mask_number=True).first()
        mask_number = ''
        if mask_number_instance:
            mask_number = mask_number_instance.mask_number

        provider_booking_id = ''
        merchant_code = ''
        is_ipd_hospital = '1' if self.hospital and self.hospital.has_ipd_doctors() else '0'
        location_verified = self.hospital.is_location_verified
        provider_id = self.doctor.id
        merchant = self.doctor.merchant.all().last()
        if merchant:
            merchant_code = merchant.id

        order_id = order.id if order else None
        dob_value = ''
        try:
            dob_value = datetime.datetime.strptime(self.profile_detail.get('dob'), "%Y-%m-%d").strftime("%d-%m-%Y") \
                if self.profile_detail.get('dob', None) else ''
        except Exception as e:
            pass

        merchant_payout = self.merchant_payout_data()
        accepted_history = self.appointment_accepted_history()
        user_insurance = self.insurance
        mobile_list = self.get_matrix_spoc_data()
        refund_data = self.refund_details_data()

        appointment_details = {
            'IPDHospital': is_ipd_hospital,
            'IsInsured': 'yes' if user_insurance else 'no',
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
            'BookingType': 'D',
            'AppointmentType': appointment_type,
            'IsHomePickUp': is_home_pickup,
            'HomePickupAddress': home_pickup_address,
            'PatientName': self.profile_detail.get("name", ''),
            'PatientAddress': patient_address,
            'ProviderName': getattr(self, 'doctor').name + " - " + self.hospital.name,
            'ServiceName': service_name,
            'InsuranceCover': 0,
            'MobileList': mobile_list,
            'BookingUrl': booking_url,
            'Fees': float(self.fees),
            'EffectivePrice': float(self.effective_price),
            'MRP': float(self.mrp),
            'DealPrice': float(self.deal_price),
            'DOB': dob_value,
            'ProviderAddress': self.hospital.get_hos_address(),
            'ProviderID': provider_id,
            'ProviderBookingID': provider_booking_id,
            'MerchantCode': merchant_code,
            'ProviderPaymentStatus': merchant_payout['provider_payment_status'],
            'PaymentURN': merchant_payout['payment_URN'],
            'Amount': float(merchant_payout['amount']) if merchant_payout['amount'] else None,
            'SettlementDate': merchant_payout['settlement_date'],
            'LocationVerified': location_verified,
            'ReportUploaded': report_uploaded,
            'Reportsent': report_sent,
            'AcceptedBy': accepted_history['source'],
            'AcceptedPhone': accepted_history['accepted_phone'],
            "CustomerStatus": refund_data['customer_status'],
            "RefundPaymentMode": float(refund_data['original_payment_mode_refund']) if refund_data['original_payment_mode_refund'] else None,
            "RefundToWallet": float(refund_data['promotional_wallet_refund']) if refund_data['promotional_wallet_refund'] else None,
            "RefundInitiationDate": int(refund_data['refund_initiated_at']) if refund_data['refund_initiated_at'] else None,
            "RefundURN": refund_data['refund_urn']
        }
        return appointment_details

    def get_matrix_spoc_data(self):
        mobile_list = list()
        # User mobile number
        mobile_list.append({'MobileNo': self.user.phone_number, 'Name': self.profile.name, 'Type': 1})
        # if self.insurance_id:
        #     auto_ivr_enabled = False
        # else:
        #     auto_ivr_enabled = self.hospital.is_auto_ivr_enabled()

        auto_ivr_enabled = self.hospital.is_auto_ivr_enabled()
        # SPOC details
        for spoc_obj in self.hospital.spoc_details.all():
            number = ''
            if spoc_obj.number:
                number = str(spoc_obj.number)
            if spoc_obj.std_code:
                number = str(spoc_obj.std_code) + number
            if number:
                number = int(number)

            # spoc_type = dict(spoc_obj.CONTACT_TYPE_CHOICES)[spoc_obj.contact_type]
            if number:
                spoc_name = spoc_obj.name
                mobile_list.append({'MobileNo': number,
                                    'Name': spoc_name,
                                    'DesignationID': spoc_obj.contact_type,
                                    'AutoIVREnable': str(auto_ivr_enabled).lower(),
                                    'Type': 2})

        # Doctor mobile numbers
        doctor_mobiles = [doctor_mobile.number for doctor_mobile in self.doctor.mobiles.all()]
        doctor_mobiles = [{'MobileNo': number, 'Name': self.doctor.name, 'Type': 2} for number in doctor_mobiles]
        mobile_list.extend(doctor_mobiles)

        return mobile_list

    @classmethod
    def get_insured_completed_appointment(cls, insurance_obj):
        count = cls.objects.filter(user=insurance_obj.user, insurance=insurance_obj, status=cls.COMPLETED).count()
        return count

    @classmethod
    def get_insured_active_appointment(cls, insurance_obj):
        appointments = cls.objects.filter(~Q(status=cls.COMPLETED), ~Q(status=cls.CANCELLED), user=insurance_obj.user,
                                          insurance=insurance_obj)
        return appointments

    @classmethod
    def get_insurance_usage(cls, insurance_obj, date=None):
        appointments = cls.objects.filter(user=insurance_obj.user, insurance=insurance_obj).exclude(status=cls.CANCELLED)
        if date:
            appointments = appointments.filter(created_at__date=date)

        count = appointments.count()
        data = appointments.aggregate(sum_amount=Sum('fees'))
        sum = data.get('sum_amount', 0)
        sum = sum if sum else 0
        return {'count': count, 'sum': sum}

    def convert_ipd_lead_data(self):
        result = {}
        result['hospital'] = self.hospital
        result['doctor'] = self.doctor
        result['user'] = self.user
        result['payment_amount'] = self.deal_price  # To be confirmed
        if self.user:
            result['name'] = self.user.full_name
            result['phone_number'] = self.user.phone_number
            result['email'] = self.user.email
            default_user_profile = self.user.get_default_profile()
            if default_user_profile:
                result['gender'] = default_user_profile.gender
                result['dob'] = default_user_profile.dob
        result['data'] = {'opd_appointment_id': self.id}
        return result

    @classmethod
    def is_followup_appointment(cls, current_appointment):
        if not current_appointment:
            return False
        doctor = current_appointment.doctor
        hospital = current_appointment.hospital
        profile = current_appointment.profile
        last_completed_appointment = cls.objects.filter(doctor=doctor, profile=profile, hospital=hospital,
                                                        status=cls.COMPLETED).order_by('-id').first()
        if not last_completed_appointment:
            return False
        last_appointment_date = last_completed_appointment.time_slot_start
        dc_obj = DoctorClinic.objects.filter(doctor=doctor, hospital=hospital, enabled=True).first()
        if not dc_obj:
            return False
        followup_duration = dc_obj.followup_duration
        if not followup_duration:
            followup_duration = settings.DEFAULT_FOLLOWUP_DURATION
        days_diff = current_appointment.date() - last_appointment_date.date()
        if days_diff.days < followup_duration:
            return True
        else:
            return False

    def get_master_order_id_and_discount(self):
        result = None, None
        order_obj = Order.objects.filter(reference_id=self.id).first()
        if order_obj:
            try:
                patent_id = order_obj.parent_id
                discount = ((Decimal(order_obj.action_data.get('mrp')) - Decimal(order_obj.action_data.get(
                    'deal_price'))) / Decimal(order_obj.action_data.get('mrp'))) * 100
                discount = str(round(discount, 2))
                result = patent_id, discount
            except Exception as e:
                result = None, None
        return result

    def get_cod_to_prepaid_url_and_discount(self, token):
        result = None, None
        order_id, discount = self.get_master_order_id_and_discount()
        if order_id:
            url = settings.BASE_URL + '/order/paymentSummary?order_id={}&token={}'.format(order_id, token)
            result = url, discount
        return result

    def generate_credit_letter(self):
        old_credit_letters = self.get_document_objects(Documents.CREDIT_LETTER)
        old_credit_letters.update(is_valid=False)
        credit_letter = self.documents.create(document_type=Documents.CREDIT_LETTER)
        context = {
            "instance": self
        }
        html_body = None
        if self.is_medanta_hospital_booking():
            html_body = render_to_string("email/documents/credit_letter_medanta.html", context=context)
        elif self.is_artemis_hospital_booking():
            html_body = render_to_string("email/documents/credit_letter_artemis.html", context=context)
        if not html_body:
            logger.error("Got error while getting hospital for opd credit letter.")
            return None
        filename = "credit_letter_{}.pdf".format(self.id)
        file = html_to_pdf(html_body, filename)
        if not file:
            logger.error("Got error while creating pdf for opd credit letter.")
            return None
        credit_letter.file = file
        credit_letter.save()
        return credit_letter

    def is_medanta_hospital_booking(self):
        medanta_hospital = Hospital.objects.filter(id=settings.MEDANTA_HOSPITAL_ID).first()
        return self.hospital == medanta_hospital if medanta_hospital else False

    def is_artemis_hospital_booking(self):
        artemis_hospital = Hospital.objects.filter(id=settings.ARTEMIS_HOSPITAL_ID).first()
        return self.hospital == artemis_hospital if artemis_hospital else False


class OpdAppointmentProcedureMapping(models.Model):
    opd_appointment = models.ForeignKey(OpdAppointment, on_delete=models.CASCADE, related_name='procedure_mappings')
    procedure = models.ForeignKey('procedure.Procedure', on_delete=models.CASCADE, related_name='opd_appointment_mappings')
    mrp = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    agreed_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deal_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return '{}>{}'.format(self.opd_appointment, self.procedure)

    class Meta:
        db_table = 'opd_appointment_procedure_mapping'


class DoctorLeave(auth_model.TimeStampedModel):
    INTERVAL_MAPPING = {
        ("00:00:00", "14:00:00"): 'morning',
        ("14:00:00", "23:59:59"): 'evening',
        ("00:00:00", "23:59:59"): 'all',
    }
    doctor = models.ForeignKey(Doctor, related_name="leaves", on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=True)
    start_time = models.TimeField(blank=True, null=True)
    end_time = models.TimeField(blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.doctor.name + "(" + str(self.start_time) + "," + str(self.end_date) + str(self.start_date)

    def start_time_in_float(self):
        start_time = self.start_time
        start_time = round(float(start_time.hour) + (float(start_time.minute) * 1 / 60), 2)
        return start_time

    def end_time_in_float(self):
        end_time = self.end_time
        end_time = round(float(end_time.hour) + (float(end_time.minute) * 1 / 60), 2)
        return end_time

    class Meta:
        db_table = "doctor_leave"

    @property
    def interval(self):
        return self.INTERVAL_MAPPING.get((str(self.start_time), str(self.end_time)))


class Prescription(auth_model.TimeStampedModel):
    appointment = models.ForeignKey(OpdAppointment, related_name='prescriptions', on_delete=models.CASCADE)
    prescription_details = models.TextField(max_length=300, blank=True, null=True)

    def __str__(self):
        return "{}-{}".format(self.id, self.appointment.id)

    class Meta:
        db_table = "prescription"


class PrescriptionFile(auth_model.TimeStampedModel, auth_model.Document):
    prescription = models.ForeignKey(Prescription, related_name='prescription_file', on_delete=models.CASCADE)
    name = models.FileField(upload_to='prescriptions', blank=False, null=False)

    def __str__(self):
        return "{}-{}".format(self.id, self.prescription.id)

    def send_notification(self, database_instance):
        appointment = self.prescription.appointment
        if not appointment.user:
            return
        if not database_instance:
            notification_models.NotificationAction.trigger(
                instance=appointment,
                user=appointment.user,
                notification_type=notification_models.NotificationAction.PRESCRIPTION_UPLOADED,
            )

    def send_notification_refactored(self, database_instance):
        from ondoc.communications.models import OpdNotification
        appointment = self.prescription.appointment
        if not appointment.user:
            return
        if not database_instance:
            opd_notification = OpdNotification(appointment, NotificationAction.PRESCRIPTION_UPLOADED)
            opd_notification.send()

    def save(self, *args, **kwargs):
        database_instance = PrescriptionFile.objects.filter(pk=self.id).first()
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.send_notification_refactored(database_instance))
        # self.send_notification(database_instance)

    class Meta:
        db_table = "prescription_file"


class MedicalCondition(auth_model.TimeStampedModel, SearchKey):
    name = models.CharField(max_length=100, verbose_name="Name")
    specialization = models.ManyToManyField(
        'PracticeSpecialization',
        through='MedicalConditionSpecialization',
        through_fields=('medical_condition', 'specialization'),
    )

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = "medical_condition"


class MedicalConditionSpecialization(auth_model.TimeStampedModel):
    medical_condition = models.ForeignKey(MedicalCondition, on_delete=models.CASCADE)
    specialization = models.ForeignKey('PracticeSpecialization', on_delete=models.CASCADE, null=True,
                                       blank=True)

    def __str__(self):
        return self.medical_condition.name + " " + self.specialization.name

    class Meta:
        db_table = "medical_condition_specialization"


class DoctorSearchResult(auth_model.TimeStampedModel):
    results = JSONField()
    result_count = models.PositiveIntegerField()

    class Meta:
        db_table = "doctor_search_result"


class HealthTip(auth_model.TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name="Name")
    text = models.CharField(max_length=1000)

    class Meta:
        db_table = "health_tip"


class CommonMedicalCondition(auth_model.TimeStampedModel):
    condition = models.OneToOneField(MedicalCondition, related_name="common_condition", on_delete=models.CASCADE)
    priority = models.PositiveIntegerField(default=0)
    def __str__(self):
        return "{}".format(self.condition)

    class Meta:
        db_table = "common_medical_condition"


class CommonSpecialization(auth_model.TimeStampedModel):
    specialization = models.OneToOneField('PracticeSpecialization', related_name="common_specialization", on_delete=models.CASCADE,
                                          null=True, blank=True)
    icon = models.ImageField(upload_to='doctor/common_specialization_icons', null=True)
    priority = models.PositiveIntegerField(default=0)

    def __str__(self):
        return "{}".format(self.specialization)

    class Meta:
        db_table = "common_specializations"

    @classmethod
    def get_specializations(cls, count):
        specializations = cls.objects.select_related('specialization').all().order_by("-priority")[:count]
        return specializations


class DoctorMapping(auth_model.TimeStampedModel):

    doctor = models.ForeignKey(Doctor, related_name='doctor_mapping', on_delete=models.CASCADE)
    profile_to_be_shown = models.ForeignKey(Doctor, related_name='profile_to_be_shown_mapping', on_delete=models.CASCADE)

    class Meta:
        db_table = "doctor_mapping"


class CompetitorInfo(auth_model.TimeStampedModel):
    PRACTO = 1
    LYBRATE = 2
    NAME_TYPE_CHOICES = (("", "Select"), (PRACTO, 'Practo'), (LYBRATE, "Lybrate"),)
    name = models.PositiveSmallIntegerField(choices=NAME_TYPE_CHOICES, default=PRACTO)

    doctor = models.ForeignKey(Doctor, related_name="competitor_doctor", on_delete=models.CASCADE, null=True,
                               blank=True)
    hospital = models.ForeignKey(Hospital, related_name="competitor_hospital", on_delete=models.CASCADE, null=True,
                                 blank=True)
    hospital_name = models.CharField(max_length=200)
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    url = models.URLField(null=True)
    processed_url = models.URLField(null=True)

    #
    # url = url.replace("http://", "")

    class Meta:
        db_table = "competitor_info"
        # unique_together = ('name', 'hospital_name', 'doctor')

    def save(self, *args, **kwargs):
        url = self.url
        if url:
            if ('//') in url:
                url = url.split('//')[1]
            if ('?') in url:
                url = url.split('?')[0]
            self.processed_url = url

        super().save(*args, **kwargs)


class SpecializationDepartment(auth_model.TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        db_table = 'specialization_department'

    def __str__(self):
        return "{}".format(self.name)


class SpecializationField(auth_model.TimeStampedModel):
    name = models.CharField(max_length=200, unique=True)

    class Meta:
        db_table = 'specialization_field'

    def __str__(self):
        return "{}".format(self.name)


class SpecializationDepartmentMapping(auth_model.TimeStampedModel):
    specialization = models.ForeignKey('PracticeSpecialization', on_delete=models.DO_NOTHING)
    department = models.ForeignKey(SpecializationDepartment, on_delete=models.DO_NOTHING)

    class Meta:
        db_table = 'specialization_department_mapping'


class PracticeSpecialization(auth_model.TimeStampedModel, SearchKey):
    name = models.CharField(max_length=200, unique=True)
    department = models.ManyToManyField(SpecializationDepartment, through=SpecializationDepartmentMapping,
                                        through_fields=('specialization', 'department'),
                                        related_name='departments')
    specialization_field = models.ForeignKey(SpecializationField, on_delete=models.DO_NOTHING)
    general_specialization_ids = ArrayField(models.IntegerField(blank=True, null=True), size=100,
                                            null=True, blank=True)
    synonyms = models.CharField(max_length=4000, null=True, blank=True)
    doctor_count = models.PositiveIntegerField(default=0, null=True)
    is_insurance_enabled = models.BooleanField(default=True)

    class Meta:
        db_table = 'practice_specialization'

    def __str__(self):
        return "{}".format(self.name)


class PracticeSpecializationContent(auth_model.TimeStampedModel):
    specialization = models.ForeignKey(PracticeSpecialization, on_delete=models.CASCADE)
    content = models.TextField(blank=True)

    class Meta:
        db_table = 'practice_specialization_content'


class DoctorPracticeSpecialization(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, related_name="doctorpracticespecializations", on_delete=models.CASCADE)
    specialization = models.ForeignKey(PracticeSpecialization, on_delete=models.CASCADE, blank=False, null=False, related_name='specialization')

    # def __str__(self):
    #     return "{}-{}".format(self.doctor.name, self.specialization.name)

    class Meta:
        db_table = "doctor_practice_specialization"
        unique_together = ("doctor", "specialization")

class CompetitorMonthlyVisit(models.Model):
    NAME_TYPE_CHOICES = CompetitorInfo.NAME_TYPE_CHOICES
    doctor = models.ForeignKey(Doctor, related_name="competitor_doctor_hits", on_delete=models.CASCADE)
    name = models.PositiveSmallIntegerField(choices=NAME_TYPE_CHOICES)
    monthly_visit = models.BigIntegerField(verbose_name='Monthly Visits through Competitor')

    class Meta:
        db_table = "competitor_monthly_visits"
        unique_together = ('doctor', 'name')


class SourceIdentifier(auth_model.TimeStampedModel):
    DOCTOR = 1
    HOSPITAL = 5
    type_choice = ((DOCTOR, "Doctor"), (HOSPITAL, "Hospital"))
    reference_id = models.IntegerField()
    unique_identifier = models.CharField(max_length=1000)
    type = models.PositiveSmallIntegerField(choices=type_choice, blank=True, null=True)

    class Meta:
        db_table = "source_identifier"
        unique_together = ('unique_identifier', )


class GoogleDetailing(auth_model.TimeStampedModel):

    identifier = models.CharField(max_length=255, null=True, blank=False)
    hospital_id = models.PositiveIntegerField(null=True, blank=True)

    name = models.CharField(max_length=500, null=True, blank=False)
    clinic_hospital_name = models.CharField(max_length=128, null=True, blank=False)
    address = models.TextField(null=True, blank=False)
    doctor_clinic_address = models.TextField(null=True, blank=False)
    clinic_address = models.TextField(null=True, blank=False)

    doctor_place_search = models.TextField(null=True)
    clinic_place_search = models.TextField(null=True)

    doctor_detail = models.TextField(null=True)
    clinic_detail = models.TextField(null=True)

    doctor_number = models.CharField(max_length=255, null=True, blank=True)
    clinic_number = models.CharField(max_length=255, null=True, blank=True)

    doctor_international_number = models.CharField(max_length=255, null=True, blank=True)
    clinic_international_number = models.CharField(max_length=255, null=True, blank=True)

    doctor_formatted_address = models.TextField(null=True)
    clinic_formatted_address = models.TextField(null=True)

    doctor_name = models.CharField(max_length=1024, null=True, blank=True)
    clinic_name = models.CharField(max_length=1024, null=True, blank=True)

    class Meta:
        db_table = 'google_api_details'

class DoctorPopularity(models.Model):
    KEY = 1
    NON_KEY = 2
    POPULARITY_CHOICES = ((KEY, 'Key'), (NON_KEY, 'Non-Key'))
    unique_identifier = models.CharField(max_length=500)
    popularity = models.PositiveSmallIntegerField(choices=POPULARITY_CHOICES)
    popularity_score = models.DecimalField(max_digits=3, decimal_places=1, validators=[MaxValueValidator(10.0)])
    rating_percent = models.PositiveSmallIntegerField(validators=[MaxValueValidator(100)])
    votes_count = models.PositiveIntegerField()
    reviews_count = models.PositiveIntegerField()

    class Meta:
        db_table = "doctor_popularity"
        unique_together = ('unique_identifier',)

    def __str__(self):
        return self.unique_identifier


class VisitReason(auth_model.TimeStampedModel, SearchKey):
    name = models.TextField()
    practice_specializations = models.ManyToManyField(PracticeSpecialization, through='VisitReasonMapping',
                                                      through_fields=('visit_reason', 'practice_specialization'),
                                                      related_name='visiting_reasons')

    class Meta:
        db_table = "visit_reason"
        unique_together = (('name',),)

    def __str__(self):
        return '{}'.format(self.name)


class VisitReasonMapping(models.Model):
    visit_reason = models.ForeignKey(VisitReason, on_delete=models.CASCADE, related_name='related_practice_specializations')
    practice_specialization = models.ForeignKey(PracticeSpecialization, on_delete=models.CASCADE, related_name='related_visit_reasons')
    is_primary = models.BooleanField(default=False)

    class Meta:
        db_table = "visit_reason_mapping"
        unique_together = (('visit_reason', 'practice_specialization'),)

    def __str__(self):
        return '{}({})'.format(self.visit_reason.name, self.practice_specialization.name)


class CancellationReason(auth_model.TimeStampedModel):
    TYPE_CHOICES = [("", "Both")]
    TYPE_CHOICES.extend(Order.PRODUCT_IDS)
    name = models.CharField(max_length=200)
    type = models.PositiveSmallIntegerField(default=None, null=True, blank=True, choices=TYPE_CHOICES)
    visible_on_front_end = models.BooleanField(default=True)
    visible_on_admin = models.BooleanField(default=True)
    is_comment_needed = models.BooleanField(default=False)

    class Meta:
        db_table = 'cancellation_reason'
        unique_together = (('name','type'),)

    def __str__(self):
        return self.name


class OfflinePatients(auth_model.TimeStampedModel):
    DOCPRIME = 1
    GOOGLE = 2
    JUSTDIAL = 3
    FRIENDS = 4
    OTHERS = 5
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    GENDER_CHOICES = [(MALE, "Male"), (FEMALE, "Female"), (OTHER, "Other")]
    REFERENCE_CHOICES = [(DOCPRIME, "Docprime"), (GOOGLE, "Google"), (JUSTDIAL, "JustDial"), (FRIENDS, "Friends"),
                         (OTHERS, "Others")]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=32, null=True, blank=True)
    encrypted_name = models.CharField(max_length=128, null=True, blank=True)
    sms_notification = models.BooleanField(default=False)
    gender = models.CharField(max_length=2, default=None, blank=True, null=True, choices=GENDER_CHOICES)
    dob = models.DateField(blank=True, null=True)
    calculated_dob = models.DateField(blank=True, null=True)
    referred_by = models.PositiveSmallIntegerField(choices=REFERENCE_CHOICES, null=True, blank=True)
    medical_history = models.CharField(max_length=256, null=True, blank=True)
    welcome_message = models.CharField(max_length=128, null=True, blank=True)
    display_welcome_message = models.BooleanField(default=False)
    doctor = models.ForeignKey(Doctor, related_name="patients_doc", on_delete=models.SET_NULL, null=True)
    hospital = models.ForeignKey(Hospital, related_name="patients_hos", on_delete=models.SET_NULL, null=True, blank=True)
    share_with_hospital = models.BooleanField(default=False)
    created_by = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True)
    error = models.BooleanField(default=False)
    error_message = models.CharField(max_length=256, blank=True, null=True)
    age = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name


    def __repr__(self):
        return self.name


    @staticmethod
    def welcome_message_sms(sms_obj):
        if sms_obj:
            try:
                default_text = '''Dear %s, you have been successfully added as a patient to %s. In case of any query, please reach out to the %s.''' \
                               % (sms_obj['name'], sms_obj['appointment'].hospital.name, sms_obj['appointment'].hospital.name)
                text = sms_obj['welcome_message'] if sms_obj['welcome_message'] else default_text
                notification_tasks.send_offline_appointment_message.apply_async(kwargs={'number': sms_obj['phone_number'], 'text': text, 'type': 'Welcome SMS'}, countdown=1)
            except Exception as e:
                logger.error("Failed to Push Offline Welcome Message SMS Task "+ str(e))

    class Meta:
        db_table = 'offline_patients'


class PatientMobile(auth_model.TimeStampedModel):
    patient = models.ForeignKey(OfflinePatients, related_name="patient_mobiles", on_delete=models.CASCADE)
    phone_number = models.BigIntegerField(blank=True, null=True,
                                          validators=[MaxValueValidator(9999999999), MinValueValidator(6000000000)])
    is_default = models.BooleanField(verbose_name='Default Number?', default=False)
    encrypted_number = models.CharField(max_length=64, null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.phone_number)

    class Meta:
        db_table = "patient_mobile"


class OfflineOPDAppointments(auth_model.TimeStampedModel):
    CREATED = 1
    BOOKED = 2
    RESCHEDULED_DOCTOR = 3
    NO_SHOW = 4
    ACCEPTED = 5
    CANCELLED = 6
    COMPLETED = 7
    REMINDER = 8
    SEND_MAP_LINK = 9

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    STATUS_CHOICES = [(CREATED, 'Created'), (BOOKED, 'Booked'),
                      (RESCHEDULED_DOCTOR, 'Rescheduled by Doctor'),
                      (NO_SHOW, 'No Show'),
                      (ACCEPTED, 'Accepted'), (CANCELLED, 'Cancelled'),
                      (COMPLETED, 'Completed')]
    doctor = models.ForeignKey(Doctor, related_name="offline_doctor_appointments", on_delete=models.SET_NULL, null=True)
    hospital = models.ForeignKey(Hospital, related_name="offline_hospital_appointments", on_delete=models.SET_NULL, null=True)
    user = models.ForeignKey(OfflinePatients, related_name="offline_patients_appointment", on_delete=models.SET_NULL, null=True)
    booked_by = models.ForeignKey(auth_model.User, related_name="offline_booked_appointements",
                                  on_delete=models.SET_NULL,
                                  null=True)
    status = models.PositiveSmallIntegerField(default=CREATED, choices=STATUS_CHOICES)
    time_slot_start = models.DateTimeField(blank=True, null=True)
    fees = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    error = models.BooleanField(default=False)
    error_message = models.CharField(max_length=256, blank=True, null=True)

    def __str__(self):
        return '{}-{}'.format(self.doctor, self.hospital)

    class Meta:
        db_table = "offline_opd_appointments"

    @staticmethod
    def appointment_add_sms(sms_obj):
        try:
            default_text = '''Dear %s, your appointment has been confirmed with %s at %s on %s.''' % (
                sms_obj['name'], sms_obj['appointment'].doctor.get_display_name(), sms_obj['appointment'].hospital.name,
                sms_obj['appointment'].time_slot_start.strftime("%B %d, %Y %I:%M %p"))
            notification_tasks.send_offline_appointment_message.apply_async(
                kwargs={'number': sms_obj['phone_number'], 'text': default_text, 'type': 'Appointment ADD'},
                countdown=1)
        except Exception as e:
            logger.error("Failed to Push Offline Appointment Add Message SMS Task " + str(e))

    @staticmethod
    def appointment_cancel_sms(sms_obj):
        try:
            cancel_time = aware_time_zone(sms_obj['old_appointment'].time_slot_start)
            default_text = "Dear %s, your appointment with %s at %s for %s has been cancelled. In case of any query, please reach out to the clinic." % (
                              sms_obj['name'], sms_obj['old_appointment'].doctor.get_display_name(), sms_obj['old_appointment'].hospital.name,
                              cancel_time.strftime("%B %d, %Y %I:%M %p"))
            notification_tasks.send_offline_appointment_message.apply_async(
                kwargs={'number': sms_obj['phone_number'], 'text': default_text, 'type': 'Appointment CANCEL'},
                countdown=1)
        except Exception as e:
            logger.error("Failed to Push Offline Appointment Cancel Message SMS Task " + str(e))

    @staticmethod
    def appointment_complete_sms(sms_obj):
        try:
            default_text = "Dear %s, your appointment with %s at %s is complete. In case of any query, please reach out to the %s." % \
                           (sms_obj['name'], sms_obj['appointment'].doctor.get_display_name(),
                            sms_obj['appointment'].hospital.name, sms_obj['appointment'].hospital.name)
            notification_tasks.send_offline_appointment_message.apply_async(
                kwargs={'number': sms_obj['phone_number'], 'text': default_text, 'type': 'Appointment COMPLETE'},
                countdown=1)
        except Exception as e:
            logger.error("Failed to Push Offline Appointment Cancel Message SMS Task " + str(e))

    @staticmethod
    def appointment_reschedule_sms(sms_obj):
        try:
            default_text = "Dear %s, your appointment with %s at %s has been rescheduled to %s. In case of any query, please reach out to the clinic." % (
                              sms_obj['name'], sms_obj['appointment'].doctor.get_display_name(), sms_obj['appointment'].hospital.name,
                              sms_obj['appointment'].time_slot_start.strftime("%B %d, %Y %I:%M %p"))
            notification_tasks.send_offline_appointment_message.apply_async(
                kwargs={'number': sms_obj['phone_number'], 'text': default_text, 'type': 'Appointment RESCHEDULE'},
                countdown=1)
        except Exception as e:
            logger.error("Failed to Push Offline Appointment Rescehdule Message SMS Task " + str(e))

    @staticmethod
    def after_commit_create_sms(sms_list):
        for sms_obj in sms_list:
            if sms_obj:
                if sms_obj.get('display_welcome_message'):
                    OfflinePatients.welcome_message_sms(sms_obj)
                OfflineOPDAppointments.appointment_add_sms(sms_obj)

    @staticmethod
    def after_commit_update_sms(sms_list):
        for sms_obj in sms_list:
            if sms_obj:
                if sms_obj.get('action_complete') and sms_obj['action_complete']:
                    OfflineOPDAppointments.appointment_complete_sms(sms_obj)
                elif sms_obj.get('action_cancel') and sms_obj['action_cancel']:
                    OfflineOPDAppointments.appointment_cancel_sms(sms_obj)
                    OfflineOPDAppointments.appointment_add_sms(sms_obj)
                elif sms_obj.get('action_reschedule') and sms_obj['action_reschedule']:
                    OfflineOPDAppointments.appointment_reschedule_sms(sms_obj)

    def get_prescriptions(self, request):

        files=[]
        resp = dict()
        for pres in self.offline_prescription.all():
            resp = {
                'updated_at': pres.updated_at,
                'details': pres.prescription_details
            }
            if pres.name and pres.name.url:
                files.append(request.build_absolute_uri(pres.name.url))
        resp['files']= files

        return resp



class SearchScore(auth_model.TimeStampedModel):
    doctor = models.ForeignKey(Doctor, on_delete=models.CASCADE)
    popularity_score = models.FloatField(default=None, null=True)
    years_of_experience_score = models.PositiveIntegerField(default=None, null=True)
    doctors_in_clinic_score = models.PositiveIntegerField(default=None, null=True)
    avg_ratings_score = models.PositiveIntegerField(default=None, null=True)
    ratings_count_score = models.PositiveIntegerField(default=None, null=True)
    final_score = models.FloatField(default=None, null=True)

    class Meta:
        db_table = 'search_score'


class UploadDoctorData(auth_model.TimeStampedModel):
    CREATED = 1
    IN_PROGRESS = 2
    SUCCESS = 3
    FAIL = 4
    STATUS_CHOICES = ("", "Select"), \
                     (CREATED, "Created"), \
                     (IN_PROGRESS, "Upload in progress"), \
                     (SUCCESS, "Upload successful"),\
                     (FAIL, "Upload Failed")
    # file, batch, status, error msg, source
    file = models.FileField()
    source = models.CharField(max_length=20)
    batch = models.CharField(max_length=20)
    status = models.PositiveSmallIntegerField(choices=STATUS_CHOICES, default=CREATED, editable=False)
    error_msg = JSONField(editable=False, null=True, blank=True)
    lines = models.PositiveIntegerField(null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="uploaded_doctor_data", null=True, editable=False,
                             on_delete=models.SET_NULL)

    def save(self, *args, **kwargs):
        retry = kwargs.pop('retry', True)
        from ondoc.notification.tasks import upload_doctor_data
        super().save(*args, **kwargs)
        if (self.status == self.CREATED or self.status == self.FAIL) and retry:
            self.status = self.IN_PROGRESS
            self.error_msg = None
            super().save(*args, **kwargs)
            upload_doctor_data.apply_async((self.id,), countdown=1)


class ProviderSignupLead(auth_model.TimeStampedModel):
    DOCTOR = 1
    HOSPITAL_ADMIN = 2
    TYPE_CHOICES = ((DOCTOR, "Doctor"), (HOSPITAL_ADMIN, "Hospital Admin"),)

    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    phone_number = models.BigIntegerField(unique=True)
    email = models.EmailField()
    type = models.IntegerField(choices=TYPE_CHOICES)
    is_docprime = models.NullBooleanField(null=True, editable=False)
    matrix_lead_id = models.IntegerField(null=True)

    def save(self, *args, **kwargs):
        super(ProviderSignupLead, self).save(*args, **kwargs)
        if self.is_docprime and not self.matrix_lead_id:
            create_or_update_lead_on_matrix.apply_async(({'obj_type': self.__class__.__name__, 'obj_id': self.id}
                                                         ,), countdown=5)

    class Meta:
        db_table = "provider_signup_lead"


class HealthInsuranceProvider(auth_model.TimeStampedModel):
    name = models.CharField(max_length=100)

    class Meta:
        db_table = 'health_insurance_provider'

    def __str__(self):
        return self.name


class HealthInsuranceProviderHospitalMapping(models.Model):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE,
                                 related_name='provider_mappings')
    provider = models.ForeignKey(HealthInsuranceProvider, on_delete=models.CASCADE,
                                related_name='hospital_provider_mappings')

    def __str__(self):
        return '{} - {}'.format(self.hospital.name, self.provider.name)

    class Meta:
        db_table = "hospital__health_insurance_provider_mapping"
        unique_together = (('hospital', 'provider'),)


class HospitalHelpline(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="hospital_helpline_numbers")
    std_code = models.CharField(max_length=20, blank=True, default="")
    number = models.BigIntegerField()
    details = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return self.hospital.name

    class Meta:
        db_table = "hospital_helpline"


class HospitalTiming(auth_model.TimeStampedModel):
    DAY_CHOICES = [(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")]
    SHORT_DAY_CHOICES = [(0, "Mon"), (1, "Tue"), (2, "Wed"), (3, "Thu"), (4, "Fri"), (5, "Sat"), (6, "Sun")]
    TIME_CHOICES = [(0.0, "12 AM"), (0.5, "12:30 AM"),
                    (1.0, "1 AM"), (5.5, "1:30 AM"),
                    (2.0, "2 AM"), (5.5, "2:30 AM"),
                    (3.0, "3 AM"), (5.5, "3:30 AM"),
                    (4.0, "4 AM"), (5.5, "4:30 AM"),
                    (5.0, "5 AM"), (5.5, "5:30 AM"),
                    (6.0, "6 AM"), (6.5, "6:30 AM"),
                    (7.0, "7:00 AM"), (7.5, "7:30 AM"),
                    (8.0, "8:00 AM"), (8.5, "8:30 AM"),
                    (9.0, "9:00 AM"), (9.5, "9:30 AM"),
                    (10.0, "10:00 AM"), (10.5, "10:30 AM"),
                    (11.0, "11:00 AM"), (11.5, "11:30 AM"),
                    (12.0, "12:00 PM"), (12.5, "12:30 PM"),
                    (13.0, "1:00 PM"), (13.5, "1:30 PM"),
                    (14.0, "2:00 PM"), (14.5, "2:30 PM"),
                    (15.0, "3:00 PM"), (15.5, "3:30 PM"),
                    (16.0, "4:00 PM"), (16.5, "4:30 PM"),
                    (17.0, "5:00 PM"), (17.5, "5:30 PM"),
                    (18.0, "6:00 PM"), (18.5, "6:30 PM"),
                    (19.0, "7:00 PM"), (19.5, "7:30 PM"),
                    (20.0, "8:00 PM"), (20.5, "8:30 PM"),
                    (21.0, "9:00 PM"), (21.5, "9:30 PM"),
                    (22.0, "10:00 PM"), (22.5, "10:30 PM"),
                    (23.0, "11 PM"), (23.5, "11:30 PM")]

    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='hosp_availability')
    day = models.PositiveSmallIntegerField(choices=DAY_CHOICES)
    start = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)
    end = models.DecimalField(max_digits=3, decimal_places=1, choices=TIME_CHOICES)


    class Meta:
        db_table = "hospital_timing"


class PartnersAppInvoice(auth_model.TimeStampedModel):
    DECIMAL_PLACES = 2
    INVOICE_SERIAL_ID_START = 300000
    ONLINE = 1
    CASH = 2
    PAYMENT_CHOICES = ((ONLINE, 'Online'), (CASH, 'Cash'))
    PAID = 1
    PENDING = 2
    PAYMENT_STATUS = ((PAID, 'Paid'), (PENDING, 'Pending'))
    INVOICE_STORAGE_FOLDER = 'partners/invoice'
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_serial_id = models.CharField(max_length=100)
    appointment = models.ForeignKey(OfflineOPDAppointments, on_delete=models.CASCADE, related_name='partners_app_invoice')
    consultation_fees = models.PositiveSmallIntegerField()
    selected_invoice_items = JSONField()
    payment_status = models.IntegerField(choices=PAYMENT_STATUS)
    payment_type = models.IntegerField(choices=PAYMENT_CHOICES, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    invoice_title = models.CharField(max_length=300, null=True, blank=True)
    sub_total_amount = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES, blank=True, null=True)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=DECIMAL_PLACES, blank=True, null=True,
                                         validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES, blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=DECIMAL_PLACES, blank=True, null=True,
                                              validators=[MinValueValidator(0), MaxValueValidator(100)])
    total_amount = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES)
    is_invoice_generated = models.BooleanField(default=False)
    file = models.FileField(upload_to=INVOICE_STORAGE_FOLDER, blank=False, null=False)
    invoice_url = models.URLField(null=True, blank=True)
    encoded_url = models.URLField(null=True, blank=True, max_length=300)
    is_valid = models.BooleanField(default=True)
    is_edited = models.BooleanField(default=False)
    edited_by = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True, related_name='patners_app_invoices')
    is_encrypted = models.BooleanField(default=False)

    def __str__(self):
        return str(self.appointment)

    def get_context(self, selected_invoice_items):
        context = dict()
        context["patient_name"] = self.appointment.user.name
        patient_mobile_queryset = self.appointment.user.patient_mobiles.all()
        if patient_mobile_queryset.exists():
            patient_mobile = patient_mobile_queryset.filter(is_default=True).first() if patient_mobile_queryset.filter(
                is_default=True).exists() else patient_mobile_queryset.first()
        else:
            patient_mobile = None
        context["patient_phone_number"] = patient_mobile
        context["invoice_serial_id"] = self.invoice_serial_id
        context["updated_at"] = self.updated_at if self.updated_at else datetime.datetime.now()
        context["payment_status"] = "Paid" if self.payment_status == self.PAID else "Pending"
        if self.payment_status == self.PAID:
            context["payment_status"] = "Paid"
            context["payment_type"] = "Online" if self.payment_type == self.ONLINE else "Cash"
        elif self.payment_status == self.PENDING:
            context["payment_status"] = "Pending"
            context["due_date"] = self.due_date
        context["doctor_name"] = self.appointment.doctor.name
        context["hospital_name"] = self.appointment.hospital.name
        context["hospital_address"] = self.appointment.hospital.get_hos_address()
        doctor_number = self.appointment.doctor.doctor_number.first()
        if doctor_number:
            context["doctor_phone_number"] = doctor_number.phone_number
        context["invoice_title"] = self.invoice_title
        context["consultation_fees"] = self.consultation_fees
        context["invoice_items"] = self.get_invoice_items(selected_invoice_items)
        context["sub_total_amount"] = str(self.sub_total_amount)
        context["tax_percentage"] = self.tax_percentage.normalize() if self.tax_percentage else None
        context["tax_amount"] = str(self.tax_amount) if self.tax_amount else "-"
        context["discount_percentage"] = self.discount_percentage.normalize() if self.discount_percentage else None
        context["discount_amount"] = str(self.discount_amount) if self.discount_amount else "-"
        context["total_amount"] = str(self.total_amount)
        return context

    def get_invoice_items(self, selected_invoice_items):
        invoice_items = list()
        # selected_invoice_items = self.selected_invoice_items
        for item in selected_invoice_items:
            if item['invoice_item'].tax_percentage:
                tax = str(item['invoice_item'].tax_amount) + ' (' + str(item['invoice_item'].tax_percentage.normalize()) + '%)'
            else:
                tax = str(item['invoice_item'].tax_amount)
            if item['invoice_item'].discount_percentage:
                discount = str(item['invoice_item'].discount_amount) + ' (' + str(item['invoice_item'].discount_percentage.normalize()) + '%)'
            else:
                discount = str(item['invoice_item'].discount_amount)
            invoice_items.append({"name": item['invoice_item'].item,
                                  "base_price": str(item['invoice_item'].base_price),
                                  "quantity": item['quantity'],
                                  "tax": tax,
                                  "discount": discount,
                                  "amount": str(item['calculated_price'])
                                  })
        return invoice_items

    @classmethod
    def last_serial(cls, appointment):
        obj = cls.objects.filter(appointment__doctor=appointment.doctor,
                                 appointment__hospital=appointment.hospital).order_by('-created_at').first()
        if obj:
            serial = int(obj.invoice_serial_id[-9:-3])
            return serial
        else:
            return cls.INVOICE_SERIAL_ID_START

    class Meta:
        db_table = "partners_app_invoice"


class EncryptedPartnersAppInvoiceLogs(auth_model.TimeStampedModel):
    invoice = JSONField()

    class Meta:
        db_table = "encrypted_partners_app_invoice_logs"


class GeneralInvoiceItems(auth_model.TimeStampedModel):
    DECIMAL_PLACES = 2
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item = models.CharField(max_length=200)
    base_price = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES)
    description = models.CharField(max_length=500, null=True, blank=True)
    tax_amount = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES, blank=True, null=True)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=DECIMAL_PLACES, blank=True, null=True,
                                         validators=[MinValueValidator(0), MaxValueValidator(100)])
    discount_amount = models.DecimalField(max_digits=10, decimal_places=DECIMAL_PLACES, blank=True, null=True)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=DECIMAL_PLACES, blank=True, null=True,
                                              validators=[MinValueValidator(0), MaxValueValidator(100)])
    user = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, related_name='invoice_items', null=True)
    hospitals = models.ManyToManyField(Hospital, related_name='invoice_items')

    def __str__(self):
        return self.item

    def get_computed_price(self):
        tax_amount = self.tax_amount if self.tax_amount else 0
        discount_amount = self.discount_amount if self.discount_amount else 0
        return (self.base_price + tax_amount - discount_amount)

    class Meta:
        db_table = "general_invoice_items"


class SelectedInvoiceItems(auth_model.TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(PartnersAppInvoice, on_delete=models.CASCADE, related_name='selected_items')
    invoice_item = models.ForeignKey(GeneralInvoiceItems, on_delete=models.CASCADE, related_name='selected')
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    calculated_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.invoice_item + " (" + self.invoice + ")"

    class Meta:
        db_table = "selected_invoice_items"


class ProviderEncrypt(auth_model.TimeStampedModel):
    is_encrypted = models.BooleanField(default=False)
    encrypted_by = models.ForeignKey(auth_model.User, null=True, blank=True, on_delete=models.SET_NULL,
                                     related_name='encrypted_hospitals')
    hint = models.CharField(max_length=128, null=True, blank=True)
    encrypted_hospital_id = models.CharField(max_length=128, null=True, blank=True)
    email = models.EmailField(max_length=100, null=True, blank=True)
    phone_numbers = ArrayField(models.CharField(max_length=10, blank=True), null=True)
    google_drive = models.EmailField(max_length=100, null=True, blank=True)
    hospital = models.OneToOneField(Hospital, on_delete=models.CASCADE, related_name='encrypt_details')
    is_valid = models.BooleanField(default=True)
    is_consent_received = models.BooleanField(default=True)

    def __str__(self):
        return self.hospital

    class Meta:
        db_table = "provider_encrypt"

    def send_sms(self, action_user):
        from ondoc.communications.models import ProviderAppNotification
        if self.is_encrypted:
            sms_notification = ProviderAppNotification(self.hospital, action_user, NotificationAction.PROVIDER_ENCRYPTION_ENABLED)
            sms_notification.send()
        elif not self.is_encrypted:
            sms_notification = ProviderAppNotification(self.hospital, action_user, NotificationAction.PROVIDER_ENCRYPTION_DISABLED)
            sms_notification.send()


class CommonHospital(auth_model.TimeStampedModel):
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, null=True, blank=True)
    network = models.ForeignKey(HospitalNetwork, on_delete=models.CASCADE, null=True, blank=True)
    priority = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "common_hospital"

