from rest_framework import serializers
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments)
from django.core import serializers as core_serializer

import json
from django.db.models import Count, Sum, When, Case, Q, F
from django.utils import timezone
from ondoc.api.v1 import utils


class RatingBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=500)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)


class RatingDataSerializer(serializers.Serializer):

    def get_ratings_data(request):
        parameters = request.query_params
        profile = parameters['profile']
        concern_id = int(parameters['concern_id'])
        if profile=='doctor':
            rating_data = RatingsReview.objects.filter(doctors__id=concern_id, review__isnull=False, is_live=True).all()
        elif profile=='lab':
            rating_data = RatingsReview.objects.filter(labs__id=concern_id, review_isnull=False, is_live=True).all()
        result = core_serializer.serialize('json', rating_data, fields=('user', 'ratings', 'review'))
        return result


class ReviewComplimentSerializer(serializers.Serializer):

    def get_compliments(request):
        parameters = request.query_params
        profile = parameters['profile']
        rating = int(parameters['rating'])
        compliment_data={}
        review_complement_data = ReviewCompliments.objects.all()
        if profile=='doctor':
            if rating <= 3:
                compliment_data = core_serializer.serialize('json', review_complement_data,
                                                        fields=('doc_low_rating',))
            else:
                compliment_data = core_serializer.serialize('json', review_complement_data,
                                                        fields=('doc_high_rating',))
        elif profile=='lab':
            if rating <= 3:
                compliment_data = core_serializer.serialize('json', review_complement_data,
                                                        fields=('lab_low_rating',))
            else:
                compliment_data = core_serializer.serialize('json', review_complement_data,
                                                        fields=('lab_high_rating',))

        return compliment_data