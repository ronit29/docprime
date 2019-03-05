from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import GeocodingResults
from ondoc.api.v1.utils import RawSql


def map_lab_geocoding_results():

    # lab_object = Lab.objects.first()
    query = "select id, st_x(location::geometry)::text lng , st_y(location::geometry)::text lat from lab where location is not null and is_live=true order by id desc";

    all_labs = RawSql(query, []).fetch_all()


    print("Attempting for lab.", len(all_labs))

    for lab in all_labs:
        print(lab)
        print(GeocodingResults.create_results(latitude=lab.get('lat'), longitude=lab.get('lng'), id=lab.get('id'), type='lab'))


class Command(BaseCommand):
    def handle(self, **options):
        map_lab_geocoding_results()