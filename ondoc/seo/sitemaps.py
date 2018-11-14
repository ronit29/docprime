from ondoc.articles.models import ArticleCategory
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
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.SPECIALIZATION_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url

    def lastmod(self, obj):
        return datetime.datetime(2018, 11, 12, hour=2, minute=10, second=0, microsecond=0)




class SpecializationCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.SPECIALIZATION_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


class DoctorLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTORS_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


class DoctorCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTORS_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


class DoctorPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.DOCTOR_PAGE)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


class LabLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


class LabCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_CITY).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


class LabPageSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.LAB_PAGE).order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


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

}


def get_sitemap_urls(sitemap_identifier, customized_dict=None):
    sitemap_class = sitemap_identifier_mapping[sitemap_identifier]
    sitemap_obj = sitemap_class()
    sitemap_obj.protocol = 'https'
    if sitemap_identifier == 'ARTICLES':
        sitemap_obj.customized_query = customized_dict['query']
        sitemap_obj.customized_name = customized_dict['name']
    return sitemap_obj
