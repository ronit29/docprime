from django.core.management.base import BaseCommand
from ondoc.doctor.models import Hospital
from ondoc.location.models import  GeocodingResults
from ondoc.api.v1.utils import RawSql


def map_hospital_geocoding_results():

    hospital_object = Hospital.objects.first()

    query = "select id, st_x(location::geometry)::text lng , st_y(location::geometry)::text lat from hospital where location is not null and is_live=true and id in (select hospital_id from doctor_clinic where doctor_id in (select id from doctor where is_live=true order by id limit 100) ) order by id limit 100";

    all_hospitals = RawSql(query, []).fetch_all()

    print("Attempting for hospital. ", len(all_hospitals))

    for hospital in all_hospitals:
        print(GeocodingResults.get_or_create(latitude=hospital.get('lat'), longitude=hospital.get('lng'), content_object=hospital_object), 'hospital_id: ', hospital.get('id'))


class Command(BaseCommand):
    def handle(self, **options):
        map_hospital_geocoding_results()