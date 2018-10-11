from rest_framework import serializers
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments)
from django.core import serializers as core_serializer
from ondoc.doctor import models as doc_models
import json
from django.db.models import Count, Sum, When, Case, Q, F
from django.utils import timezone
from ondoc.api.v1 import utils


class ListReviewComplimentSerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ReviewCompliments.TYPE_CHOICES)
    message = serializers.CharField(max_length=500)
    rating_level = serializers.IntegerField(max_value=5, default=None)
    class Meta:
        model = ReviewCompliments
        fields = ('id', 'message', 'rating_level', 'type')


class RatingCreateBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=500)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)
    # compliment = ListReviewComplimentSerializer(source='request.data')
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ReviewCompliments.objects.all()))

    # def validate(self, attrs):
    #     if (attrs.get('appointment_id') and attrs.get('appointment_type')):
    #         if attrs.get('appointment_type') == RatingsReview.OPD:
    #             pass
    #             raise serializers.ValidationError("Appointment Not Completed.")


class RatingPromptCloseBodySerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)

class RatingListBodySerializerdata(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)
    object_id = serializers.IntegerField()


class RatingsGraphSerializer(serializers.Serializer):
    rating_count = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    star_count = serializers.SerializerMethodField()
    top_compliments = serializers.SerializerMethodField()

    def get_top_compliments(self, obj):
        comp = []
        for rate in obj.all():
            if rate.compliment.exists():
                for r in rate.compliment.values('id', 'message', 'icon'):
                    comp.append(r)
        comp_count = {}
        for x in comp:
            if comp_count.get(x['id']):
                comp_count[x['id']] += 1
                x['count'] +=1
            else:
                comp_count[x['id']] = 1
                x['count'] = 1
        return comp

    def get_rating_count(self, obj):
        count = 0
        if obj.all().first():
            count = obj.all().count()
        return count

    def get_review_count(self, obj):
        count = 0
        if obj.filter(review__isnull=False).exists():
            count = obj.filter(review__isnull=False).count()
        return count

    def get_star_count(self, obj):
        count = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for rate in obj.all():
            count[rate.ratings] += 1

        return count


    def get_avg_rating(self, obj):
        avg = None
        if obj.all().first():
            all_rating = obj.values_list('ratings', flat=True)
            avg = sum(all_rating) / len(all_rating)
            avg = round(avg, 1)
        return avg


class RatingsModelSerializer(serializers.ModelSerializer):
    compliment = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    def get_user_name(self, obj):
        name= None
        profile = obj.user.profiles.all().first()
        if profile:
            name = profile.name
        return name

    def get_date(self, obj):
        date = None
        if obj and obj.updated_at:
            date = obj.updated_at.strftime('%d %b %Y')
        return date

    def get_compliment(self, obj):
        compliments_string = ''
        if obj.compliment:
            c_list = obj.compliment.values_list('message', flat=True)
            compliments_string = (', ').join(c_list)
        return compliments_string

    class Meta:
        model = RatingsReview
        fields = ('id', 'user', 'ratings', 'review', 'is_live', 'date', 'compliment', 'user_name')


class RatingUpdateBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=500, allow_blank=True)
    id = serializers.IntegerField()
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ReviewCompliments.objects.all()))

    def validate(self, attrs):
        if not RatingsReview.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("Invalid id")
        return attrs


