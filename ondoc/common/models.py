from django.db import models
from weasyprint import HTML, CSS
import string
import random
from django.core.files.uploadedfile import SimpleUploadedFile
from weasyprint.fonts import FontConfiguration

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
        css = CSS(string=self.css)
        font_config = FontConfiguration()
        pdf_file = HTML(string=self.html).write_pdf(stylesheets=[css])
        random_string = ''.join([random.choice(string.ascii_letters + string.digits) for n in range(12)])
        name = random_string + '.pdf'
        file = SimpleUploadedFile(name, pdf_file, content_type='application/pdf')
        self.file = file
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'pdftest'
