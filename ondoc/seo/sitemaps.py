from ondoc.articles.models import ArticleCategory
from ondoc.diagnostic.models import Lab
from ondoc.doctor.models import Doctor, Hospital
from ondoc.location.models import EntityUrls
from django.contrib.sitemaps import Sitemap
from ondoc.seo.models import SitemapManger
from django.conf import settings
import datetime

class IndexSitemap(Sitemap):
    def __init__(self):
        self.protocol = 'https'

    def items(self):
        return SitemapManger.objects.filter(valid=True)

    def lastmod(self, obj):
        return obj.created_at

    def location(self, obj):
        partial_url_path_list = obj.file.url.split('/')
        return '/%s' % partial_url_path_list[len(partial_url_path_list)-1]


class SpecializationLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.SPECIALIZATION_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)




class SpecializationCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.SPECIALIZATION_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class DoctorLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTORS_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class DoctorCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTORS_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class DoctorPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        doctor_ids = Doctor.objects.filter(is_live=True).values_list('id', flat=True)
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE, entity_id__in=doctor_ids)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class LabLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class LabCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class LabPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        lab_ids = Lab.objects.filter(is_live=True).values_list('id', flat=True)
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE, entity_id__in=lab_ids).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class ArticleSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        qs = ArticleCategory.objects.filter(url=self.customized_query).order_by('id')
        if not qs.exists():
            return []

        return qs.first().articles.filter(is_published=True).order_by('id')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return obj.updated_at


class LabTestSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_TEST).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class HospitalPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        hosp_ids = Hospital.objects.filter(is_live=True).values_list('id', flat=True)
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE, entity_id__in=hosp_ids).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class HospitalLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITALS_LOCALITY_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class HospitalCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITALS_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class IpdProcedureCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.IPD_PROCEDURE_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class IpdProcedureHospitalCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.IPD_PROCEDURE_HOSPITAL_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


class IpdProcedureDoctorCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(is_valid=True, sitemap_identifier=EntityUrls.SitemapIdentifier.IPD_PROCEDURE_DOCTOR_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime.today() - datetime.timedelta(days=datetime.datetime.today().isoweekday() % 7)


sitemap_identifier_mapping = {
    'SPECIALIZATION_LOCALITY_CITY': SpecializationLocalityCitySitemap,
    'SPECIALIZATION_CITY': SpecializationCitySitemap,
    'DOCTORS_LOCALITY_CITY': DoctorLocalityCitySitemap,
    'DOCTORS_CITY': DoctorCitySitemap,
    'DOCTOR_PAGE': DoctorPageSitemap,
    'LAB_LOCALITY_CITY': LabLocalityCitySitemap,
    'LAB_CITY': LabCitySitemap,
    'LAB_PAGE': LabPageSitemap,
    'ARTICLES': ArticleSitemap,
    'LAB_TEST': LabTestSitemap,

    'HOSPITAL_PAGE': HospitalPageSitemap,
    'HOSPITALS_LOCALITY_CITY': HospitalLocalityCitySitemap,
    'HOSPITALS_CITY': HospitalCitySitemap,
    'IPD_PROCEDURE_CITY': IpdProcedureCitySitemap,
    'IPD_PROCEDURE_HOSPITAL_CITY': IpdProcedureHospitalCitySitemap,
    'IPD_PROCEDURE_DOCTOR_CITY': IpdProcedureDoctorCitySitemap,

}


def get_sitemap_urls(sitemap_identifier, customized_dict=None):
    if sitemap_identifier_mapping.get(sitemap_identifier):
        sitemap_class = sitemap_identifier_mapping[sitemap_identifier]
        sitemap_obj = sitemap_class()
        sitemap_obj.protocol = 'https'
        if sitemap_identifier == 'ARTICLES':
            sitemap_obj.customized_query = customized_dict['query']
            sitemap_obj.customized_name = customized_dict['name']
        return sitemap_obj
