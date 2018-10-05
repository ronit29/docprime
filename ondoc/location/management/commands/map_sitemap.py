
from django.core.management.base import BaseCommand
from django.core.paginator import Paginator

from ondoc.location.models import EntityLocationRelationship, EntityUrls
from ondoc.seo.models import Sitemap
from ondoc.seo.sitemaps import get_sitemap_urls
from django.template import loader


def map_sitemaps():
    for sitemap_identifier in EntityUrls.SitemapIdentifier.availabilities():
        sitemap_obj = get_sitemap_urls(sitemap_identifier)
        template = loader.get_template('sitemap.xml')

        paginator = sitemap_obj.paginator
        file = None

        for page_num in range(1, paginator.num_pages + 1):
            filename = 'sitemap_%s.xml' % page_num
            file = template.render({'urlset': sitemap_obj.get_urls(page_num)})

        name = 'filename_%s' % sitemap_identifier

        with open(name, 'w') as name:
            print("Generating sitemap_index.xml %s" % name)
            # name.write(loader.render_to_string('name.xml', {'sitemaps': sitemap_obj.get_urls()}))
            name.write(file)


        print("success for ", sitemap_identifier)


class Command(BaseCommand):
    def handle(self, **options):
        map_sitemaps()
