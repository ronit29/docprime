import reversion
from django.contrib.gis.geos import Point
from django.contrib.postgres.fields import JSONField
from django.core.validators import FileExtensionValidator, MinValueValidator, MaxValueValidator
from django.db import models, transaction
from django.db.models import Q
from weasyprint import HTML, CSS
import string
import random
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from weasyprint.fonts import FontConfiguration
# from hardcopy import bytestring_to_pdf
import io
#from tempfile import NamedTemporaryFile
from django.core.files.storage import default_storage
from django.core.files.storage import FileSystemStorage
from django.core.files.base import ContentFile
from django.core.files import File
from io import BytesIO
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from ondoc.authentication.models import TimeStampedModel
from ondoc.doctor import models as doc_models
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment
from ondoc.authentication.models import User
from ondoc.authentication import models as auth_model
from ondoc.bookinganalytics.models import DP_StateMaster, DP_CityMaster
import datetime
from datetime import date
from django.utils import timezone

from ondoc.common.helper import Choices
from django.conf import settings
import requests
from rest_framework import status

# from ondoc.doctor.models import PurchaseOrderCreation, PracticeSpecialization



class Cities(models.Model):
    name = models.CharField(max_length=48, db_index=True)

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'cities'


class MatrixCityMapping(models.Model):
    city_id = models.PositiveIntegerField()
    name = models.CharField(max_length=48, db_index=True)

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'matrix_city_mapping'


class PDFTester(models.Model):
    html = models.TextField(max_length=50000000)
    css = models.TextField(max_length=50000000, blank=True)
    file = models.FileField(upload_to='common/pdf/test', blank=True)

    # def save(self, *args, **kwargs):
    #
    #     random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
    #     path = 'common/pdf/test/' + random_string + '.pdf'
    #     fs = FileSystemStorage()
    #     file = fs.open(path, 'wb')
    #
    #     extra_args = {
    #         'virtual-time-budget': 6000
    #     }
    #
    #     bytestring_to_pdf(self.html.encode(), file, **extra_args)
    #
    #     file.close()
    #
    #     ff = File(fs.open(path, 'rb'))
    #
    #     random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
    #     name = random_string+'.pdf'
    #
    #     self.file = InMemoryUploadedFile(ff.file, None, 'aaa.pdf', 'application/pdf', ff.file.tell(), None)
    #
    #
    #     super().save(*args, **kwargs)


    class Meta:
        db_table = 'pdftest'


class AppointmentHistory(TimeStampedModel):
    CRM = "crm"
    WEB = "web"
    DOC_APP = "d_app"
    CONSUMER_APP = "c_app"
    DOC_WEB = "d_web"
    D_WEB_URL = "d_web_url"
    D_TOKEN_URL = "d_token_url"
    IVR = "ivr"
    API= "thyrocare_api"
    SOURCE_CHOICES = ((CONSUMER_APP, "Consumer App"), (CRM, "CRM"), (WEB, "Consumer Web"), (DOC_APP, "Doctor App"),
                      (DOC_WEB, "Provider Web"), (D_WEB_URL, "Doctor Web URL"), (D_TOKEN_URL, "Doctor Token URL"),
                      (IVR, "Auto IVR"), (API, "Thyrocare API"))

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    status = models.PositiveSmallIntegerField(null=False)
    user = models.ForeignKey(User, null=True, default=None, on_delete=models.CASCADE)
    source = models.CharField(max_length=50, blank=True, choices=SOURCE_CHOICES, default='')

    @classmethod
    def create(cls, *args, **kwargs):
        obj = kwargs.get('content_object')
        if not obj:
            raise Exception('Function accept content_object in **kwargs')

        user = None
        source = ''
        if hasattr(obj, "_responsible_user"):
            user = obj._responsible_user
        if hasattr(obj, "_source"):
            source = obj._source

        if not user and not source:
            return 

        content_type = ContentType.objects.get_for_model(obj)
        cls(content_type=content_type, object_id=obj.id, status=obj.status, user=user, source=source).save()


    class Meta:
        db_table = 'appointment_history'


