from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from ondoc.seo.models import SitemapManger
from ondoc.seo.sitemaps import get_sitemap_urls
from django.template import loader
from django.core.files import File


def map_sitemaps():
    for sitemap_identifier in EntityUrls.SitemapIdentifier.availabilities():
        sitemap_obj = get_sitemap_urls(sitemap_identifier)
        template = loader.get_template('sitemap.xml')

        paginator = sitemap_obj.paginator
        for page_num in range(1, paginator.num_pages + 1):
            filename = 'sitemap_%s.xml' % page_num
            count = len(sitemap_obj.get_urls())
            file = template.render({'urlset': sitemap_obj.get_urls(page_num)})

            name = 'filename_%s.xml' % sitemap_identifier
            with open(name, 'w') as name:
                print("Generating sitemap_index.xml %s" % name)
                name.write(file)
                sitemap = SitemapManger.objects.create(count=count, file=File(name))



            #     name.close()
            #     file1 = File(name)
            #     file1.readable()
            #     file1.close()
            #     # sitemap_file = SitemapManger.objects.create(count=count, file=file)
            #
            #     sitemap_file = SitemapManger.objects.create()
            #     sitemap_file.count = count
            #     sitemap_file.file = file1
            #     # sitemap_file.save()
            #     # sitemap_file = SitemapManger(file=name, count=count)
            #     sitemap_file.save()
        return 'Sitemap successful'


class Command(BaseCommand):
    def handle(self, **options):
        map_sitemaps()
