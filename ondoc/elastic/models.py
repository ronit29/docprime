from django.db import models
from ondoc.authentication.models import TimeStampedModel
from .tasks import fetch_and_upload_json
from django.core.validators import FileExtensionValidator

# Create your models here.


class DemoElastic(TimeStampedModel):
    file = models.FileField(upload_to='demoelastic', validators=[FileExtensionValidator(allowed_extensions=['json'])],
                            null=True, blank=True, default='')
    query = models.TextField(null=True, blank=False)
    mongo_database = models.CharField(max_length=100, null=True, blank=True)
    mongo_collection = models.CharField(max_length=100, null=True, blank=True)
    mongo_connection_string = models.CharField(max_length=200, default='', null=False, blank=True)

    def save(self, *args, **kwargs):
        super(DemoElastic, self).save(*args, **kwargs)

        # fetch_and_upload_json.apply_async(({'id': self.id}, ), countdown=5)

    class Meta:
        db_table = "demo_elastic"