class PaymentOptions(TimeStampedModel):
    image = models.ImageField('Payment image', upload_to='payment/images')
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    is_enabled = models.BooleanField()
    action = models.CharField(max_length=50)
    priority = models.IntegerField(default=0, null=True)
    payment_gateway = models.TextField(blank=True, default='')

    @classmethod
    def filtered_payment_option(cls, order_obj):
        from ondoc.coupon.models import Coupon
        queryset = cls.objects.filter(is_enabled=True).order_by('-priority')

        orders_to_check = []
        if order_obj.orders.exists():
            orders_to_check = order_obj.orders.all()
        else:
            orders_to_check = [order_obj]

        used_coupon = []
        for order in orders_to_check:
            if "coupon" in order.action_data:
                used_coupon.extend(order.action_data["coupon"])
        used_coupon = list(set(used_coupon))

        pg_specific_coupon = Coupon.objects.filter(id__in=used_coupon).exclude(payment_option__isnull=True).first()
        if pg_specific_coupon:
            allowed_options = queryset.filter(id=pg_specific_coupon.payment_option.id)
            not_allowed = queryset.filter(~models.Q(id=pg_specific_coupon.payment_option.id))
            invalid_reason = "Below payment modes are not applicable as you have used the coupon " + pg_specific_coupon.code + ". " \
                             "Please remove the coupon to pay with the options listed below."
        else:
            allowed_options = queryset
            not_allowed = []
            invalid_reason = ""

        return cls.build_payment_option(allowed_options), cls.build_payment_option(not_allowed), invalid_reason

    @classmethod
    def build_payment_option(cls, queryset):
        options = []
        for data in queryset:
            resp = {}
            resp['name'] = data.name
            resp['image'] = data.image.url
            resp['description'] = data.description
            resp['is_enabled'] = data.is_enabled
            resp['action'] = data.action
            resp['payment_gateway'] = data.payment_gateway
            resp['id'] = data.id
            resp['payment_gateway'] = data.payment_gateway
            resp['is_selected'] = False
            options.append(resp)

        if options:
            options[0]['is_selected'] = True
        return options

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'payment_options'


class UserConfig(TimeStampedModel):
    key = models.CharField(max_length=500, unique=True)
    data = JSONField(blank=True, null=True)

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = 'user_config'


class AppointmentMaskNumber(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    mask_number = models.CharField(blank=True, null=True, max_length=20)
    validity_up_to = models.DateTimeField(null=True, blank=True)
    is_mask_number = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)

    def build_data(self):
        data = {}
        data['appointment_id'] = self.object_id
        data['mask_number'] = self.mask_number
        data['validity_up_to'] = self.validity_up_to
        return data

    class Meta:
        db_table = 'appointment_mask_number'


