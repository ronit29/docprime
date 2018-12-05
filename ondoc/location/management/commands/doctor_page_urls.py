from django.core.management import BaseCommand
from django.template.defaultfilters import slugify
from ondoc.api.v1.utils import RawSql
from ondoc.doctor.models import Doctor, DoctorPracticeSpecialization, Hospital
from ondoc.location.models import DoctorPageURL, EntityUrls
from django.contrib.gis.geos import Point
from django.db.models import Prefetch


def doctor_page_urls():
    query = '''select nextval('entity_url_version_seq') as inc'''
    seq = RawSql(query,[]).fetch_all()
    if seq:
        sequence = seq[0]['inc'] if seq[0]['inc'] else 0
    else:
        sequence = 0

    doc_obj =Doctor.objects.prefetch_related('doctorpracticespecializations', 'doctorpracticespecializations__specialization',
                                        (Prefetch('hospitals', queryset=Hospital.objects.filter(is_live=True).order_by('hospital_type', 'id')))
                                         ).filter(is_live=True, is_test_doctor=False)

    for doctor in doc_obj:
        try:
            print(DoctorPageURL.create_page_urls(doctor,sequence))
        except Exception as e:
            print(str(e))


class Command(BaseCommand):
    def handle(self, **options):
        doctor_page_urls()