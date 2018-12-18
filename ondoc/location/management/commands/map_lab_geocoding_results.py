from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import GeocodingResults
from ondoc.api.v1.utils import RawSql


def map_lab_geocoding_results():

    lab_object = Lab.objects.first()
    query = "select id, st_x(location::geometry)::text lng , st_y(location::geometry)::text lat from lab where location is not null and is_live=true";

    all_labs = RawSql(query, []).fetch_all()


    print("Attempting for lab.", len(all_labs))

    for lab in all_labs:
        print(lab)
        print(GeocodingResults.get_or_create(latitude=lab.get('lat'), longitude=lab.get('lng'), content_object=lab_object), 'lab_id: ',lab.get('id'))


class Command(BaseCommand):
    def handle(self, **options):
        map_lab_geocoding_results()