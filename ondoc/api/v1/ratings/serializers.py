from rest_framework import serializers
from ondoc.ratings_review import models as rating_models
from django.db.models import Count, Sum, When, Case, Q, F
from django.utils import timezone
from ondoc.api.v1 import utils


class RatingBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=500)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=rating_models.RatingsReview.APPOINTMENT_TYPE_CHOICES)
