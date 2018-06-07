from django.db import models
from ondoc.authentication.models import TimeStampedModel, CreatedByModel


class ChatMedicalCondition(TimeStampedModel):
    name = models.CharField(max_length=100, verbose_name="Name")

    def __str__(self):
        return "{}".format(self.name)

    class Meta:
        db_table = "chat_medical_condition"