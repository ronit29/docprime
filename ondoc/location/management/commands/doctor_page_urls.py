from django.core.management import BaseCommand
from django.template.defaultfilters import slugify
from ondoc.api.v1.utils import RawSql
from ondoc.doctor.models import Doctor, DoctorPracticeSpecialization, Hospital, PracticeSpecialization
from ondoc.location.models import DoctorPageURL, EntityUrls
from django.contrib.gis.geos import Point
from django.db.models import Prefetch


def doctor_page_urls():
    from ondoc.diagnostic.models import Lab
    Lab.update_labs_seo_urls()
    # query = '''select nextval('entity_url_version_seq') as inc'''
    # seq = RawSql(query,[]).fetch_all()

    # #if seq:
    # sequence = seq[0]['inc']

    # if seq:
    #     sequence = seq[0]['inc'] if seq[0]['inc'] else 0
    # else:
    #     sequence = 0

    # doc_obj = Doctor.objects.prefetch_related(Prefetch('doctorpracticespecializations',
    #         queryset=DoctorPracticeSpecialization.objects.prefetch_related(
    #         Prefetch('specialization', queryset=PracticeSpecialization.objects.all())).order_by('id')),
    #         (Prefetch('hospitals', queryset=Hospital.objects.filter(is_live=True).order_by('hospital_type', 'id')))
    #          ).filter(is_live=True, is_test_doctor=False)

    # doc_obj =Doctor.objects.prefetch_related('doctorpracticespecializations', 'doctorpracticespecializations__specialization',
    #                                     (Prefetch('hospitals', queryset=Hospital.objects.filter(is_live=True).order_by('hospital_type', 'id')))
    #                                      ).filter(is_live=True, is_test_doctor=False).order_by('id')


    #     try:
    # DoctorPageURL.create_doctor_page_urls()
    # for doctor in doc_obj:
    #     status = DoctorPageURL.create_doctor_page_urls(doctor,sequence)
        
    # EntityUrls.objects.filter(sitemap_identifier='DOCTOR_PAGE', sequence__lt=sequence).update(is_valid=False)

        # except Exception as e:
        #     print("failure: " + str(doctor.id) + ", error: " + str(e))


class Command(BaseCommand):
    def handle(self, **options):
        doctor_page_urls()