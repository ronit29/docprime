from rest_framework import serializers
from ondoc.ratings_review.models import (RatingsReview, ReviewCompliments)
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
    review = serializers.CharField(max_length=500, allow_blank=True)
    appointment_id = serializers.IntegerField()
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)
    # compliment = ListReviewComplimentSerializer(source='request.data')
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ReviewCompliments.objects.all()), allow_empty=True)

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
        response = []
        request = self.context.get('request')
        for rate in obj.all():
            for cmlmnt in  rate.compliment.all():
                r = {'id': cmlmnt.id,
                     'message': cmlmnt.message,
                     'icon': cmlmnt.icon.url if cmlmnt.icon else None}
                comp.append(r)
        comp_count = {}
        for x in comp:
            if comp_count.get(x['id']):
                comp_count[x['id']]['count'] += 1

            else:
                comp_count[x['id']] = x
                comp_count[x['id']]['count'] = 1
                comp_count[x['id']]['icon'] = request.build_absolute_uri(x['icon']) if x.get('icon') is not None else None
        response = [comp_count[k] for k in sorted(comp_count, key=comp_count.get('count'), reverse=True)][:3]
        return response

    def get_rating_count(self, obj):
        count = 0
        if obj.exists():
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
        total = obj.count()
        if total:
            for rate in obj.all():
                star_data[rate.ratings]['count'] += 1
            for key, value in star_data.items():
                star_data[key]['percent'] = '{0:.2f}'.format((star_data[key]['count'] / total * 100))
            return star_data
        return star_data


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
        if obj.appointment_type == RatingsReview.OPD:
            app = doc_models.OpdAppointment.objects.filter(id=obj.appointment_id).first()
        else:
            app = lab_models.LabAppointment.objects.filter(id=obj.appointment_id).first()
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


