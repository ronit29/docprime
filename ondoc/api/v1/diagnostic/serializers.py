from rest_framework import serializers
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition, LabImage)
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.authentication.models import UserProfile, Address
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
from ondoc.api.v1.auth.serializers import AddressSerializer, UserProfileSerializer
from ondoc.api.v1.utils import form_time_slot
from ondoc.doctor.models import OpdAppointment
from django.db.models import Count, Sum, When, Case, Q, F
from django.contrib.auth import get_user_model
from collections import OrderedDict
import datetime
import pytz
import json
import decimal
import random

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

    def get_lab_thumbnail(self, obj):
        request = self.context.get("request")
        if not request:
            raise ValueError("request is not passed in serializer.")
        return request.build_absolute_uri(obj.get_thumbnail()) if obj.get_thumbnail() else None

    def get_lat(self,obj):
        if obj.location:
            return obj.location.y

    def get_long(self,obj):
        if obj.location:
            return obj.location.x

    def get_address(self, obj):
        address = ''
        if obj.building:
            address += str(obj.building)
        if obj.locality:
            address += str(obj.locality) + ' , '
        if obj.sublocality:
            address += str(obj.sublocality) + ' , '
        if obj.city:
            address += str(obj.city) + ' , '
        if obj.state:
            address += str(obj.state) + ' , '
        if obj.country:
            address += str(obj.country)
        return address

    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'address', 'lab_image', 'lab_thumbnail', 'name', 'operational_since', 'locality',
                  'sublocality', 'city', 'state', 'country', 'always_open', 'about', 'home_pickup_charges',
                  'is_home_collection_enabled', )


class LabProfileSerializer(LabModelSerializer):

    class Meta:
        model = Lab
        fields = ('id', 'lat', 'long', 'address', 'lab_image', 'lab_thumbnail', 'name', 'operational_since', 'locality',
                  'sublocality', 'city', 'state', 'country', 'about', 'always_open', 'building', )

class AvailableLabTestSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')
    agreed_price = serializers.SerializerMethodField()
    deal_price = serializers.SerializerMethodField()
    is_home_pickup_available = serializers.SerializerMethodField()

    def get_is_home_pickup_available(self, obj):
        if obj.lab.is_home_collection_enabled and obj.test.home_collection_possible:
            return True
        return False

    def get_agreed_price(self, obj):
        agreed_price = obj.computed_agreed_price if obj.custom_agreed_price is None else obj.custom_agreed_price
        return agreed_price

    def get_deal_price(self, obj):
        deal_price = obj.computed_deal_price if obj.custom_deal_price is None else obj.custom_deal_price
        return deal_price

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', 'agreed_price', 'deal_price', 'enabled', 'is_home_pickup_available', )


class LabCustomSerializer(serializers.Serializer):
    # lab = serializers.SerializerMethodField()
    lab = LabModelSerializer()
    price = serializers.IntegerField(default=None)
    distance = serializers.IntegerField(source='distance.m')
    pickup_available = serializers.IntegerField(default=0)
    lab_timing = serializers.CharField(max_length=200)
    lab_timing_data = serializers.ListField()

    # def get_lab(self, obj):
    #     queryset = Lab.objects.get(pk=obj['lab'])
    #     serializer = LabModelSerializer(queryset)
    #     return serializer.data


class CommonTestSerializer(serializers.ModelSerializer):
    id = serializers.ReadOnlyField(source='test.id')
    name = serializers.ReadOnlyField(source='test.name')

    class Meta:
        model = CommonTest
        fields = ('id', 'name', )


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
        fields = ('id', 'lab', 'lab_test', 'profile', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'patient_thumbnail', 'patient_name')


class LabAppTransactionModelSerializer(serializers.Serializer):
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


class LabAppRescheduleModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = LabAppointment
        fields = '__all__'


