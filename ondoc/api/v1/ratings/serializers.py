from rest_framework import serializers
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments)
from django.core import serializers as core_serializer

import json
from django.db.models import Count, Sum, When, Case, Q, F
from django.utils import timezone
from ondoc.api.v1 import utils


class RatingCreateBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=500)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)


class RatingListBodySerializerdata(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)
    object_id = serializers.IntegerField()


class RatingsModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = RatingsReview
        fields = ('id', 'user', 'ratings', 'review', 'is_live', 'updated_at')

class ReviewComplimentSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ReviewCompliments.TYPE_CHOICES)
    rating_level = serializers.IntegerField(max_value=5)


class GetComplementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewCompliments
        fields = ('id', 'message', 'rating_level', 'type')