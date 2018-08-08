from django.db import models
from ondoc.authentication.models import TimeStampedModel


class Report(TimeStampedModel):
    report_name = models.CharField(max_length=100)
    description = models.CharField(max_length=100)
    sql = models.TextField()

    class Meta:
        db_table = 'report'

    def __str__(self):
        return "{}".format(self.report_name)


class GeneratedReport(Report):
    class Meta:
        proxy = True
        default_permissions = []


