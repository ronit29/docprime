from django.core.management.base import BaseCommand
from ondoc.doctor.models import DoctorImage, Doctor, SourceIdentifier
from django.core.files.storage import default_storage
import time
class Command(BaseCommand):
    help = 'Upload doctor images'

    def handle(self, *args, **options):

        doctors = Doctor.objects.prefetch_related('images').filter(source='pr').order_by('created_by')
        for doc in doctors:

            if not doc.images.exists():

                si = SourceIdentifier.objects.filter(type=SourceIdentifier.DOCTOR, reference_id=doc.id).first()
                if si:
                    path = 'temp/verified/' + si.unique_identifier + '.jpg'

                    if default_storage.exists(path):

                        file = default_storage.open(path, 'rb')
                        DoctorImage.objects.create(doctor=doc, name=file)

