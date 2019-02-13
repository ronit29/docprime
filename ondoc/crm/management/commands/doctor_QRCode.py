import io
import random
from io import BytesIO, StringIO
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management.base import BaseCommand
import qrcode
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from ondoc.common.models import QRCode
from ondoc.doctor.models import Doctor

class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'

    def handle(self, *args, **options):
        for doc in Doctor.objects.all()[:10]:
            temp_url = settings.BASE_URL + "/opd/doctor/{}".format(doc.id)
            img = qrcode.make(temp_url)
            tempfile_io = BytesIO()
            img.save(tempfile_io, format='JPEG')
            filename = "qrcode_{}_{}.jpeg".format(str(timezone.now().strftime("%I%M%S_%d%m%Y")),
                                                  random.randint(1111111111, 9999999999))
            image_file = InMemoryUploadedFile(tempfile_io, None, name=filename, content_type='image/jpeg', size=10000, charset=None)
            # thumb_io = BytesIO()
            # img.save(thumb_io, format='JPEG')
            # bw = io.TextIOWrapper(thumb_io)
            # f2 = ContentFile(thumb_io)
            # thumb_file = InMemoryUploadedFile(thumb_io, None, 'foo.jpg', 'image/jpeg', thumb_size, None)
            QRCode_object = QRCode(name=image_file, content_type=ContentType.objects.get_for_model(Doctor), object_id=doc.id)
            QRCode_object.save()

            # group.permissions.add(*permissions)





