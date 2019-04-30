from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from ondoc.authentication import models as auth_model
from ondoc.authentication.models import TimeStampedModel, Document
from ondoc.common.models import MatrixMappedCity, MatrixMappedState


class CorporateBooking(auth_model.TimeStampedModel):
    corporate_name = models.CharField(max_length=1000, default='')
    matrix_city = models.ForeignKey(MatrixMappedCity, on_delete=models.CASCADE, default='', related_name='citymatrix')
    matrix_state = models.ForeignKey(MatrixMappedState, on_delete=models.CASCADE, default='',
                                     related_name='statematrix')
    corporate_address = models.CharField(max_length=1000, null=True, blank=True)
    locality = models.CharField(max_length=1000, null=True, blank=True)
    sublocality = models.CharField(max_length=1000, null=True, blank=True)
    PIN = models.BigIntegerField(null=True, blank=True, verbose_name='PIN Code')
    pan_no = models.CharField(max_length=10000, default='', verbose_name='PAN no.')
    gst_no = models.CharField(max_length=10000, default='', verbose_name='GST no.')

    def __str__(self):
        return "{}".format(self.corporate_name)

    class Meta:
        db_table = 'corporate_booking'


class CorporateDeal(auth_model.TimeStampedModel):
    corporate_id = models.ForeignKey(CorporateBooking, on_delete=models.CASCADE, verbose_name='Corporate Name')
    deal_start_date = models.DateTimeField()
    deal_end_date = models.DateTimeField()
    payment_date = models.DateTimeField()
    gross_amount = models.IntegerField(default=None)
    YES = 1
    NO = 2
    tds_choices = ((YES, 'Yes'), (NO, 'No'),)
    tds_deducted = models.IntegerField(choices=tds_choices, default=NO)
    expected_provider_fee = models.IntegerField(default=None)
    employee_count = models.IntegerField(default=None)
    service_description = models.TextField(default='N/A')
    receipt_no = models.CharField(max_length=1000, default='')
    receipt_image = models.FileField(default=None, upload_to='corporate/receipt', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "corporate_deal"


class CorporateDocument(TimeStampedModel, Document):
    PAN = 1
    ADDRESS_PROOF = 2
    GST = 3
    COMPANY_REGISTRATION = 4
    BANK_STATEMENT = 5
    LOGO = 6
    EMAIL_CONFIRMATION = 9
    image_sizes = [(90, 60), ]
    image_base_path = 'corporate/images'
    CHOICES = [(PAN, "PAN Card"), (ADDRESS_PROOF, "Address Proof"), (GST, "GST Certificate"),
               (COMPANY_REGISTRATION, "Company Registration Certificate"), (BANK_STATEMENT, "Bank Statement"),
               (LOGO, "LOGO"),
               (EMAIL_CONFIRMATION, "Email Confirmation")]
    corporate_booking = models.ForeignKey(CorporateBooking, null=True, blank=True, default=None,
                                          on_delete=models.CASCADE,
                                          related_name='corporate_documents')
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='corporate/images', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "corporate_document"
