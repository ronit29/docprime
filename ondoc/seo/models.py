from django.db import models
from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator
from ondoc.doctor.models import PracticeSpecialization

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
    count = models.PositiveIntegerField(default=0, null=True)
    valid = models.BooleanField(default=True)

    def delete(self, *args, **kwargs):
        self.file.delete()
        super(SitemapManger, self).delete(*args, **kwargs)

    class Meta:
        db_table = "sitemap_manager"


class SeoSpecialization(TimeStampedModel):
    specialization = models.ForeignKey(PracticeSpecialization, on_delete=models.CASCADE, null=True,
                                       blank=True)
    rank = models.PositiveIntegerField(default=0, null=True)

    class Meta:
        db_table = "seo_specialization"
