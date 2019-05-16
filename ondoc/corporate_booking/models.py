from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from ondoc.authentication import models as auth_model
from ondoc.authentication.models import TimeStampedModel, Document
from ondoc.bookinganalytics.models import DP_CorporateDeals
from ondoc.common.models import MatrixMappedCity, MatrixMappedState, SyncBookingAnalytics


class Corporates(auth_model.TimeStampedModel):
    corporate_name = models.CharField(max_length=1000, default='')
    building = models.CharField(max_length=1000, null=True, blank=True)
    sublocality = models.CharField(max_length=1000, null=True, blank=True)
    locality = models.CharField(max_length=1000, null=True, blank=True)
    matrix_city = models.ForeignKey(MatrixMappedCity, on_delete=models.CASCADE, default='', related_name='citymatrix', verbose_name='city')
    matrix_state = models.ForeignKey(MatrixMappedState, on_delete=models.CASCADE, default='', related_name='statematrix', verbose_name='state')
    PIN = models.BigIntegerField(null=True, blank=True, verbose_name='PIN Code')
    pan_no = models.CharField(max_length=10000, default='', verbose_name='PAN no.')
    gst_no = models.CharField(max_length=10000, default='', verbose_name='GST no.')

    def __str__(self):
        return "{}".format(self.corporate_name)

    class Meta:
        db_table = 'corporate_booking'


class CorporateDeal(auth_model.TimeStampedModel):
    corporate = models.ForeignKey(Corporates, on_delete=models.CASCADE, verbose_name='Corporate Name')
    deal_start_date = models.DateTimeField()
    deal_end_date = models.DateTimeField()
    payment_date = models.DateTimeField()
    gross_amount = models.IntegerField(default=None)
    tds_choices = (('YES', 'Yes'), ('NO', 'No'),)
    tds_deducted = models.CharField(max_length=50, choices=tds_choices, default='NO', verbose_name='TDS deducted')
    expected_provider_fee = models.IntegerField(default=None)
    employee_count = models.IntegerField(default=None)
    service_description = models.TextField(default='')
    receipt_no = models.CharField(max_length=1000, default='')
    is_active = models.BooleanField(default=False)
    receipt_image = models.FileField(default=None, upload_to='corporate/receipt',
                                     validators=[FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])
    synced_analytics = GenericRelation(SyncBookingAnalytics, related_name="corporate_deal_analytics")


    def __str__(self):
        return "{}".format(self.id)


    def sync_with_booking_analytics(self):
        obj = DP_CorporateDeals.objects.filter(CorporateDealId=self.id).first()
        if not obj:
            obj = DP_CorporateDeals()
            obj.CorporateDealId = self.id

        obj.CorporateName = self.corporate.corporate_name
        obj.DealStartDate = self.deal_start_date
        obj.ReceiptNumber = self.receipt_no
        obj.CreatedDate = self.created_at
        obj.ExpectedProviderFee = self.expected_provider_fee
        obj.GrossAmount = self.gross_amount
        obj.NumberOfEmployees = self.employee_count
        obj.TDSDeducted = self.tds_deducted
        obj.PaymentDate = self.payment_date
        obj.IsActive = self.is_active
        obj.DealEndDate = self.deal_end_date
        obj.UpdatedDate = self.updated_at
        obj.save()


        try:
            SyncBookingAnalytics.objects.update_or_create(object_id=self.id,
                                                          content_type=ContentType.objects.get_for_model(CorporateDeal),
                                                          defaults={"synced_at": self.updated_at, "last_updated_at": self.updated_at})
        except Exception as e:
            pass

        return obj

    class Meta:
        db_table = "corporate_deal"


class CorporateDocument(TimeStampedModel, Document):
    PAN = 1
    ADDRESS_PROOF = 2
    GST = 3
    COMPANY_REGISTRATION = 4
    BANK_STATEMENT = 5
    LOGO = 6
    EMAIL_CONFIRMATION = 7
    OTHER = 8
    image_sizes = [(90, 60), ]
    image_base_path = 'corporate/images'
    CHOICES = [(PAN, "PAN Card"), (ADDRESS_PROOF, "Address Proof"), (GST, "GST Certificate"),
               (COMPANY_REGISTRATION, "Company Registration Certificate"), (BANK_STATEMENT, "Bank Statement"),
               (LOGO, "LOGO"),
               (EMAIL_CONFIRMATION, "Email Confirmation"), (OTHER, "Other")]
    corporate_booking = models.ForeignKey(Corporates, null=True, blank=True, default=None,
                                          on_delete=models.CASCADE,
                                          related_name='corporate_documents')
    document_type = models.PositiveSmallIntegerField(choices=CHOICES)
    name = models.FileField(upload_to='corporate/images', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])

    def __str__(self):
        return "{}".format(self.id)

    class Meta:
        db_table = "corporate_document"
