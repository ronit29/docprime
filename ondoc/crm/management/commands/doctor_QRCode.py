import io
import random
from io import BytesIO, StringIO

import xlrd
from django.core.files.storage import default_storage
# from reportlab.graphics import renderPDF
# from reportlab.graphics.barcode.qr import QrCodeWidget
# from reportlab.graphics.shapes import Drawing
# from reportlab.pdfgen import canvas
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
#import pandas as pd


class Command(BaseCommand):
    help = 'Create groups and setup permissions for teams'

    def handle(self, *args, **options):
        # ExcelFileName= '/home/sheryas/ID.xlsx'
        # workbook = xlrd.open_workbook(ExcelFileName)
        # worksheet = workbook.sheet_by_name("Sheet1")  # We need to read the data
        # num_rows = worksheet.nrows  # Number of Rows
        # num_cols = worksheet.ncols  # Number of Columns
        id_list = [2078, 5765, 17099, 16, 8145, 6, 54, 6412, 17120, 5849, 17310, 67, 5872, 8050, 6901, 52663, 17447, 17127, 3923, 7402, 7159, 17818, 322, 57922, 9148,
                   7153, 7057, 47, 8073, 7343, 51631, 17345, 6410, 5823, 1827,
                   17524, 45, 5753, 5833, 863, 17374, 17729, 7215, 7816, 17,
                   7053, 17454, 6187, 2195, 7559, 5796, 9345, 17469, 26, 6933,
                   7240, 6151, 1, 1471, 16766, 9302, 52, 6547, 7044, 6136, 7571,
                   916, 8272, 7231, 6587, 830, 7150, 17456, 5890,
                   9070, 8280, 1815, 17756, 7822, 7454, 6157, 7077, 323, 8077, 1024, 29, 7243, 7777,
                   5717, 56, 7549, 404, 1444, 27346, 7589, 9, 9216, 17151, 132, 6339, 6320, 6333, 1217, 7701, 7774, 7106, 7055, 5788, 1184, 5832, 6342, 15, 6494]
        result_data = []
        # data = None
        # for curr_row in range(1, num_rows):
        #     data = worksheet.cell(curr_row, 0)
        #     result_data.append(data)


        for doc in Doctor.objects.filter(id__in=id_list, is_live=True):
            if not doc.qr_code.all().exists():
                doc.generate_qr_code()
                doc.generate_sticker()