class GlobalNonBookable(TimeStampedModel):
    INTERVAL_MAPPING = {
        ("00:00:00", "14:00:00"): 'morning',
        ("14:00:00", "23:59:59"): 'evening',
        ("00:00:00", "23:59:59"): 'all',
    }

    DOCTOR = "doctor"
    LAB = "lab"
    BOOKING_TYPE_CHOICES = ((DOCTOR, "Doctor Clinic"), (LAB, "Lab"))
    booking_type = models.CharField(max_length=20, blank=False, choices=BOOKING_TYPE_CHOICES, null=False)
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=False)
    start_time = models.TimeField(null=False)
    end_time = models.TimeField(null=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    def start_time_in_float(self):
        start_time = self.start_time
        start_time = round(float(start_time.hour) + (float(start_time.minute) * 1 / 60), 2)
        return start_time

    def end_time_in_float(self):
        end_time = self.end_time
        end_time = round(float(end_time.hour) + (float(end_time.minute) * 1 / 60), 2)
        return end_time

    @classmethod
    def get_non_bookables(self, booking_type=DOCTOR):
        non_bookables_range = list()
        non_bookables = self.objects.filter(deleted_at__isnull=True, booking_type=booking_type)
        for nb in non_bookables:
            start_datetime = datetime.datetime.combine(nb.start_date, nb.start_time)
            end_datetime = datetime.datetime.combine(nb.end_date, nb.end_time)
            non_bookables_range.append({'start_datetime': start_datetime, 'end_datetime': end_datetime})
        return non_bookables_range

    class Meta:
        db_table = 'global_non_bookable_timing'

    @property
    def interval(self):
        return self.INTERVAL_MAPPING.get((str(self.start_time), str(self.end_time)))


class Feature(TimeStampedModel):
    icon = models.ImageField('Feature image', upload_to='feature/images')
    name = models.CharField(max_length=100)
    priority = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'feature'

    def __str__(self):
        return self.name


class Service(TimeStampedModel):
    icon = models.ImageField('Service image', upload_to='service/images')
    name = models.CharField(max_length=100)

    class Meta:
        db_table = 'service'

    def __str__(self):
        return self.name


class Remark(auth_model.TimeStampedModel):
    FEEDBACK = 1
    REOPEN = 2
    OTHER = 3
    STATUS_CHOICES = [("", "Select"), (FEEDBACK, "Feedback"), (REOPEN, "Reopen"), (OTHER, "Other")]

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    user = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField()
    status = models.PositiveSmallIntegerField(default=0, choices=STATUS_CHOICES)

    class Meta:
        db_table = 'remark'


class SyncBookingAnalytics(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    synced_at = models.DateTimeField(null=True)
    last_updated_at = models.DateTimeField(null=True)

    class Meta:
        unique_together = (('object_id', 'content_type'), )
        db_table = "sync_booking_analytics"


class MatrixMappedState(TimeStampedModel):
    name = models.CharField(max_length=48, db_index=True)
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="state_analytics")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'matrix_mapped_state'
        verbose_name_plural = "Matrix Mapped States"

    def get_booking_analytics_data(self):
        data = dict()

        data['CreatedOn'] = self.updated_at
        data['StateId'] = self.id
        data['StateName'] = self.name

        return data

    def sync_with_booking_analytics(self):
        # obj = DP_StateMaster.objects.filter(StateId=self.id).first()
        # if not obj:
        #     obj = DP_StateMaster()
        #     obj.CreatedOn = self.updated_at
        #     obj.StateId = self.id
        # obj.StateName = self.name
        # obj.save()

        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(MatrixMappedState),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            print(str(e))
            pass

        # return obj


class MatrixMappedCity(TimeStampedModel):
    name = models.CharField(max_length=48, db_index=True)
    state = models.ForeignKey(MatrixMappedState, on_delete=models.SET_NULL, null=True, blank=True)
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="city_analytics")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'matrix_mapped_city'
        verbose_name_plural = "Matrix Mapped Cities"

    def get_booking_analytics_data(self):
        data = dict()

        data['CreatedOn'] = self.updated_at
        data['CityId'] = self.id
        data['CityName'] = self.name

        return data

    def sync_with_booking_analytics(self):
        # obj = DP_CityMaster.objects.filter(CityId=self.id).first()
        # if not obj:
        #     obj = DP_CityMaster()
        #     obj.CreatedOn = self.updated_at
        #     obj.CityId = self.id
        # obj.CityName = self.name
        # obj.save()

        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(MatrixMappedCity),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            pass

        # return obj


class QRCode(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey()
    name = models.FileField(upload_to='qrcode', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])
    data = JSONField(null=True, blank=True)
    # name = models.ImageField(upload_to='qrcode', blank=True, null=True)

    class Meta:
        db_table = 'qr_code'


class CompletedBreakupMixin(object):

    def get_completion_breakup(self):

        completed_appointments = [self]
        if self.money_pool:
            completed_appointments = self.money_pool.get_completed_appointments()

        total_wallet = self.effective_price
        total_cashback = 0

        if self.money_pool:
            total_wallet = self.money_pool.wallet
            total_cashback = self.money_pool.cashback
        elif self.price_data:
            total_wallet = self.price_data["wallet_amount"]
            total_cashback = self.price_data["cashback_amount"]

        for app in completed_appointments:
            curr_cashback = min(total_cashback, app.effective_price)
            curr_wallet = min(total_wallet, app.effective_price - curr_cashback)

            total_cashback -= curr_cashback
            total_wallet -= curr_wallet

            if app.id == self.id:
                return curr_wallet, curr_cashback

        return 0, 0


