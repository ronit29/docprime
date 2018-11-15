from django.db import models
from ondoc.authentication.models import TimeStampedModel
from .tasks import fetch_and_upload_json
from django.core.validators import FileExtensionValidator

# Create your models here.


class DemoElastic(TimeStampedModel):
    file = models.FileField(upload_to='demoelastic', validators=[FileExtensionValidator(allowed_extensions=['json'])],
                            null=True, blank=True, default='')
    path = models.CharField(max_length=200, default=None, null=True, blank=True)

    def save(self, *args, **kwargs):
        to_be_uploaded = self.id is None
        super(DemoElastic, self).save(*args, **kwargs)

        if to_be_uploaded:
            fetch_and_upload_json.apply_async(({'id': self.id}, ), countdown=5)

    class Meta:
        db_table = "demo_elastic"
