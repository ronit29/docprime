from ondoc.location.models import EntityUrls
from django.contrib.sitemaps import Sitemap
from django.conf import settings


class EntityUrlSitemap(Sitemap):
    changefreq = "weekly"
    priority = 1

    def items(self):
        return EntityUrls.objects.all()

    def location(self, obj):
        return "/%s" %(obj.url)


def get_sitemap_urls(sitemap_identifier):
    aa = EntityUrlSitemap()
    aa.protocol = 'https'
    return aa.get_urls()