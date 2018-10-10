from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from ondoc.seo.models import SitemapManger
from ondoc.seo.sitemaps import get_sitemap_urls
from django.template import loader
from django.core.files import File
from io import StringIO


def map_sitemaps():
    for sitemap_identifier in EntityUrls.SitemapIdentifier.availabilities():
        sitemap_obj = get_sitemap_urls(sitemap_identifier)
        template = loader.get_template('sitemap.xml')

        paginator = sitemap_obj.paginator
        for page_num in range(1, paginator.num_pages + 1):
            if sitemap_identifier == 'DOCTORS_CITY':
                filename = 'doctor-city'
            if sitemap_identifier == 'DOCTORS_LOCALITY_CITY':
                filename = 'doctor-locality'
            if sitemap_identifier == 'LAB_LOCALITY_CITY':
                filename = 'lab-locality'
            if sitemap_identifier == 'LAB_CITY':
                filename = 'lab-city'
            if sitemap_identifier == 'SPECIALIZATION_CITY':
                filename = 'specialization-city'
            if sitemap_identifier == 'SPECIALIZATION_LOCALITY_CITY':
                filename = 'specialization-locality-city'
            if sitemap_identifier == 'LAB_PAGE':
                filename = 'lab-profile'
            if sitemap_identifier == 'DOCTOR_PAGE':
                filename = 'doctor-profile'

            count = len(sitemap_obj.get_urls())
            file = template.render({'urlset': sitemap_obj.get_urls(page_num)})

            string_io_obj = StringIO()
            string_io_obj.write(file)
            string_io_obj.seek(0)
            print("Generating sitemap_index.xml %s" % name)
            # name.write(file)
            sitemap = SitemapManger.objects.create(count=count, file=File(string_io_obj,
                                                                          name='%s-search%s-sitemap.xml'
                                                                               % (filename, page_num)))
            sitemap.save()

    return 'Sitemap Successful'


class Command(BaseCommand):
    def handle(self, **options):
        map_sitemaps()
