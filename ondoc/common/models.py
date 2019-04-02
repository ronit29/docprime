from django.contrib.postgres.fields import JSONField
from django.core.validators import FileExtensionValidator
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType

from ondoc.authentication.models import TimeStampedModel
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment
from ondoc.authentication.models import User
from ondoc.authentication import models as auth_model
from ondoc.bookinganalytics.models import DP_StateMaster, DP_CityMaster


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


class AppointmentHistory(TimeStampedModel):
    CRM = "crm"
    WEB = "web"
    DOC_APP = "d_app"
    CONSUMER_APP = "c_app"
    DOC_WEB = "d_web"
    SOURCE_CHOICES = ((CONSUMER_APP, "Consumer App"), (CRM, "CRM"), (WEB, "Consumer Web"), (DOC_APP, "Doctor App"), (DOC_WEB, "Provider Web"))
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    status = models.PositiveSmallIntegerField(null=False)
    user = models.ForeignKey(User, null=True, default=None, on_delete=models.CASCADE)
    source = models.CharField(max_length=10, blank=True, choices=SOURCE_CHOICES, default='')

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
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey()
    synced_at = models.DateTimeField(auto_now_add=True, null=True)
    last_updated_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        db_table = "sync_booking_analytics"


class MatrixMappedState(TimeStampedModel):
    name = models.CharField(max_length=48, db_index=True)
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="state_analytics")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'matrix_mapped_state'
        verbose_name_plural = "Matrix Mapped States"


    def sync_with_booking_analytics(self, sync_entry=None):
        obj = DP_StateMaster.objects.filter(StateId=self.id).first()
        if not obj:
            obj = DP_StateMaster()
            obj.CreatedOn = self.updated_at
            obj.StateId = self.id
        obj.StateName = self.name
        obj.save()
        if sync_entry:
            sync_entry.synced_at = self.updated_at
            sync_entry.last_updated_at = self.updated_at
            sync_entry.save()
        else:
            sync_analytics_object = SyncBookingAnalytics(synced_at=self.updated_at,
                                                         last_updated_at=self.updated_at,
                                                         content_type=ContentType.objects.get_for_model(MatrixMappedState),
                                                         object_id=self.id)
            sync_analytics_object.save()

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


    def sync_with_booking_analytics(self, sync_entry=None):
        obj = DP_CityMaster.objects.filter(CityId=self.id).first()
        if not obj:
            obj = DP_CityMaster()
            obj.CreatedOn = self.updated_at
            obj.CityId = self.id
        obj.CityName = self.name
        obj.save()

        if sync_entry:
            sync_entry.synced_at = self.updated_at
            sync_entry.last_updated_at = self.updated_at
            sync_entry.save()
        else:
            sync_analytics_object = SyncBookingAnalytics(synced_at=self.updated_at,
                                                         last_updated_at=self.updated_at,
                                                         content_type=ContentType.objects.get_for_model(MatrixMappedCity),
                                                         object_id=self.id)
            sync_analytics_object.save()

        return obj


class QRCode(TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True)
    object_id = models.PositiveIntegerField(null=True)
    content_object = GenericForeignKey()
    name = models.FileField(upload_to='qrcode', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])
    # name = models.ImageField(upload_to='qrcode', blank=True, null=True)

    class Meta:
        db_table = 'qr_code'

