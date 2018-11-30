from django.db import models
from weasyprint import HTML, CSS
import string
import random
from django.core.files.uploadedfile import SimpleUploadedFile, InMemoryUploadedFile
from weasyprint.fonts import FontConfiguration
from hardcopy import bytestring_to_pdf
import io
#from tempfile import NamedTemporaryFile
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.core.files import File
from io import BytesIO

class Cities(models.Model):
    name = models.CharField(max_length=48, db_index=True)

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'cities'


class MatrixCityMapping(models.Model):
    city_id = models.PositiveIntegerField()
    name = models.CharField(max_length=48, db_index=True)

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = 'matrix_city_mapping'


class PDFTester(models.Model):
    html = models.TextField(max_length=50000000)
    css = models.TextField(max_length=50000000, blank=True)
    file = models.FileField(upload_to='common/pdf/test', blank=True)

    def save(self, *args, **kwargs):

        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        path = 'common/pdf/test/' + random_string + '.pdf'
        file = default_storage.open(path, 'wb')

        extra_args = {
            'virtual-time-budget': 6000
        }

        bytestring_to_pdf(self.html.encode(), file, **extra_args)

        file.close()

        ff = File(default_storage.open(path, 'rb'))

        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        name = random_string+'.pdf'

        self.file = InMemoryUploadedFile(ff.file, None, 'aaa.pdf', 'application/pdf', ff.file.tell(), None)


        super().save(*args, **kwargs)


    class Meta:
        db_table = 'pdftest'
