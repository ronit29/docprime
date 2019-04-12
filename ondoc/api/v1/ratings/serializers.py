from rest_framework import serializers
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments, AppCompliments, AppRatings)
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as lab_models
from django.db.models import Q


class ReviewComplimentBodySerializer(serializers.Serializer):
    type = serializers.ChoiceField(choices=ReviewCompliments.TYPE_CHOICES)


class GetComplementSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReviewCompliments
        fields = ('id', 'message', 'rating_level', 'type')


class RatingCreateBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=5000, allow_blank=True)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)
    # compliment = ListReviewComplimentSerializer(source='request.data')
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ReviewCompliments.objects.all()), allow_empty=True)

    def validate(self, attrs):
        if (attrs.get('appointment_id') and attrs.get('appointment_type')):
            if attrs.get('appointment_type') == RatingsReview.OPD:
                app = doc_models.OpdAppointment.objects.filter(id=attrs.get('appointment_id')).first()
            else:
                app = lab_models.LabAppointment.objects.filter(id=attrs.get('appointment_id')).first()
            if app and app.is_rated:
                raise serializers.ValidationError("Appointment Already Rated.")
        return attrs


class RatingPromptCloseBodySerializer(serializers.Serializer):
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)


class RatingListBodySerializerdata(serializers.Serializer):
    content_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)
    object_id = serializers.IntegerField()

    def validate(self, attrs):
        if attrs.get('content_type') == RatingsReview.OPD and not doc_models.Doctor.objects.filter(id=attrs.get('object_id')).exists():
            raise serializers.ValidationError('Doctor Not Found')
        elif attrs.get('content_type') == RatingsReview.LAB and not lab_models.Lab.objects.filter(id=attrs.get('object_id')).exists():
            raise serializers.ValidationError('Lab Not Found')
        return attrs


class RatingsGraphSerializer(serializers.Serializer):
    rating_count = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    star_count = serializers.SerializerMethodField()
    top_compliments = serializers.SerializerMethodField()

    def get_top_compliments(self, obj):
        comp = []
        response = []
        comp_count = {}
        request = self.context.get('request')
        for rate in obj:
            for cmlmnt in rate.compliment.all():
                if cmlmnt.rating_level == 4 or cmlmnt.rating_level == 5:
                    r = {'id': cmlmnt.id,
                         'message': cmlmnt.message,
                         'level': cmlmnt.rating_level,
                         'icon': cmlmnt.icon.url if cmlmnt.icon else None}
                    if comp_count.get(r['id']):
                        comp_count[r['id']]['count'] += 1

                    else:
                        comp_count[r['id']] = r
                        comp_count[r['id']]['count'] = 1
                        comp_count[r['id']]['icon'] = request.build_absolute_uri(r['icon']) if r.get(
                            'icon') is not None else None
                        comp.append(comp_count[r['id']])
        temp = {}
        for x in comp:
            if temp.get(x['message']):
                temp[x['message']]['count'] += x['count']
            else:
                temp[x['message']] = x
        response = [temp[k] for k in sorted(temp, key=lambda k: temp[k]['count'], reverse=True)][:3]
        return response

    def get_rating_count(self, obj):
        count = obj.count()
        return count

    def get_review_count(self, obj):
        count = obj.exclude(Q(review='') | Q(review=None)).count()
        return count

    def get_star_count(self, obj):
        star_data = {1: {'count': 0, 'percent': 0},
                 2: {'count': 0, 'percent': 0},
                 3: {'count': 0, 'percent': 0},
                 4: {'count': 0, 'percent': 0},
                 5: {'count': 0, 'percent': 0}}
        total = len(obj)
        if total:
            for rate in obj:
                star_data[rate.ratings]['count'] += 1
            for key, value in star_data.items():
                star_data[key]['percent'] = '{0:.2f}'.format((star_data[key]['count'] / total * 100))
            return star_data
        return star_data

    def get_avg_rating(self, obj):
        avg = None
        if obj.exists():
            all_rating = obj.values_list('ratings', flat=True)
            avg = sum(all_rating) / len(all_rating)
            avg = round(avg, 1)
        return avg


class GoogleRatingsGraphSerializer(serializers.Serializer):
    rating_count = serializers.SerializerMethodField()
    review_count = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()
    star_count = serializers.SerializerMethodField()
    top_compliments = serializers.SerializerMethodField()

    def get_top_compliments(self, obj):
        return None

    def get_rating_count(self, obj):
        count = obj.get('user_ratings_total') if obj.get('user_ratings_total') else None
        return count

    def get_review_count(self, obj):
        empty_review_count = 0
        if obj.get('user_reviews'):
            for data in obj.get('user_reviews'):
                if data.get('text') == '' or data.get('text') == None:
                    empty_review_count += 1
            count = len(obj.get('user_reviews')) - empty_review_count
            return count
        return None

    def get_star_count(self, obj):
        return None

    def get_avg_rating(self, obj):
        avg = obj.get('user_avg_rating') if obj.get('user_avg_rating') else None
        if avg:
            avg = round(avg, 1)
        return avg


class RatingsModelSerializer(serializers.ModelSerializer):
    compliment = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()

    def get_user_name(self, obj):
        name = app = None
        app_obj = self.context.get('app')
        if app_obj:
            for ap in app_obj:
                if obj.appointment_id == ap.id:
                    app = ap
                    break
            if app:
                profile = app.profile
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
        c_list = []
        for cm in obj.compliment.all():
            c_list.append(cm.message)
        if c_list:
            compliments_string = (', ').join(c_list)
        return compliments_string

    class Meta:
        model = RatingsReview
        fields = ('id', 'user', 'ratings', 'review', 'is_live', 'date', 'compliment', 'user_name')


class RatingUpdateBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=5000, allow_blank=True)
    id = serializers.IntegerField()
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ReviewCompliments.objects.all()))

    def validate(self, attrs):
        if not RatingsReview.objects.filter(id=attrs['id']).exists():
            raise serializers.ValidationError("Invalid id")
        return attrs


class AppRatingCreateBodySerializer(serializers.Serializer):
    rating = serializers.IntegerField(max_value=5)
    review = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    platform = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    app_version = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    app_name = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    device_id = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    brand = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    model = serializers.CharField(max_length=5000, allow_blank=True, required=False)
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=AppCompliments.objects.all()),
                                       allow_empty=True, required=False)