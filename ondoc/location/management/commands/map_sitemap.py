from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from ondoc.seo.models import Sitemap
from ondoc.seo.sitemaps import get_sitemap_urls
from django.template import loader


def map_sitemaps():
    for sitemap_identifier in EntityUrls.SitemapIdentifier.availabilities():
        aa = get_sitemap_urls(sitemap_identifier)
        template = loader.get_template('sitemap.xml')
        file = template.render({'urlset': aa})
        print("success for ", sitemap_identifier)

class Command(BaseCommand):
    def handle(self, **options):
        map_sitemaps()
