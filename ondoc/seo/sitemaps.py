from ondoc.location.models import EntityUrls
from django.contrib.sitemaps import Sitemap
from django.conf import settings


class SpecializationLocalityCitySitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.SPECIALIZATION_LOCALITY_CITY)\
            .order_by('created_at')

    def location(self, obj):
        return "/%s" % obj.url


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


sitemap_identifier_mapping = {
    'SPECIALIZATION_LOCALITY_CITY': SpecializationLocalityCitySitemap,
    'SPECIALIZATION_CITY': SpecializationCitySitemap,
    'DOCTORS_LOCALITY_CITY': DoctorLocalityCitySitemap,
    'DOCTORS_CITY': DoctorCitySitemap,
    'DOCTOR_PAGE': DoctorPageSitemap,
    'LAB_LOCALITY_CITY': LabLocalityCitySitemap,
    'LAB_CITY': LabCitySitemap,
    'LAB_PAGE': LabPageSitemap
}


def get_sitemap_urls(sitemap_identifier):
    sitemap_class = sitemap_identifier_mapping[sitemap_identifier]
    sitemap_obj = sitemap_class()
    sitemap_obj.protocol = 'https'
    return sitemap_obj
