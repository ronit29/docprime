from django.contrib.postgres.fields import JSONField
from django.core.validators import FileExtensionValidator
from django.db import models
from weasyprint import HTML, CSS
import string
import random
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from weasyprint.fonts import FontConfiguration
from hardcopy import bytestring_to_pdf
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
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment
from ondoc.authentication.models import User
from ondoc.authentication import models as auth_model
from ondoc.bookinganalytics.models import DP_StateMaster, DP_CityMaster
import datetime
from django.utils import timezone

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

    def save(self, *args, **kwargs):

        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        path = 'common/pdf/test/' + random_string + '.pdf'
        fs = FileSystemStorage()
        file = fs.open(path, 'wb')

        extra_args = {
            'virtual-time-budget': 6000
        }

        bytestring_to_pdf(self.html.encode(), file, **extra_args)

        file.close()

        ff = File(fs.open(path, 'rb'))

        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        name = random_string+'.pdf'

        self.file = InMemoryUploadedFile(ff.file, None, 'aaa.pdf', 'application/pdf', ff.file.tell(), None)


        super().save(*args, **kwargs)


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
    SOURCE_CHOICES = ((CONSUMER_APP, "Consumer App"), (CRM, "CRM"), (WEB, "Consumer Web"), (DOC_APP, "Doctor App"),
                      (DOC_WEB, "Provider Web"), (D_WEB_URL, "Doctor Web URL"), (D_TOKEN_URL, "Doctor Token URL"),
                      (IVR, "Auto IVR"))

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


    def sync_with_booking_analytics(self):
        obj = DP_StateMaster.objects.filter(StateId=self.id).first()
        if not obj:
            obj = DP_StateMaster()
            obj.CreatedOn = self.updated_at
            obj.StateId = self.id
        obj.StateName = self.name
        obj.save()

        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(MatrixMappedState),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            pass

        return obj


class MatrixMappedCity(TimeStampedModel):
    name = models.CharField(max_length=48, db_index=True)
    state = models.ForeignKey(MatrixMappedState, on_delete=models.SET_NULL, null=True, blank=True)
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="city_analytics")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'matrix_mapped_city'
        verbose_name_plural = "Matrix Mapped Cities"


    def sync_with_booking_analytics(self):
        obj = DP_CityMaster.objects.filter(CityId=self.id).first()
        if not obj:
            obj = DP_CityMaster()
            obj.CreatedOn = self.updated_at
            obj.CityId = self.id
        obj.CityName = self.name
        obj.save()

        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(MatrixMappedCity),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            pass

        return obj


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
