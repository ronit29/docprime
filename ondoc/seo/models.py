from django.db import models
from django.utils.html import strip_tags

from ondoc.authentication.models import TimeStampedModel
from django.core.validators import FileExtensionValidator
from ondoc.doctor.models import PracticeSpecialization, PracticeSpecializationContent
from ondoc.diagnostic.models import LabNetwork

# Create your models here.
from ondoc.location.models import EntityUrls
from bs4 import BeautifulSoup


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
    file = models.FileField(upload_to='seo', validators=[FileExtensionValidator(allowed_extensions=['xml, gzip'])])
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
        if self.is_html_empty(self.top_content):
            self.top_content = ''
        if self.is_html_empty(self.bottom_content):
            self.bottom_content = ''
        self.top_content = self.top_content.strip("&nbsp;").strip()
        entity_to_be_used = None
        if (not self.id or not self.top_content) and self.url and self.url.url_type == EntityUrls.UrlType.SEARCHURL:
            entity_to_be_used = self.url
        if (not self.id or not self.top_content) and self.url_value:
            entity_to_be_used = EntityUrls.objects.filter(url_type=EntityUrls.UrlType.SEARCHURL, url=self.url_value,
                                                          is_valid=True).first()

        if entity_to_be_used:
            ps_content = PracticeSpecializationContent.objects.filter(
                specialization_id=entity_to_be_used.specialization_id).first()
            if ps_content:
                self.top_content = ps_content.content

        if self.url:
            self.url_value = self.url.url

        super().save(force_insert, force_update, using, update_fields)

    def is_html_empty(self, html):
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text().strip()
        if not text:
            return True
        return False
