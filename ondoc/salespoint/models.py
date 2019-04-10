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

    @classmethod
    def is_affiliate_available(cls, name):
        name = name.lower()
        salespoint_affiliates = SalesPoint.objects.filter().values_list('name', flat=True)
        salespoint_affiliates = list(map(lambda x: x.lower(), salespoint_affiliates))
        if name in salespoint_affiliates:
            return True

        return False


    class Meta:
        db_table = 'salespoint'


class SalespointTestmapping(TimeStampedModel):
    salespoint = models.ForeignKey(SalesPoint, on_delete=models.CASCADE)
    available_tests = models.ForeignKey(AvailableLabTest, on_delete=models.CASCADE, related_name='active_sales_point_mappings')
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = 'salespoint_test_mapping'