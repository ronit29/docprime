from rest_framework import serializers
from rest_framework.fields import CharField
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition, LabImage, LabReportFile, CommonPackage)
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.authentication.models import UserProfile, Address
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer, CommaSepratedToListField
from ondoc.api.v1.auth.serializers import AddressSerializer, UserProfileSerializer
from ondoc.api.v1.utils import form_time_slot
from ondoc.doctor.models import OpdAppointment
from ondoc.account.models import Order
from ondoc.coupon.models import Coupon
from django.db.models import Count, Sum, When, Case, Q, F
from django.contrib.auth import get_user_model
from collections import OrderedDict
from django.utils import timezone
from ondoc.api.v1 import utils
import datetime
import pytz
import random
import logging
import json
from ondoc.ratings_review.models import RatingsReview
from django.db.models import Avg
from django.db.models import Q
from ondoc.api.v1.ratings import serializers as rating_serializer
from ondoc.location.models import EntityUrls, EntityAddress

logger = logging.getLogger(__name__)
utc = pytz.UTC
User = get_user_model()


class LabTestListSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id', 'name', 'is_package')


class LabListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lab
        fields = ('id', 'name')


class LabTestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabTest
        fields = ('id', 'name', 'pre_test_info', 'why')
        # fields = ('id', 'account_name', 'users', 'created')


class LabImageModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabImage
        fields = ('name', )
        # exclude = ('created_at', 'updated_at',)


class LabModelSerializer(serializers.ModelSerializer):

    lat = serializers.SerializerMethodField()
    long = serializers.SerializerMethodField()
    address = serializers.SerializerMethodField()
    lab_image = LabImageModelSerializer(many=True)
    lab_thumbnail = serializers.SerializerMethodField()
    home_pickup_charges = serializers.ReadOnlyField()
    seo = serializers.SerializerMethodField()
    # rating = rating_serializer.RatingsModelSerializer(read_only=True, many=True, source='get_ratings')
    rating_graph = serializers.SerializerMethodField()
    breadcrumb = serializers.SerializerMethodField()
    rating = serializers.SerializerMethodField()
    unrated_appointment = serializers.SerializerMethodField()


    def get_rating(self, obj):
        queryset = obj.rating.exclude(Q(review='') | Q(review=None)).filter(is_live=True).order_by('-updated_at')
        reviews = rating_serializer.RatingsModelSerializer(queryset, many=True)
        return reviews.data[:5]

    def get_unrated_appointment(self, obj):
        request = self.context.get('request')
        if request:
            if request.user.is_authenticated:
                user = request.user
                lab_app = None
                lab_all = user.lab_appointments.filter(lab=obj).order_by('-id')
                for lab in lab_all:
                    if lab.status == LabAppointment.COMPLETED and lab.is_rated == False:
                        lab_app = lab
                    break
                if lab_app:
                    data = LabAppointmentModelSerializer(lab_app, many=False, context={'request': request})
                    return data.data
            return None

    def get_rating_graph(self, obj):
        if obj and obj.rating:
            data = rating_serializer.RatingsGraphSerializer(obj.rating, context={'request':self.context.get('request')}).data
            return data
        return None


    def get_seo(self, obj):
        if self.parent:
            return None
        entity = EntityUrls.objects.filter(entity_id=obj.id, url_type='PAGEURL', is_valid='t',
                                           entity_type__iexact='Lab')
        locality = ''
        sublocality = ''
        if entity.exists():
            location_id = entity.first().additional_info.get('location_id')
            type = EntityAddress.objects.filter(id=location_id).values('type', 'value', 'parent')
            if type.exists():
                if type.first().get('type') == 'LOCALITY':
                    locality = type.first().get('value')

            if type.exists():
                if type.first().get('type') == 'SUBLOCALITY':
                    sublocality = type.first().get('value')
                    parent = EntityAddress.objects.filter(id=type.first().get('parent')).values('value')
                    if sublocality:
                        locality = ' ' + parent.first().get('value')
        if not(sublocality == '') or not(locality == ''):
            title = obj.name + ' - Diagnostic Centre in '+ sublocality + locality + ' |DocPrime'
        else:
            title = obj.name + ' - Diagnostic Centre |DocPrime'

        description = obj.name + ': Book test at ' + obj.name + ' online, check fees, packages prices and more at DocPrime. '
        return {'title': title, "description": description}

    def get_breadcrumb(self, obj):

        if self.parent:
            return None
        entity = EntityUrls.objects.filter(entity_id=obj.id, url_type='PAGEURL', is_valid='t',
                                           entity_type__iexact='Lab')
        breadcrums = None
        if entity.exists():
            breadcrums = entity.first().additional_info.get('breadcrums')
            if breadcrums:
                return breadcrums
        return breadcrums

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        if not request:
            raise ValueError("request is not passed in serializer.")
        return request.build_absolute_uri(obj.get_thumbnail()) if obj.get_thumbnail() else None

    def get_address(self, obj):
        return obj.get_lab_address() if obj.get_lab_address() else None

    def get_lat(self,obj):
        if obj.location:
            return obj.location.y

    def get_long(self,obj):
        if obj.location:
            return obj.location.x


    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'lab_image', 'lab_thumbnail', 'name', 'operational_since', 'locality', 'address',
                  'sublocality', 'city', 'state', 'country', 'always_open', 'about', 'home_pickup_charges',
                  'is_home_collection_enabled', 'seo', 'breadcrumb', 'rating', 'rating_graph', 'unrated_appointment')