class RefundDetails(TimeStampedModel):
    refund_reason = models.TextField(null=True, blank=True, default=None)
    refund_initiated_by = models.ForeignKey(auth_model.User, related_name="refunds_initiated", on_delete=models.DO_NOTHING, null=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'refund_details'

    @classmethod
    def log_refund(cls, appointment):
        if hasattr(appointment, '_source') and appointment._source == AppointmentHistory.CRM:
            refund_reason = appointment._refund_reason if hasattr(appointment, '_refund_reason') else None
            refund_initiated_by = appointment._responsible_user if hasattr(appointment, '_responsible_user') else None
            if not refund_initiated_by:
                raise Exception("Must have a responsible user.")
            cls .objects.create(refund_reason=refund_reason, refund_initiated_by=refund_initiated_by, content_object=appointment)


class MatrixDataMixin(object):

    def get_matrix_policy_data(self):
        user_insurance = self.user.active_insurance
        primary_proposer_name = None

        if user_insurance:
            primary_proposer = user_insurance.get_primary_member_profile()
            primary_proposer_name = primary_proposer.get_full_name() if primary_proposer else None

        insurance_link = '%s/admin/insurance/userinsurance/%s/change' % (settings.ADMIN_BASE_URL, user_insurance.id)

        policy_details = {
            "ProposalNo": None,
            "PolicyPaymentSTATUS": 300 if user_insurance else 0,
            "BookingId": user_insurance.id if user_insurance else None,
            "ProposerName": primary_proposer_name,
            "PolicyId": user_insurance.policy_number if user_insurance else None,
            "InsurancePlanPurchased": user_insurance.insurance_plan.name if user_insurance else None,
            "PurchaseDate": int(user_insurance.purchase_date.timestamp()) if user_insurance else None,
            "ExpirationDate": int(user_insurance.expiry_date.timestamp()) if user_insurance else None,
            "COILink": insurance_link,
            "InsuranceLink": insurance_link,
            "PeopleCovered": user_insurance.insurance_plan.get_people_covered() if user_insurance else ""
        }

        return policy_details

    def calculate_age(self):
        if not self.profile:
            return 0
        if not self.profile.dob:
            return 0
        dob = self.profile.dob
        today = date.today()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    def appointment_accepted_history(self):
        source = ""
        accepted_phone = None
        history_obj = self.history.filter(status=self.ACCEPTED).first()
        if history_obj:
            source = history_obj.source
            if source == 'ivr':
                auto_ivr_data = history_obj.content_object.auto_ivr_data
                for data in auto_ivr_data:
                    if data.get('status') == self.ACCEPTED:
                        accepted_phone = data.get('phone_number')
            else:
                user = history_obj.user
                if user:
                    accepted_phone = user.phone_number

        return {'source': source, 'accepted_phone': accepted_phone}

    def merchant_payout_data(self):
        provider_payment_status = ''
        settlement_date = None
        payment_URN = ''
        amount = None
        merchant_payout = self.merchant_payout
        if merchant_payout:
            provider_payment_status = dict(merchant_payout.STATUS_CHOICES)[merchant_payout.status]
            settlement_date = int(merchant_payout.payout_time.timestamp()) if merchant_payout.payout_time else None
            payment_URN = merchant_payout.utr_no
            amount = merchant_payout.payable_amount

        return {'provider_payment_status': provider_payment_status, 'settlement_date': settlement_date, 'payment_URN': payment_URN, 'amount': amount}

    def refund_details_data(self):
        from ondoc.account.models import ConsumerTransaction
        from ondoc.account.models import PgTransaction
        from ondoc.account.models import ConsumerRefund
        customer_status = ""
        refund_urn = ""
        refund_initiated_at = None
        original_payment_mode_refund = 0.0
        promotional_wallet_refund = 0.0

        product_id = self.PRODUCT_ID
        ct = ConsumerTransaction.objects.filter(type=PgTransaction.CREDIT, reference_id=self.id, product_id=product_id,
                                                action=ConsumerTransaction.CANCELLATION)

        wallet_ct = ct.filter(source=ConsumerTransaction.WALLET_SOURCE).first()
        cashback_ct = ct.filter(source=ConsumerTransaction.CASHBACK_SOURCE).first()

        if wallet_ct:
            original_payment_mode_refund = wallet_ct.amount
            refund_initiated_at = wallet_ct.created_at.timestamp()
            # consumer_refund = ConsumerRefund.objects.filter(consumer_transaction_id=wallet_ct.id).first()
            # if consumer_refund:
            #     refund_initiated_at = consumer_refund.refund_initiated_at
            #     customer_status = consumer_refund.refund_state

        if cashback_ct:
            promotional_wallet_refund = cashback_ct.amount
            refund_initiated_at = cashback_ct.created_at.timestamp()

        return {'original_payment_mode_refund': original_payment_mode_refund, 'promotional_wallet_refund': promotional_wallet_refund,
                'customer_status': customer_status, 'refund_urn': refund_urn, 'refund_initiated_at': refund_initiated_at}


class DeviceDetails(TimeStampedModel):
    device_id = models.CharField(max_length=200)
    app_version = models.CharField(max_length=20, null=True, blank=True)
    os = models.CharField(max_length=40, null=True, blank=True)
    os_version = models.CharField(max_length=20, null=True, blank=True)
    make = models.CharField(max_length=100, null=True, blank=True)
    model = models.CharField(max_length=100, null=True, blank=True)
    # installed_date = models.DateTimeField()   # created_at is the installed_date for given d_token
    firebase_reg_id = models.CharField(max_length=200, null=True, blank=True)
    user = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name="device_details")
    app_name = models.CharField(max_length=200, null=True, blank=True)
    ping_status = models.CharField(max_length=50, null=True, blank=True)
    last_ping_time = models.DateTimeField(null=True, blank=True)
    dnd = models.BooleanField(default=False)
    res = models.CharField(max_length=100, null=True, blank=True)
    adv_id = models.CharField(max_length=100, null=True, blank=True)
    apps_flyer_id = models.CharField(max_length=100, null=True, blank=True)
    data = JSONField()

    def __str__(self):
        return self.device_id

    class Meta:
        db_table = "device_details"


