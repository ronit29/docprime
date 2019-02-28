from django.contrib.postgres.fields import JSONField
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from ondoc.authentication.models import TimeStampedModel
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment
from ondoc.authentication.models import User


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
    SOURCE_CHOICES = ((CONSUMER_APP, "Consumer App"), (CRM, "CRM"), (WEB, "Web"), (DOC_APP, "Doctor App"))
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
    DOCTOR = "doctor"
    LAB = "lab"
    BOOKING_TYPE_CHOICES = ((DOCTOR, "Doctor Clinic"), (LAB, "Lab"))
    booking_type = models.CharField(max_length=20, blank=True, choices=BOOKING_TYPE_CHOICES, default='')
    start_date = models.DateField(null=False)
    end_date = models.DateField(null=False)
    start_time = models.TimeField(null=False)
    end_time = models.TimeField(null=False)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'global_non_bookable_timing'


class Feature(TimeStampedModel):
    icon = models.ImageField('Feature image', upload_to='feature/images')
    name = models.CharField(max_length=100)

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