from rest_framework import serializers
from ondoc.ratings_review import models as rating_models
from django.core import serializers as core_serializer
from django.db.models import Count, Sum, When, Case, Q, F
from django.utils import timezone
from ondoc.api.v1 import utils


class RatingBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=500)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=rating_models.RatingsReview.APPOINTMENT_TYPE_CHOICES)


class RatingDataSerializer(serializers.Serializer):

    def get_ratings_data(request):
        profile = request.data.get('profile')
        concern_id = request.data.get('concern_id')
        if profile=='doctor':
            rating_data = rating_models.RatingsReview.objects.filter(doctors__id=concern_id, review__isnull=False).all()
        elif profile=='lab':
            rating_data = rating_models.RatingsReview.objects.filter(labs__id=concern_id, review_isnull=False).all()
        result = core_serializer.serialize('json', rating_data)
        return result



