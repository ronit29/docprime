from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management.base import BaseCommand
from ondoc.location.models import EntityLocationRelationship, EntityUrls
from ondoc.seo.models import SitemapManger
from ondoc.seo.sitemaps import get_sitemap_urls
from django.template import loader
from django.core.files import File
from io import StringIO, BytesIO
import datetime
from ondoc.articles.models import ArticleCategory
from django.template.defaultfilters import slugify


def map_sitemaps():
    available_sitemaps = EntityUrls.SitemapIdentifier.availabilities()

    for sitemap_identifier in available_sitemaps:
        sitemap_obj = get_sitemap_urls(sitemap_identifier)
        processor(sitemap_identifier, sitemap_obj)

    for category in ArticleCategory.objects.all():
        sitemap_obj = get_sitemap_urls('ARTICLES', customized_dict={'query': category.url, 'name': category.name})
        processor('ARTICLES', sitemap_obj)

    return 'Sitemap Successful'


def processor(sitemap_identifier, sitemap_obj):
    template = loader.get_template('sitemap.xml')
    filename = ''
    paginator = sitemap_obj.paginator
    for page_num in range(1, paginator.num_pages + 1):
        if sitemap_identifier == 'DOCTORS_CITY':
            filename = 'doctor-city-search'
        elif sitemap_identifier == 'DOCTORS_LOCALITY_CITY':
            filename = 'doctor-locality-search'
        elif sitemap_identifier == 'LAB_LOCALITY_CITY':
            filename = 'lab-locality-search'
        elif sitemap_identifier == 'LAB_CITY':
            filename = 'lab-city-search'
        elif sitemap_identifier == 'SPECIALIZATION_CITY':
            filename = 'specialization-city-search'
        elif sitemap_identifier == 'SPECIALIZATION_LOCALITY_CITY':
            filename = 'specialization-locality-city-search'
        elif sitemap_identifier == 'LAB_PAGE':
            filename = 'lab-profile'
        elif sitemap_identifier == 'DOCTOR_PAGE':
            filename = 'doctor-profile'
        elif sitemap_identifier == 'ARTICLES':
            filename = sitemap_obj.customized_name
        elif sitemap_identifier == 'LAB_TEST':
            filename = 'lab-test'

        filename = slugify(filename)

        count = len(sitemap_obj.get_urls())
        file = template.render({'urlset': sitemap_obj.get_urls(page_num)}).encode()
        relative_name = '%s-%s' % (filename, page_num)
        name = '%s-sitemap.xml' % (relative_name)
        string_io_obj = BytesIO()
        string_io_obj.write(file)
        string_io_obj.seek(0)

        file_obj = InMemoryUploadedFile(string_io_obj, None, name, 'text/xml',
                                  string_io_obj.tell(), None)

        print("Generating sitemap_index.xml %s" % filename)
        existing_sitemap = SitemapManger.objects.filter(file__contains=relative_name, valid=True)
        if existing_sitemap.exists():
            existing_sitemap = existing_sitemap.first()
            existing_sitemap.delete()
            # existing_sitemap.save()

        sitemap = SitemapManger(count=count, file=file_obj)
        sitemap.save()


class Command(BaseCommand):
    def handle(self, **options):
        map_sitemaps()