class LabProfileSerializer(LabModelSerializer):

    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'address', 'lab_image', 'lab_thumbnail', 'name', 'operational_since', 'locality',
                  'sublocality', 'city', 'state', 'country', 'about', 'always_open', 'building', )


class AvailableLabTestPackageSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    is_package = serializers.ReadOnlyField(source='test.is_package')
    number_of_tests = serializers.ReadOnlyField(source='test.number_of_tests')
    expected_tat = serializers.ReadOnlyField(source='test.expected_tat')
    pre_test_info = serializers.ReadOnlyField(source='test.pre_test_info')
    why = serializers.ReadOnlyField(source='test.why')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()
    package = serializers.SerializerMethodField()
    parameters = serializers.SerializerMethodField()

    def get_is_home_collection_enabled(self, obj):
        if self.context.get("lab") is not None:
            if self.context["lab"].is_home_collection_enabled and obj.test.home_collection_possible:
                return True
            return False
        return obj.test.home_collection_possible
        # return None

    def get_agreed_price(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        return agreed_price

    def get_deal_price(self, obj):
        deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
        return deal_price

    def get_package(self, obj):
        ret_data = list()
        if obj.test.is_package:
            packages_test = obj.test.packages.all()
            for t_obj in packages_test:
                # param_list = t_obj.lab_test.labtests.all().values_list("parameter__name", flat=True)
                param_objs = t_obj.lab_test.labtests.all()
                param_list = list()
                for obj in param_objs:
                    param_list.append(obj.parameter.name)
                ret_data.append({
                    "name": t_obj.lab_test.name,
                    "why": t_obj.lab_test.why,
                    "pre_test_info": t_obj.lab_test.pre_test_info,
                    "expected_tat": t_obj.lab_test.expected_tat,
                    "parameters": param_list
                })
        return ret_data

    def get_parameters(self, obj):
        # parameters = obj.test.labtests.all().values_list("parameter__name", flat=True)

        parameters = list()
        param_objs = obj.test.labtests.all()
        for obj in param_objs:
            parameters.append(obj.parameter.name)

        return parameters

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_collection_enabled',
                  'package', 'parameters', 'is_package', 'number_of_tests', 'why', 'pre_test_info', 'expected_tat')


class AvailableLabTestSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_collection_enabled = serializers.SerializerMethodField()

    def get_is_home_collection_enabled(self, obj):
        if self.context.get("lab") is not None:
            if self.context["lab"].is_home_collection_enabled and obj.test.home_collection_possible:
                return True
            return False
        return obj.test.home_collection_possible
        # return None

    def get_agreed_price(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        return agreed_price

    def get_deal_price(self, obj):
        deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
        return deal_price

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_collection_enabled')


class LabCustomSerializer(serializers.Serializer):
    # lab = serializers.SerializerMethodField()
    lab = LabModelSerializer()
    price = serializers.IntegerField(default=None)
    mrp = serializers.IntegerField(default=None)
    distance = serializers.IntegerField(source='distance.m')
    pickup_available = serializers.IntegerField(default=0)
    lab_timing = serializers.CharField(max_length=1000)
    lab_timing_data = serializers.ListField()
    next_lab_timing = serializers.DictField()
    next_lab_timing_data = serializers.DictField()


    # def get_lab(self, obj):
    #     queryset = Lab.objects.get(pk=obj['lab'])
    #     serializer = LabModelSerializer(queryset)
    #     return serializer.data


class CommonTestSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='test.id')
    name = serializers.ReadOnlyField(source='test.name')
    icon = serializers.SerializerMethodField

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj['icon']) if obj['icon'] else None

    class Meta:
        model = CommonTest
        fields = ('id', 'name', 'icon')


class CommonPackageSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='package.id')
    name = serializers.ReadOnlyField(source='package.name')
    icon = serializers.SerializerMethodField()

    def get_icon(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.icon.url) if obj.icon else None

    class Meta:
        model = CommonPackage
        fields = ('id', 'name', 'icon')


class CommonConditionsSerializer(serializers.ModelSerializer):

    test = serializers.SerializerMethodField()

    def get_test(self, obj):
        test_id = []
        if obj:
            for tst in obj.lab_test.all():
                test_id.append({"id": tst.id, "name": tst.name})
        return test_id

    class Meta:
        model = CommonDiagnosticCondition
        fields = ('id', 'name', 'test')


class PromotedLabsSerializer(serializers.ModelSerializer):
    # lab = LabModelSerializer()
    id = serializers.ReadOnlyField(source='lab.id')
    name = serializers.ReadOnlyField(source='lab.name')

    class Meta:
        model = PromotedLab
        fields = ('id', 'name', )


class LabAppointmentModelSerializer(serializers.ModelSerializer):
    LAB_TYPE = 'lab'
    type = serializers.ReadOnlyField(default="lab")
    lab_name = serializers.ReadOnlyField(source="lab.name")
    lab_image = LabImageModelSerializer(many=True, source='lab.lab_image', read_only=True)
    lab_thumbnail = serializers.SerializerMethodField()
    patient_thumbnail = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()
    allowed_action = serializers.SerializerMethodField()

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.lab.get_thumbnail()) if obj.lab.get_thumbnail() else None

    def get_patient_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.profile.get_thumbnail()) if obj.profile.get_thumbnail() else None

    def get_patient_name(self, obj):
        if obj.profile_detail:
            return obj.profile_detail.get("name")

    def get_allowed_action(self, obj):
        user_type = ''
        if self.context.get('request'):
            user_type = self.context['request'].user.user_type
            return obj.allowed_action(user_type, self.context.get('request'))
        else:
            return []

    class Meta:
        model = LabAppointment
        fields = ('id', 'lab', 'lab_test', 'profile', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'patient_thumbnail', 'patient_name', 'allowed_action', 'address')


class LabAppointmentBillingSerializer(serializers.ModelSerializer):
    LAB_TYPE = 'lab'
    type = serializers.ReadOnlyField(default="lab")
    lab_name = serializers.ReadOnlyField(source="lab.name")
    lab_image = LabImageModelSerializer(many=True, source='lab.lab_image', read_only=True)
    lab_thumbnail = serializers.SerializerMethodField()
    patient_thumbnail = serializers.SerializerMethodField()
    patient_name = serializers.SerializerMethodField()

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.lab.get_thumbnail()) if obj.lab.get_thumbnail() else None

    def get_patient_thumbnail(self, obj):
        request = self.context.get("request")
        return request.build_absolute_uri(obj.profile.get_thumbnail()) if obj.profile.get_thumbnail() else None

    def get_patient_name(self, obj):
        if obj.profile_detail:
            return obj.profile_detail.get("name")

    class Meta:
        model = LabAppointment
        fields = ('id', 'lab', 'lab_test', 'profile', 'type', 'lab_name', 'status', 'agreed_price', 'price',
                  'effective_price', 'time_slot_start', 'time_slot_end', 'is_home_pickup', 'lab_thumbnail', 'lab_image',
                  'patient_thumbnail', 'patient_name', 'payment_type')


class LabAppTransactionModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.filter(is_live=True))
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    agreed_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    time_slot_start = serializers.DateTimeField()
    profile_detail = serializers.JSONField()
    status = serializers.IntegerField()
    payment_type = serializers.IntegerField()
    lab_test = serializers.ListField(child=serializers.IntegerField())
    home_pickup_charges = serializers.DecimalField(max_digits=10, decimal_places=2)
    is_home_pickup = serializers.BooleanField(default=False)
    address = serializers.JSONField(required=False)
    coupon = serializers.ListField(child=serializers.IntegerField(), required=False, default = [])
    discount = serializers.DecimalField(max_digits=10, decimal_places=2)


class LabAppRescheduleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabAppointment
        fields = '__all__'


class LabAppointmentUpdateSerializer(serializers.Serializer):
    appointment_status = [LabAppointment.CREATED, LabAppointment.ACCEPTED, LabAppointment.RESCHEDULED_LAB,
                          LabAppointment.CANCELLED, LabAppointment.RESCHEDULED_PATIENT, LabAppointment.COMPLETED,
                          LabAppointment.BOOKED]
    status = serializers.ChoiceField(choices=appointment_status)
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)

    def validate(self, data):
        request = self.context.get("request")
        temp_data = data
        temp_data["lab_id"] = self.context["lab_id"]
        LabAppointmentCreateSerializer.time_slot_validator(temp_data, request)

        return data

    def create(self, data):
        pass

    def update(self, instance, data):
        # if data['status'] == LabAppointment.RESCHEDULED_PATIENT:
        #     self.reschedule_validation(instance, data)
        # elif data['status'] == LabAppointment.CANCELLED:
        #     self.cancel_validation(instance, data)
        # else:
        #     raise serializers.ValidationError("Invalid Status")
        instance.time_slot_start = data.get("start_time", instance.time_slot_start)
        instance.time_slot_end = data.get("end_time", instance.time_slot_end)
        instance.status = data.get("status", instance.status)
        instance.save()
        return instance

    @staticmethod
    def reschedule_validation(instance, data):
        d = datetime.datetime.now().replace(tzinfo=utc)
        if instance.time_slot_start < d and data['start_time'] < d:
            raise serializers.ValidationError("Cannot Reschedule")

    def cancel_validation(self, instance, data):
        now = datetime.datetime.now().replace(tzinfo=utc)
        if instance.time_slot_start < now:
            raise serializers.ValidationError("Cannot Cancel")


