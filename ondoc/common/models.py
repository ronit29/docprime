from django.contrib.postgres.fields import JSONField
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
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from ondoc.authentication.models import TimeStampedModel
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment


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
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    status = models.PositiveSmallIntegerField(null=False)

    @classmethod
    def create(cls, *args, **kwargs):
        obj = kwargs.get('content_object')
        if not obj:
            raise Exception('Function accept content_object in **kwargs')

        content_type = ContentType.objects.get_for_model(obj)
        cls(content_type=content_type, object_id=obj.id, status=obj.status).save()


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
            queryset = queryset.filter(id=pg_specific_coupon.payment_option.id)

        return cls.build_payment_option(queryset)

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
