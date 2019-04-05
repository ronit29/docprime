from django.db import models
from ondoc.authentication.models import TimeStampedModel
from ondoc.diagnostic.models import AvailableLabTest


# Create your models here.
class SalesPoint(TimeStampedModel):
    name = models.CharField(max_length=100, blank=False)
    spo_code = models.CharField(max_length=200, blank=False, unique=True)

    def __str__(self):
        return "{}".format(self.name)

    @classmethod
    def get_salespoint_via_code(cls, code):
        return cls.objects.filter(spo_code=code).first()

    class Meta:
        db_table = 'salespoint'


class SalespointTestmapping(TimeStampedModel):
    salespoint = models.ForeignKey(SalesPoint, on_delete=models.CASCADE)
    available_lab_test = models.ForeignKey(AvailableLabTest, on_delete=models.CASCADE, related_name='active_sales_point_mappings')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'salespoint_test_mapping'