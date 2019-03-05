import io
import random
from io import BytesIO, StringIO

import xlrd
from django.core.files.storage import default_storage
from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.pdfgen import canvas
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.management.base import BaseCommand
import qrcode
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponse
from django.utils import timezone
from PIL import Image
from PIL import ImageFont
from PIL import ImageDraw
from ondoc.common.models import QRCode
from ondoc.doctor.models import Doctor, DoctorImage
import pandas as pd


class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'

    def handle(self, *args, **options):
        ExcelFileName= '/home/sheryas/ID.xlsx'
        workbook = xlrd.open_workbook(ExcelFileName)
        worksheet = workbook.sheet_by_name("Sheet1")  # We need to read the data
        num_rows = worksheet.nrows  # Number of Rows
        num_cols = worksheet.ncols  # Number of Columns
        result_data = []
        data = None
        row_data = []
        for curr_row in range(1, num_rows):
            data = worksheet.cell(curr_row, 0)
            result_data.append(data)
        for item in result_data:
            doctor_id = item.value
            doc = Doctor.objects.filter(id=2, is_live=True).first()
            if doc:
                qr_code = doc.generate_qr_code()
                # for qr in doc.qr_code.all():
                #     object = qr
                #     if object:
                doc.generate_sticker()




        # for curr_col in range(0, num_cols):
        #     data = worksheet.cell_value(curr_row, curr_col)  # Read the data in the current cell
        #     # print(data)
        #     # row_data.append(data)
        # result_data.append(row_data)






















#         response = HttpResponse(content_type='application/pdf')
#         response['Content-Disposition'] = 'attachment; filename="egzamin.pdf"'
#         p = canvas.Canvas(response)
#         for doc in Doctor.objects.filter(is_live=True)[:10]:
#             temp_url = settings.BASE_URL + "/opd/doctor/{}".format(doc.id)
#             name = doc.name
#             doc_info = doc.raw_about
#             image = doc.images.first()
#
#             if not image:
#                 print('image not found')
#
#
#             img = qrcode.make(temp_url)
#             tempfile_io = BytesIO()
#             img.save(tempfile_io, format='JPEG')
#             filename = "qrcode_{}_{}.jpeg".format(str(timezone.now().strftime("%I%M%S_%d%m%Y")),
#                                                   random.randint(1111111111, 9999999999))
#             image_file1 = InMemoryUploadedFile(tempfile_io, None, name=filename, content_type='image/jpeg', size=10000, charset=None)
#             QRCode_object = QRCode(name=image_file1, content_type=ContentType.objects.get_for_model(Doctor), object_id=doc.id)
#             QRCode_object.save()
#
# # Converting text into image
#
#             doc_text = Image.new('RGB', (200, 100))
#             draw = ImageDraw.Draw(doc_text)
#             draw.text((20, 20), name , fill=(30, 47, 0))
#             s = BytesIO()
#             doc_text.save(s, format='JPEG')
#             # in_memory_file = s.getvalue()
#             filename2 = "doc_text_{}_{}.jpeg".format(str(timezone.now().strftime("%I%M%S_%d%m%Y")),
#                                                   random.randint(1111111111, 9999999999))
#             image_file2 = InMemoryUploadedFile(s, None, name=filename2, content_type='image2/jpeg', size=10000,
#                                                charset=None)
#             path = default_storage.save(filename2, ContentFile(image_file2.read()))
#             # QRCode_object2 = QRCode(name=image_file2, content_type=ContentType.objects.get_for_model(Doctor), object_id=doc.id)
#             # QRCode_object2.save()







