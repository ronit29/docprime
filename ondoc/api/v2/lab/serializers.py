from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
import logging
from ondoc.doctor import models as doc_models
logger = logging.getLogger(__name__)
User = get_user_model()


class DoctorBlockCalenderSerializer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in doc_models.DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(required=False, choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField()
