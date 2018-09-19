from django.db import models
from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator

# Create your models here.
class Sitemap(TimeStampedModel):
    file = models.FileField(upload_to='seo', validators=[FileExtensionValidator(allowed_extensions=['xml'])])

    class Meta:
        db_table = "sitemap"
