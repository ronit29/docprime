from django.core.management.base import BaseCommand

from ondoc.insurance.models import UserInsurance
from django.db import transaction
import uuid, requests
from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile



class Command(BaseCommand):

    help = 'Rename Insurance COI files!'

    @transaction.atomic
    def handle(self, *args, **options):
        queryset = UserInsurance.objects.all()
        for data in queryset:
            if data.coi:
                file_path = data.coi.url
                request = requests.get(file_path, stream=True)
                if request.status_code != requests.codes.ok:
                    continue
                file_name = file_path.split('/')[-1]
                splited = file_name.split('.')
                splited = splited[0]
                file_name = str(splited) + '-' + str(uuid.uuid4().hex) + '.' + str(splited[-1])
                temp_file = TemporaryUploadedFile(file_name, 'byte', 1000, 'utf-8')
                for block in request.iter_content(1024 * 8):
                    if not block:
                        break
                    temp_file.write(block)
                data.coi = InMemoryUploadedFile(temp_file, None, file_name, 'application/pdf', temp_file.tell(), None)
                data.save()


