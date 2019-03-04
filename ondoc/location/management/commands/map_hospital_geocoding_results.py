from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.location.models import  GeocodingResults
from ondoc.api.v1.utils import RawSql


def map_hospital_geocoding_results():

    #hospital_object = Hospital.objects.first()

    query = "select id, st_x(location::geometry)::text lng , st_y(location::geometry)::text lat from hospital where location is not null and is_live=true order by id desc";

    all_hospitals = RawSql(query, []).fetch_all()

    print("Attempting for hospital. ", len(all_hospitals))

    for hospital in all_hospitals:
        response = GeocodingResults.create_results(latitude=hospital.get('lat'), longitude=hospital.get('lng'), id=hospital.get('id'), type='hospital')
        #print(response)


class Command(BaseCommand):
    def handle(self, **options):
        map_hospital_geocoding_results()