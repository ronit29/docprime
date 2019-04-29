from django.core.validators import FileExtensionValidator
from django.db import models

# Create your models here.
from ondoc.authentication import models as auth_model



class CorporateBooking(auth_model.TimeStampedModel):
    corporate_id = models.IntegerField(null=True, blank=True)
    corporate_name = models.CharField(max_length=1000, null=True, blank=True)
    corporate_address = models.CharField(max_length=10000, null=True, blank=True)
    pan_no = models.CharField(max_length=10000, null=True, blank=True, verbose_name='PAN no.')
    gst_no = models.CharField(max_length=10000, null=True, blank=True, verbose_name='GST no.')
    corporate_documents = models.FileField(upload_to='corporate_booking', validators=[
        FileExtensionValidator(allowed_extensions=['pdf', 'jfif', 'jpg', 'jpeg', 'png'])])


    class meta:
        db_table = 'corporate_booking'



