class LastUsageTimestamp(TimeStampedModel):
    phone_number = models.BigIntegerField(validators=[MinValueValidator(1000000000), MaxValueValidator(9999999999)])
    registered_on_app = models.BooleanField(default=False)
    device = models.ForeignKey(DeviceDetails, null=True, blank=True, related_name="last_usage", on_delete=models.SET_NULL)
    source = models.CharField(max_length=20, choices=AppointmentHistory.SOURCE_CHOICES)
    # first_usage_timestamp = models.DateTimeField(auto_now_add=True)           created_at is the first_usage_timestamp
    last_app_open_timestamp = models.DateTimeField()

    def __str__(self):
        return str(self.phone_number)

    class Meta:
        db_table = "last_usage_timestamp"


class BlockedStates(TimeStampedModel):

    class States(Choices):
        LOGIN = 'LOGIN'
        INSURANCE = 'INSURANCE'
        VIP = 'VIP'

    state_name = models.CharField(max_length=50, null=False, blank=False, choices=States.as_choices(), unique=True)
    message = models.TextField()

    def __str__(self):
        return self.state_name

    class Meta:
        db_table = 'blocked_states'


class BlacklistUser(TimeStampedModel):
    user = models.ForeignKey(User, related_name='blacklist_user', on_delete=models.DO_NOTHING)
    type = models.ForeignKey(BlockedStates, on_delete=models.DO_NOTHING)
    reason = models.TextField(null=True)
    blocked_by = models.ForeignKey(User, on_delete=models.DO_NOTHING)
    enabled = models.BooleanField(default=True)

    @classmethod
    def get_state_by_number(cls, phone_number, blocked_state):
        blacklist_user = cls.objects.filter(user__phone_number=phone_number, type__state_name=blocked_state,
                                            enabled=True, user__user_type=User.CONSUMER).first()
        if blacklist_user:
            return blacklist_user.type

        return None

    class Meta:
        db_table = 'blacklist_users'
        unique_together = (("user", "type"), )


class GenericNotes(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey()
    notes = models.TextField()
    created_by = models.ForeignKey(User, on_delete=models.DO_NOTHING, blank=True, null=True)
    notes_file = models.FileField(null=True, blank=True, upload_to='notes', validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])])

    class Meta:
        db_table = 'generic_notes'