class LabAppointmentUpdateSerializer(serializers.Serializer):
    appointment_status = [LabAppointment.CREATED, LabAppointment.ACCEPTED, LabAppointment.RESCHEDULED_LAB,
                          LabAppointment.CANCELED, LabAppointment.RESCHEDULED_PATIENT, LabAppointment.COMPLETED,
                          LabAppointment.BOOKED]
    status = serializers.ChoiceField(choices=appointment_status)
    start_time = serializers.DateTimeField(required=False)
    end_time = serializers.DateTimeField(required=False)

    def validate(self, data):
        temp_data = data
        temp_data["lab_id"] = self.context["lab_id"]
        LabAppointmentCreateSerializer.time_slot_validator(temp_data)

        return data

    def create(self, data):
        pass

    def update(self, instance, data):
        # if data['status'] == LabAppointment.RESCHEDULED_PATIENT:
        #     self.reschedule_validation(instance, data)
        # elif data['status'] == LabAppointment.CANCELED:
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
    start_date = serializers.CharField()
    start_time = serializers.FloatField()
    end_date = serializers.CharField(required=False)
    end_time = serializers.FloatField(required=False)
    is_home_pickup = serializers.BooleanField(default=False)
    address = serializers.IntegerField(required=False, allow_null=True)
    payment_type = serializers.IntegerField(default=OpdAppointment.PREPAID)

    def validate(self, data):
        request = self.context.get("request")
        if data.get("is_home_pickup") is True and (not data.get("address")):
            raise serializers.ValidationError("Address required for home pickup")
        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            raise serializers.ValidationError("Invalid profile id")
        self.test_lab_id_validator(data)
        self.time_slot_validator(data)
        return data

    def create(self, data):
        deal_price_calculation= Case(When(custom_deal_price__isnull=True, then=F('computed_deal_price')),
                                     When(custom_deal_price__isnull=False, then=F('custom_deal_price')))
        agreed_price_calculation = Case(When(custom_agreed_price__isnull=True, then=F('computed_agreed_price')),
                                      When(custom_agreed_price__isnull=False, then=F('custom_agreed_price')))

        self.num_appointment_validator(data)
        lab_test_queryset = AvailableLabTest.objects.filter(lab=data["lab"], test__in=data['test_ids'])
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
    def test_lab_id_validator(data):
        if not data['test_ids']:
            raise serializers.ValidationError(" No Test Ids given")
        avail_test_queryset = AvailableLabTest.objects.filter(lab=data["lab"], test__in=data['test_ids']).values(
            'id')

        if len(avail_test_queryset) != len(data['test_ids']):
            raise serializers.ValidationError("Test Ids or lab Id is incorrect")

    @staticmethod
    def time_slot_validator(data):
        start_dt = (CreateAppointmentSerializer.form_time_slot(data.get('start_date'), data.get('start_time')) if not data.get("time_slot_start") else data.get("time_slot_start"))

        day_of_week = start_dt.weekday()
        start_hour = round(float(start_dt.hour) + (float(start_dt.minute) * 1 / 60), 2)

        lab_queryset = data['lab']

        if data["is_home_pickup"] and not lab_queryset.is_home_collection_enabled:
            raise serializers.ValidationError("Home Pickup is disabled for the lab")

        if not data["is_home_pickup"] and lab_queryset.always_open:
            return

        lab_timing_queryset = lab_queryset.lab_timings.filter(day=day_of_week, start__lte=start_hour, end__gte=start_hour, for_home_pickup=data["is_home_pickup"]).exists()

        if not lab_timing_queryset:
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
    order_by = serializers.CharField(required=False)


class LabAppointmentRetrieveSerializer(LabAppointmentModelSerializer):
    profile = UserProfileSerializer()
    allowed_action = serializers.SerializerMethodField()
    lab = LabModelSerializer()
    lab_test = AvailableLabTestSerializer(many=True)

    def get_allowed_action(self,obj):
        user_type = ''
        if self.context.get('request'):
            user_type = self.context['request'].user.user_type
            return LabAppointment.allowed_action(obj, user_type)
        else:
            return []

    class Meta:
        model = LabAppointment
        fields = ('id', 'type', 'lab_name', 'status', 'deal_price', 'effective_price', 'time_slot_start', 'time_slot_end',
                   'is_home_pickup', 'lab_thumbnail', 'lab_image', 'profile', 'allowed_action', 'lab_test', 'lab')
