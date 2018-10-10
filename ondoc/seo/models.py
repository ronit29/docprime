from django.db import models
from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator


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
    file = models.FileField(upload_to='seo', validators=[FileExtensionValidator(allowed_extensions=['xml'])])
    count = models.PositiveIntegerField()
    valid = models.BooleanField(default=True)

    class Meta:
        db_table = "sitemap_manager"