class TdsDeductionMixin(object):

    def get_tds_amount(self):
        from ondoc.authentication.models import Merchant
        from ondoc.authentication.models import MerchantNetRevenue
        import decimal
        tds = 0
        merchant = self.get_merchant
        if merchant:
            booking_net_revenue = self.get_booking_revenue()
            payout_amount = 0
            if self.__class__.__name__ == 'OpdAppointment':
                payout_amount = self.fees
            elif self.__class__.__name__ == 'LabAppointment':
                payout_amount = self.agreed_price
                if self.is_home_pickup:
                    payout_amount += self.home_pickup_charges

            if merchant.enable_for_tds_deduction:
                merchant_net_revenue_obj = merchant.net_revenue.filter(financial_year=settings.CURRENT_FINANCIAL_YEAR).first()
                if merchant_net_revenue_obj:
                    old_revenue = merchant_net_revenue_obj.total_revenue
                    new_revenue = merchant_net_revenue_obj.total_revenue + booking_net_revenue
                    if (new_revenue >= decimal.Decimal(settings.TDS_THRESHOLD_AMOUNT)) and (old_revenue < decimal.Decimal(settings.TDS_THRESHOLD_AMOUNT)):
                        tds = (new_revenue * decimal.Decimal(settings.TDS_APPLICABLE_RATE)) / 100
                    elif old_revenue > decimal.Decimal(settings.TDS_THRESHOLD_AMOUNT):
                        tds_deduction_count = merchant.tds_deduction.filter(financial_year=settings.CURRENT_FINANCIAL_YEAR).count()
                        if tds_deduction_count > 0:
                            tds = (booking_net_revenue * decimal.Decimal(settings.TDS_APPLICABLE_RATE)) / 100
                        else:
                            tds = (new_revenue * decimal.Decimal(settings.TDS_APPLICABLE_RATE)) / 100
                else:
                    if booking_net_revenue >= decimal.Decimal(settings.TDS_THRESHOLD_AMOUNT):
                        tds = (booking_net_revenue * decimal.Decimal(settings.TDS_APPLICABLE_RATE)) / 100
        return tds

    def update_net_revenues(self, tds):
        from ondoc.authentication.models import MerchantNetRevenue
        merchant = self.get_merchant
        if merchant:
            booking_net_revenue = self.get_booking_revenue()
            merchant_net_revenue_obj = merchant.net_revenue.filter(financial_year=settings.CURRENT_FINANCIAL_YEAR).first()
            if merchant_net_revenue_obj:
                total_revenue = booking_net_revenue + merchant_net_revenue_obj.total_revenue
                if not merchant_net_revenue_obj.tds_deducted:
                    total_tds = tds
                else:
                    total_tds = merchant_net_revenue_obj.tds_deducted + tds
                merchant_net_revenue_obj.total_revenue = total_revenue
                merchant_net_revenue_obj.tds_deducted = total_tds
                merchant_net_revenue_obj.save()
            else:
                merchant_net_revenue_obj = MerchantNetRevenue(merchant=merchant, financial_year=settings.CURRENT_FINANCIAL_YEAR)
                merchant_net_revenue_obj.tds_deducted = tds
                merchant_net_revenue_obj.total_revenue = booking_net_revenue
                merchant_net_revenue_obj.save()


class Documents(TimeStampedModel):
    DOCUMENT = 1
    CREDIT_LETTER = 2
    DOCUMENT_TYPES = [("", "Select"), (DOCUMENT, "Document"), (CREDIT_LETTER, "Credit Letter")]

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    document_type = models.PositiveSmallIntegerField(default=1, choices=DOCUMENT_TYPES)
    file = models.FileField(upload_to='credit_letter', null=True, blank=True)
    is_valid = models.BooleanField(default=True)

    class Meta:
        db_table = 'documents'


class VirtualAppointment(TimeStampedModel):
    BOOKED = "booked"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    DOCTOR = "doctor"
    LAB = "lab"
    STATUS_CHOICES = [(BOOKED, "Booked"), (CANCELLED, "Cancelled"), (COMPLETED, "Completed")]
    TYPE_CHOICES = [(DOCTOR, "Doctor"), (LAB, "Lab")]
    name = models.CharField(max_length=200)
    type = models.CharField(choices=TYPE_CHOICES, max_length=20)
    status = models.CharField(choices=STATUS_CHOICES, max_length=20)
    time_slot_start = models.DateTimeField()
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()

    class Meta:
        db_table = 'virtual_appointment'

    def save(self, *args, **kwargs):
        database_instance = None
        if self.id:
            database_instance = self.__class__.objects.filter(pk=self.id).first()
        push_to_matrix = False
        if (not database_instance) or (database_instance and database_instance.time_slot_start != database_instance):
            push_to_matrix = True
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.app_commit_tasks(push_to_matrix=push_to_matrix))

    def app_commit_tasks(self, push_to_matrix):
        from ondoc.procedure.models import IpdProcedureLead
        if push_to_matrix:
            if isinstance(self.content_object, IpdProcedureLead) and hasattr(self.content_object, 'app_commit_tasks'):
                self.content_object.app_commit_tasks(send_lead_email=False, update_status_in_matrix=True)


