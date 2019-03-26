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
    appointment_id = serializers.IntegerField(required=False, allow_null=True)
    appointment_type = serializers.ChoiceField(choices=RatingsReview.APPOINTMENT_TYPE_CHOICES)      #treat appointment_type as entity_type
    # compliment = ListReviewComplimentSerializer(source='request.data')
    compliment = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=ReviewCompliments.objects.all()), allow_empty=True)
    entity_id = serializers.IntegerField(required=False, allow_null=True)
    related_entity_id = serializers.IntegerField(required=False, allow_null=True)

    def validate(self, attrs):
        if not (attrs.get('appointment_id') or attrs.get('entity_id')):
            raise serializers.ValidationError("either one of appointment id or entity id is required")
        if (attrs.get('appointment_id') and attrs.get('appointment_type')):
            query = RatingsReview.objects.filter(appointment_id=attrs['appointment_id'], appointment_type=attrs['appointment_type'])
            # if attrs.get('appointment_type') == RatingsReview.OPD:
            #     app = doc_models.OpdAppointment.objects.filter(id=attrs.get('appointment_id')).first()
            # else:
            #     app = lab_models.LabAppointment.objects.filter(id=attrs.get('appointment_id')).first()
            if query.exists():
                raise serializers.ValidationError("Appointment Already Rated.")
        if attrs.get('appointment_type') == RatingsReview.OPD and attrs.get('entity_id'):
            if not attrs.get('related_entity_id'):
                raise serializers.ValidationError("related_entity_id(Hospital) is missing for given entity_id(Doctor)")
            elif not doc_models.Hospital.objects.filter(id=attrs.get('related_entity_id')).exists():
                raise serializers.ValidationError("object for related_entity_id(Hospital) is not found")
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
        elif attrs.get('content_type') == RatingsReview.HOSPITAL and not doc_models.Hospital.objects.filter(id=attrs.get('object_id')).exists():
            raise serializers.ValidationError('Hospital Not Found')
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
        count = len(obj)
        return count

    def get_review_count(self, obj):
        empty_review_count = 0
        for data in obj:
            if data.get('text') == '' or data.get('text') == None:
                empty_review_count += 1
        count = len(obj) - empty_review_count
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
                star_data[rate.get('rating')]['count'] += 1
            for key, value in star_data.items():
                star_data[key]['percent'] = '{0:.2f}'.format((star_data[key]['count'] / total * 100))
            return star_data
        return star_data

    def get_avg_rating(self, obj):
        avg = None
        sum_rating = 0
        if obj:
            for data in obj:
                sum_rating += data.get('rating')
            avg = sum_rating / len(obj)
            avg = round(avg, 1)
        return avg


class RatingsModelSerializer(serializers.ModelSerializer):
    compliment = serializers.SerializerMethodField()
    date = serializers.SerializerMethodField()
    user_name = serializers.SerializerMethodField()
    is_verified = serializers.SerializerMethodField()

    def get_user_name(self, obj):
        name = app = profile = None
        app_obj = self.context.get('app')
        if app_obj:
            for ap in app_obj:
                if obj.appointment_id == ap.id:
                    app = ap
                    break
            if app:
                profile = app.profile
        else:
            for pro in obj.user.profiles.all():
                if pro.is_default_user:
                    profile = pro
                    break
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

    def get_is_verified(self, obj):
        return True if obj.appointment_id else False

    class Meta:
        model = RatingsReview
        fields = ('id', 'user', 'ratings', 'review', 'is_live', 'date', 'compliment', 'user_name', 'is_verified', 'related_entity_id')


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