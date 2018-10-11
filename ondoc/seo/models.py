from django.db import models
from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator
from django.core.files.storage import FileSystemStorage
from django.conf import settings
import os


class OverwriteStorage(FileSystemStorage):

    def get_available_name(self, name, max_length=256):
        if self.exists(name):
            os.remove(os.path.join(settings.MEDIA_ROOT, name))
        return name

# Create your models here.
class Sitemap(TimeStampedModel):
    file = models.FileField(upload_to='seo', validators=[FileExtensionValidator(allowed_extensions=['xml'])])

    class Meta:
        db_table = "sitemap"

# Create your models here.
class Robot(TimeStampedModel):
    file = models.FileField(upload_to='seo', validators=[FileExtensionValidator(allowed_extensions=['txt'])])

    class Meta:
        db_table = "robot"


class SitemapManger(TimeStampedModel):
    file = models.FileField(upload_to='seo', storage=OverwriteStorage(), validators=[FileExtensionValidator(allowed_extensions=['xml'])])
    count = models.PositiveIntegerField(default=0, null=True)
    valid = models.BooleanField(default=True)

    class Meta:
        db_table = "sitemap_manager"