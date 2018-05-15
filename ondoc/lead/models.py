from django.db import models
from django.contrib.postgres.fields import JSONField


class HospitalLead(models.Model):
    source_id = models.PositiveIntegerField()
    city = models.CharField(max_length=100)
    lab = models.CharField(max_length=256)
    json = JSONField()

    def __str__(self):
        return "{}-{}".format(self.lab, self.id)

    class Meta:
        db_table = "hospital_lead"