class MerchantPayoutMixin(object):

    def create_payout_from_appointment(self):
        from ondoc.doctor.models import OpdAppointment
        if self.status == self.COMPLETED and self.merchant_payout is None and self.payment_type not in [OpdAppointment.COD]:
            self.save_merchant_payout()
            self.update_payout_id(self.merchant_payout_id)

    def update_payout_id(self, payout_id):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.insurance.models import UserInsurance

        if self.__class__.__name__ == 'OpdAppointment':
            OpdAppointment.objects.filter(id=self.id).update(merchant_payout_id=payout_id)
        elif self.__class__.__name__ == 'LabAppointment':
            LabAppointment.objects.filter(id=self.id).update(merchant_payout_id=payout_id)
        elif self.__class__.__name__ == 'UserInsurance':
            UserInsurance.objects.filter(id=self.id).update(merchant_payout_id=payout_id)


class Fraud(auth_model.TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    user = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True)
    reason = models.TextField(max_length=300)

    class Meta:
        db_table = 'fraud'
        unique_together = ('content_type', 'object_id',)



class SponsorListingURL(auth_model.TimeStampedModel):
    poc = models.ForeignKey("doctor.PurchaseOrderCreation", on_delete=models.CASCADE, null=True, blank=True, related_name='poc_sponsorlisting')
    seo_url = models.CharField(max_length=500, null=True, blank=True)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'sponsor_listing_url'

    def __str__(self):
        return self.seo_url


class SponsorListingSpecialization(auth_model.TimeStampedModel):
    from django.contrib.gis.db import models as gis_models

    poc = models.ForeignKey("doctor.PurchaseOrderCreation", on_delete=models.CASCADE, related_name='poc_specialization', null=True)
    specialization = models.ForeignKey("doctor.PracticeSpecialization", on_delete=models.SET_NULL, null=True, blank=True, related_name='listing_specialization')
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    location = gis_models.PointField(geography=True, srid=4326, blank=True, null=True)
    radius = models.FloatField(null=True)
    is_enabled = models.BooleanField(default=False)

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if self.latitude and self.longitude:
            self.location = Point(float(self.longitude), float(self.latitude))

        super().save(force_insert, force_update, using, update_fields)


    class Meta:
        db_table = 'sponsor_listing_specialization'

    # def __str__(self):
    #     return self.id




class SponsorListingUtmTerm(auth_model.TimeStampedModel):
    poc = models.ForeignKey('doctor.PurchaseOrderCreation', on_delete=models.CASCADE, related_name='poc_utm_term', null=True)
    utm_term = models.CharField(max_length=1000, null=True, blank=True)
    is_enabled = models.BooleanField(default=False)

    class Meta:
        db_table = 'sponsor_listing_utm_term'

    def __str__(self):
        return self.utm_term


class SponsoredListingService(auth_model.TimeStampedModel):
    poc = models.ForeignKey('doctor.PurchaseOrderCreation', on_delete=models.SET_NULL, related_name='poc_sponsor_service', null=True)
    hospital_service = models.ForeignKey('doctor.HospitalSponsoredServices', on_delete=models.SET_NULL, null=True, related_name='hospservices')
    class Meta:
        db_table = 'sponsoredlisting_service'


