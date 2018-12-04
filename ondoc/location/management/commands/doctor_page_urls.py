from django.core.management import BaseCommand
from django.template.defaultfilters import slugify
from ondoc.api.v1.utils import RawSql
from ondoc.doctor.models import Doctor, DoctorPracticeSpecialization
from ondoc.location.models import DoctorPageURL, EntityUrls
from django.contrib.gis.geos import Point


def doctor_page_urls():
    query = '''select nextval('entity_url_version_seq') as inc'''
    seq = RawSql(query,[]).fetch_all()
    if seq:
        sequence = seq[0]['inc'] if seq[0]['inc'] else 0
    else:
        sequence = 0

    doc_obj =Doctor.objects.prefetch_related('doctorpracticespecializations', 'doctorpracticespecializations__specialization').filter(is_live=True, is_test_doctor=False)[:10]
    for doctor in doc_obj:
        try:
            dp = DoctorPageURL(doctor, sequence)
            dp.create_page_urls()
        except Exception as e:
            print(str(e))


class Command(BaseCommand):
    def handle(self, **options):
        doctor_page_urls()