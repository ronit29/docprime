from django.db import models
from django.utils.html import strip_tags

from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator
from ondoc.doctor.models import PracticeSpecialization, PracticeSpecializationContent
from ondoc.diagnostic.models import LabNetwork

# Create your models here.
from ondoc.location.models import EntityUrls


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


class SeoLabNetwork(TimeStampedModel):
    lab_network = models.ForeignKey(LabNetwork, on_delete=models.CASCADE, null=False, blank=True)
    rank = models.PositiveIntegerField(default=0, null=True)

    class Meta:
        db_table = "seo_lab_network"



class NewDynamic(TimeStampedModel):
    top_content = models.TextField(null=False, blank=True)
    bottom_content = models.TextField(null=False, blank=True)
    url = models.ForeignKey(EntityUrls, on_delete=models.DO_NOTHING, null=True, blank=True, db_constraint=False)
    url_value = models.TextField(null=False, blank=True)
    is_enabled = models.BooleanField(default=False)
    meta_title = models.CharField(max_length=5000, default='', blank=True)
    meta_description = models.CharField(max_length=5000, default='', blank=True)
    class Meta:
        db_table = "dynamic_url_content"

    def save(self, force_insert=False, force_update=False, using=None, update_fields=None):
        if not self.id:
            if not strip_tags(self.top_content).strip("&nbsp;").strip():
                if self.url.url_type == EntityUrls.UrlType.SEARCHURL and PracticeSpecializationContent.objects.filter(
                        specialization_id=self.url.specialization_id):
                    self.top_content = PracticeSpecializationContent.objects.filter(
                        specialization_id=self.url.specialization_id).first().content
        if self.url:
            self.url_value = self.url.url
        super().save(force_insert, force_update, using, update_fields)

