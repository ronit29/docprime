from django.contrib.postgres.fields import JSONField
from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from ondoc.authentication.models import TimeStampedModel
# from ondoc.doctor.models import OpdAppointment
# from ondoc.diagnostic.models import LabAppointment
from ondoc.authentication import models as auth_model


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

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'payment_options'


class UserConfig(TimeStampedModel):
    key = models.CharField(max_length=500, unique=True)
    data = JSONField(blank=True, null=True)

    class Meta:
        db_table = 'user_config'


class Remark(auth_model.TimeStampedModel):
    content_type = models.ForeignKey(ContentType, on_delete=models.DO_NOTHING)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    user = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True)
    content = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'remark'