class DocumentsProofs(auth_model.TimeStampedModel):

    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey()
    user = models.ForeignKey(User, null=True, on_delete=models.CASCADE)
    proof_file = models.FileField(null=False, upload_to='document_proofs', validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jpg', 'jpeg', 'png'])])

    # @classmethod
    # def prescription_exist_for_date(cls, user, date):
    #     return cls.objects.filter(created_at__date=date, user=user, object_id__isnull=False).exists()

    @classmethod
    def update_with_object(cls, app_obj, ids):
        content_type = ContentType.objects.get_for_model(app_obj)
        cls.objects.filter(id__in=ids).update(content_type_id=content_type.id, object_id=app_obj.id)

    @classmethod
    def is_proof_uploaded(cls, app_obj):
        content_type = ContentType.objects.get_for_model(app_obj)
        document_proofs = cls.objects.filter(content_type_id=content_type.id, object_id=app_obj.id)
        if document_proofs:
            return True
        else:
            return False

    class Meta:
        db_table = 'document_proofs'


@reversion.register()
class SearchCriteria(auth_model.TimeStampedModel):
    SEARCH_CHOICES = [("", "Select"), ("is_gold", "is_gold"), ("is_vip", "is_vip")]
    search_key = models.CharField(max_length=500, null=True, blank=True, choices=SEARCH_CHOICES, default=None)
    search_value = models.BooleanField(default=False)

    class Meta:
        db_table = 'search_criteria'

    def save(self, *args, **kwargs):
        search_criteria_obj = self.__class__.objects.filter(search_key=self.search_key).first()
        if search_criteria_obj:
            search_criteria_obj.search_value = self.search_value
            super(SearchCriteria, self).save(*args, **kwargs)
        else:
            super(SearchCriteria, self).save(*args, **kwargs)


class Certifications(auth_model.TimeStampedModel):
    name = models.CharField(max_length=200)

    class Meta:
        db_table = 'certifications'

    def __str__(self):
        return self.name


class GoogleLatLong(auth_model.TimeStampedModel):
    latitude = models.FloatField()
    longitude = models.FloatField()
    coordinates = models.TextField(null=True, blank=True)
    is_hospital_done = models.BooleanField(default=False)
    is_doctor_done = models.BooleanField(default=False)

    @classmethod
    def generate_place_ids(cls):
        coordinates_obj = GoogleLatLong.objects.filter(Q(is_hospital_done=False)|Q(is_doctor_done=False))
        types = ['doctor', 'hospital']
        for point_obj in coordinates_obj:
            for type in types:
                if (type == 'doctor' and point_obj.is_doctor_done == False) or (
                        type == 'hospital' and point_obj.is_hospital_done == False):
                    location = str(point_obj.latitude) + ' , ' + str(point_obj.longitude)
                    params = {'radius': 450, 'type': type, 'key': settings.REVERSE_GEOCODING_API_KEY,
                              'location': location}

                    place_response = requests.get('https://maps.googleapis.com/maps/api/place/nearbysearch/json',
                                                  params=params)
                    if place_response.status_code != status.HTTP_200_OK or not place_response.ok:
                        print('failure  status_code: ' + str(place_response.status_code) + ', reason: ' + str(
                            place_response.reason) + str(point_obj) + " type: " + type)

                    place_searched_data = place_response.json()
                    if place_searched_data.get('status') == 'OVER_QUERY_LIMIT':
                        print('OVER_QUERY_LIMIT'+ str(point_obj) + " type: " + type)
                        return None

                    if place_searched_data.get('results'):
                        for data in place_searched_data.get('results'):
                            if type == 'hospital':
                                HospitalPlaceIDs.objects.get_or_create(place_id=data.get('place_id'),
                                                                google_coordinates=point_obj)
                                point_obj.is_hospital_done = True

                            if type == 'doctor':
                                DoctorPlaceIDs.objects.get_or_create(place_id=data.get('place_id'),
                                                              google_coordinates=point_obj)
                                point_obj.is_doctor_done = True
                        point_obj.save()

    class Meta:
        db_table = 'google_lat_long'


class HospitalPlaceIDs(auth_model.TimeStampedModel):
    place_id = models.TextField()
    google_coordinates = models.ForeignKey(GoogleLatLong, on_delete=models.CASCADE, related_name="hosp_place_ids", null=True)

    class Meta:
        db_table = 'hospital_place_ids'


class DoctorPlaceIDs(auth_model.TimeStampedModel):
    place_id = models.TextField()
    google_coordinates = models.ForeignKey(GoogleLatLong, on_delete=models.CASCADE, related_name="doc_place_ids", null=True)

    class Meta:
        db_table = 'doctor_place_ids'


class GeneralMatrixLeads(auth_model.TimeStampedModel):
    matrix_lead_id = models.IntegerField(null=True)
    request_body = JSONField(default={})
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE, null=True, blank=True)
    phone_number = models.BigIntegerField(blank=True, null=True, validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)])
    lead_type = models.CharField(max_length=100, null=False, blank=False)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        transaction.on_commit(lambda: self.after_commit())

    def after_commit(self):
        from ondoc.notification.tasks import process_leads_to_matrix
        if self.request_body.get('lead_type') == "DROPOFF":
            process_leads_to_matrix.apply_async(({'id': self.id}, ), countdown=600)
        else:
            process_leads_to_matrix.apply_async(({'id': self.id}, ))

    @classmethod
    def create_lead(cls, request):
        phone_number = request.data.get('phone_number', None)
        if not phone_number:
            return None

        if phone_number and (request.user.is_anonymous or not request.user.is_authenticated):
            user = User.objects.filter(phone_number=phone_number, user_type=User.CONSUMER).first()
        else:
            user = request.user
            phone_number = user.phone_number

        data = {'user': user, 'request_body': request.data, 'phone_number': phone_number, 'lead_type': request.data.get('lead_type')}
        obj = cls(**data)
        obj.save()

        return obj

    class Meta:
        db_table = 'general_matrix_leads'
