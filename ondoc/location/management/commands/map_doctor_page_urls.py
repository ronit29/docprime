from django.core.management.base import BaseCommand
from ondoc.doctor.models import Doctor
from ondoc.api.v1.utils import RawSql
from ondoc.location.models import EntityUrls, DoctorPageURL


def map_doctor_urls():
    query = '''select nextval('entity_url_version_seq') as inc'''
    seq = RawSql(query,[]).fetch_all()
    if seq:
        sequence = seq[0]['inc'] if seq[0]['inc'] else 0
    else:
        sequence = 0

    all_doctors = Doctor.objects.filter(is_live=True, is_test_doctor=False).order_by('-id').all()
    for doctor in all_doctors:
        try:
            dp = DoctorPageURL(doctor, sequence)
            dp.create()
        except Exception as e:
            print(str(e))

        # success = EntityUrls.create_page_url(doctor, sequence)
        # print("success is", success)
        # if not success:
        #     print("Failed for id", doctor.id)


class Command(BaseCommand):
    def handle(self, **options):
        map_doctor_urls()