class LabAppointmentCreateSerializer(serializers.Serializer):
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.filter(is_live=True))
    test_ids = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.all()))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    time_slot_start = serializers.DateTimeField(required=False)
    start_date = serializers.DateTimeField()
    start_time = serializers.FloatField()
    end_date = serializers.DateTimeField(required=False)
    end_time = serializers.FloatField(required=False)
    is_home_pickup = serializers.BooleanField(default=False)
    address = serializers.PrimaryKeyRelatedField(queryset=Address.objects.all(), required=False, allow_null=True)
    # address = serializers.IntegerField(required=False, allow_null=True)
    payment_type = serializers.IntegerField(default=OpdAppointment.PREPAID)
    coupon_code = serializers.ListField(child=serializers.CharField(), required=False, default=[])

    def validate(self, data):
        MAX_APPOINTMENTS_ALLOWED = 3
        ACTIVE_APPOINTMENT_STATUS = [LabAppointment.BOOKED, LabAppointment.ACCEPTED,
                                     LabAppointment.RESCHEDULED_PATIENT, LabAppointment.RESCHEDULED_LAB]
        request = self.context.get("request")

        if not utils.is_valid_testing_lab_data(request.user, data["lab"]):
            raise serializers.ValidationError("Both User and Lab should be for testing")

        if data.get("is_home_pickup"):
            if data.get("address") is None:
                raise serializers.ValidationError("Address required for home pickup")
            elif not Address.objects.filter(id=data.get("address").id, user=request.user).exists():
                raise serializers.ValidationError("Invalid address for given user")

        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            raise serializers.ValidationError("Invalid profile id")

        # if LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile=data["profile"], lab=data[
        #     "lab"]).exists():
        #     raise serializers.ValidationError("A previous appointment with this lab already exists. Cancel it before booking new Appointment.")

        if LabAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile=data["profile"]).count() >= MAX_APPOINTMENTS_ALLOWED:
            raise serializers.ValidationError('Max '+str(MAX_APPOINTMENTS_ALLOWED)+' active appointments are allowed')

        if data.get("coupon_code"):
            coupon_code = data.get("coupon_code")
            coupon_obj = Coupon.objects.filter(code__in=coupon_code)
            if len(coupon_code) == len(coupon_obj):
                for coupon in coupon_obj:
                    obj = LabAppointment()
                    if obj.validate_user_coupon(user=request.user, coupon_obj=coupon).get("is_valid"):
                        if coupon.is_user_specific:
                            if not obj.validate_product_coupon(coupon_obj=coupon,
                                                                     lab=data.get("lab"), test=data.get("test_ids"),
                                                                     product_id=Order.LAB_PRODUCT_ID):
                                raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))
                    else:
                        raise serializers.ValidationError('Invalid coupon code - ' + str(coupon))

        self.test_lab_id_validator(data, request)
        self.time_slot_validator(data, request)
        return data

    def create(self, data):
        deal_price_calculation= Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                     When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
        agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                      When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))

        self.num_appointment_validator(data)
        lab_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"], test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab').annotate(total_mrp=Sum("mrp"),
                                                                 total_deal_price=Sum(deal_price_calculation),
                                                                 total_agreed_price=Sum(agreed_price_calculation))
        total_deal_price = total_mrp = effective_price = 0
        if temp_lab_test:
            total_mrp = temp_lab_test[0].get("total_mrp", 0)
            total_agreed = temp_lab_test[0].get("total_agreed_price", 0)
            total_deal_price = temp_lab_test[0].get("total_deal_price", 0)
            effective_price = temp_lab_test[0].get("total_deal_price")
            # TODO PM - call coupon function to calculate effective price
        start_dt = form_time_slot(data["start_date"], data["start_time"])
        profile_detail = {
            "name": data["profile"].name,
            "gender": data["profile"].gender,
            "dob": str(data["profile"].dob),
        }
        otp = random.randint(1000, 9999)
        appointment_data = {
            "lab": data["lab"],
            "user": self.context["request"].user,
            "profile": data["profile"],
            "price": total_mrp,
            "agreed_price": total_agreed,
            "deal_price": total_deal_price,
            "effective_price": effective_price,
            "time_slot_start": start_dt,
            "profile_detail": profile_detail,
            "payment_status": OpdAppointment.PAYMENT_ACCEPTED,
            "status": LabAppointment.BOOKED,
            "payment_type": data["payment_type"],
            "otp": otp
        }
        if data.get("is_home_pickup") is True:
            address = Address.objects.filter(pk=data.get("address")).first()
            address_serialzer = AddressSerializer(address)
            appointment_data.update({
                "address": address_serialzer.data,
                "is_home_pickup": True
            })
        queryset = LabAppointment.objects.create(**appointment_data)
        queryset.lab_test.add(*lab_test_queryset)
        return queryset

    def update(self, instance, data):
        pass

    @staticmethod
    def num_appointment_validator(data):
        ACTIVE_APPOINTMENT_STATUS = [LabAppointment.CREATED, LabAppointment.ACCEPTED,
                                     LabAppointment.RESCHEDULED_PATIENT, LabAppointment.RESCHEDULED_LAB]
        count = (LabAppointment.objects.filter(lab=data['lab'],
                                               profile=data['profile'],
                                               status__in=ACTIVE_APPOINTMENT_STATUS).count())
        if count >= 2:
            raise serializers.ValidationError("More than 2 appointment with the lab")

    @staticmethod
    def test_lab_id_validator(data, request):
        if not data['test_ids']:
            logger.error(
                "Error 'No Test Ids given' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError(" No Test Ids given")

        avail_test_queryset = AvailableLabTest.objects.filter(lab_pricing_group__labs=data["lab"], test__in=data['test_ids']).values(
            'id').distinct('test')

        if len(avail_test_queryset) != len(data['test_ids']):
            logger.error("Error 'Test Ids or lab Id is incorrect' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Test Ids or lab Id is incorrect")

    @staticmethod
    def time_slot_validator(data, request):
        start_dt = (form_time_slot(data.get('start_date'), data.get('start_time')) if not data.get("time_slot_start") else data.get("time_slot_start"))

        if start_dt < timezone.now():
            logger.error("Error 'Cannot book in past' for lab appointment with data - " + json.dumps(request.data))
            raise serializers.ValidationError("Cannot book in past")

        day_of_week = start_dt.weekday()

        lab_queryset = data['lab']

        lab_timing_queryset = lab_queryset.lab_timings.filter(day=day_of_week, start__lte=data.get('start_time'),
                                                              end__gte=data.get('start_time'),
                                                              for_home_pickup=data["is_home_pickup"]).exists()
        if data["is_home_pickup"]:
            if not lab_queryset.is_home_collection_enabled:
                logger.error(
                    "Error 'Home Pickup is disabled for the lab' for lab appointment with data - " + json.dumps(
                        request.data))
                raise serializers.ValidationError("Home Pickup is disabled for the lab")
            if data.get("start_time") < 7.0 or data.get("start_time") > 19.0:
                logger.error(
                    "Error 'No time slot available' for lab appointment with data - " + json.dumps(
                        request.data))
                raise serializers.ValidationError("No time slot available")
        else:
            if not lab_queryset.always_open and not lab_timing_queryset:
                logger.error(
                    "Error 'No time slot available' for lab appointment with data - " + json.dumps(request.data))
                raise serializers.ValidationError("No time slot available")


class TimeSlotSerializer(serializers.Serializer):
    MORNING = 0
    AFTERNOON = 1
    EVENING = 2
    TIME_SPAN = 15
    # INT_SPAN = (TIME_SPAN/60)
    # TIME_INTERVAL = [":"+str(i) for i in range()]
    timing = serializers.SerializerMethodField()

    def get_timing(self, obj):
        start = float(obj.start)
        end = float(obj.end)
        time_span = self.TIME_SPAN
        day = obj.day
        timing = self.context['timing']

        int_span = (time_span / 60)
        # timing = dict()
        if not timing[day].get('timing'):
            timing[day]['timing'] = dict()
            timing[day]['timing'][self.MORNING] = OrderedDict()
            timing[day]['timing'][self.AFTERNOON] = OrderedDict()
            timing[day]['timing'][self.EVENING] = OrderedDict()
        num_slots = int(60 / time_span)
        if 60 % time_span != 0:
            num_slots += 1
        h = start
        while h < end:
        # for h in range(start, end):
            for i in range(0, num_slots):
                temp_h = h + i * int_span
                day_slot, am_pm = self.get_day_slot(temp_h)
                day_time_hour = int(temp_h)
                day_time_min = (temp_h - day_time_hour) * 60
                if temp_h >= 12:
                    day_time_hour -= 12
                day_time_min_str = str(int(day_time_min))
                day_time_hour_str = str(int(day_time_hour))

                if int(day_time_hour) < 10:
                    day_time_hour_str = '0' + str(int(day_time_hour))

                if int(day_time_min) < 10:
                    day_time_min_str = '0' + str(int(day_time_min))
                time_str = day_time_hour_str + ":" + day_time_min_str + " " + am_pm
                # temp_dict[temp_h] = time_str
                timing[day]['timing'][day_slot][temp_h] = time_str
            h += 1
        return timing

    def get_day_slot(self, time):
        am = 'AM'
        pm = 'PM'
        if time < 12:
            return self.MORNING, am
        elif time < 16:
            return self.AFTERNOON, pm
        else:
            return self.EVENING, pm


class IdListField(serializers.Field):
    def to_internal_value(self, data):
        try:
            id_str = data.strip(',')
            ids = set(map(int, id_str.split(",")))
        except:
            raise serializers.ValidationError("Wrong Ids")
        return ids


class SearchLabListSerializer(serializers.Serializer):
    min_distance = serializers.IntegerField(required=False)
    max_distance = serializers.IntegerField(required=False)
    min_price = serializers.IntegerField(required=False)
    max_price = serializers.IntegerField(required=False)
    long = serializers.FloatField(required=False)
    lat = serializers.FloatField(required=False)
    ids = IdListField(required=False)
    sort_on = serializers.CharField(required=False)
    name = serializers.CharField(required=False)
    network_id = serializers.IntegerField(required=False)


class UpdateStatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    time_slot_start = serializers.DateTimeField(required=False)
    time_slot_end = serializers.DateTimeField(required=False)
    start_date = serializers.CharField(required=False)
    start_time = serializers.FloatField(required=False)


class LabAppointmentRetrieveSerializer(LabAppointmentModelSerializer):
    profile = UserProfileSerializer()
    lab = LabModelSerializer()
    lab_test = AvailableLabTestSerializer(many=True)
    address = serializers.SerializerMethodField()
    type = serializers.ReadOnlyField(default='lab')

    def get_address(self, obj):
        resp_address = ""
        if obj.address:
            if obj.address.get("address"):
                resp_address += str(obj.address.get("address")).strip().replace(',','')
            if obj.address.get("land_mark"):
                if resp_address:
                    resp_address += ", "
                resp_address += str(obj.address.get("land_mark"))
            if obj.address.get("locality"):
                if resp_address:
                    resp_address += ", "
                resp_address += str(obj.address.get("locality"))
            if obj.address.get("pincode"):
                if resp_address:
                    resp_address += ", "
                resp_address += str(obj.address.get("pincode"))
        return resp_address

    class Meta:
        model = LabAppointment
        fields = ('id', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end','is_rated', 'rating_declined',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'profile', 'allowed_action', 'lab_test', 'lab', 'otp', 'address', 'type')


class DoctorLabAppointmentRetrieveSerializer(LabAppointmentModelSerializer):
    profile = UserProfileSerializer()
    lab = LabModelSerializer()
    lab_test = AvailableLabTestSerializer(many=True)

    class Meta:
        model = LabAppointment
        fields = ('id', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'profile', 'allowed_action', 'lab_test', 'lab')


class AppointmentCompleteBodySerializer(serializers.Serializer):
    lab_appointment = serializers.PrimaryKeyRelatedField(queryset=LabAppointment.objects.all())
    otp = serializers.IntegerField(max_value=9999)

    def validate(self, attrs):
        appointment = attrs.get('lab_appointment')
        if appointment.status == LabAppointment.COMPLETED:
            raise serializers.ValidationError("Appointment Already Completed.")
        elif appointment.status == LabAppointment.CANCELLED:
            raise serializers.ValidationError("Cannot Complete a Cancelled Appointment.")
        if not appointment.otp == attrs['otp']:
            raise serializers.ValidationError("Invalid OTP.")
        return attrs


class LabAppointmentFilterSerializer(serializers.Serializer):
    RANGE_CHOICES = ['all', 'previous', 'upcoming', 'pending']
    range = serializers.ChoiceField(choices=RANGE_CHOICES, required=False, default='all')
    lab_id = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.all(), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    date = serializers.DateField(required=False)


class LabReportFileSerializer(serializers.ModelSerializer):

    class Meta:
        model = LabReportFile
        fields = ('report', 'name')


class LabReportSerializer(serializers.Serializer):
    appointment = serializers.PrimaryKeyRelatedField(queryset=LabAppointment.objects.all())
    report_details = serializers.CharField(allow_blank=True, allow_null=True, required=False, max_length=300)
    name = serializers.FileField()

    def validate_appointment(self, value):
        request = self.context.get('request')

        if not LabAppointment.objects.filter(Q(id=value.id), (
                Q(lab__network__isnull=True, lab__manageable_lab_admins__user=request.user,
                  lab__manageable_lab_admins__is_disabled=False) |
                Q(lab__network__isnull=False,
                  lab__network__manageable_lab_network_admins__user=request.user,
                  lab__network__manageable_lab_network_admins__is_disabled=False))).exists():
            raise serializers.ValidationError("User is not authorized to upload report.")
        return value
