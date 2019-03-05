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
        for curr_row in range(1, num_rows):
            data = worksheet.cell(curr_row, 0)
            result_data.append(data)
        for item in result_data:
            doctor_id = item.value
            doc = Doctor.objects.filter(id=doctor_id, is_live=True).first()
            if doc:
                doc.generate_qr_code()
                doc.generate_sticker()










