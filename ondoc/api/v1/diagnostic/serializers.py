from rest_framework import serializers
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition, LabImage)
from ondoc.authentication.models import UserProfile, Address
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
from django.db.models import Count, Sum
from django.contrib.auth import get_user_model
from collections import OrderedDict
import datetime
import pytz
import json

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
        exclude = ('created_at', 'updated_at',)


class LabModelSerializer(serializers.ModelSerializer):

    lat = serializers.FloatField(source='location.y')
    long = serializers.FloatField(source='location.x')
    address = serializers.SerializerMethodField()
    lab_image = LabImageModelSerializer(many=True)

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
        # fields = '__all__'
        exclude = ('created_at', 'updated_at', 'location', 'location_error', )


class AvailableLabTestSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()
    test_id = serializers.ReadOnlyField(source='test.id')

    class Meta:
        model = AvailableLabTest
        fields = ('test_id', 'mrp', 'test', )
        # exclude = ('lab', 'agreed_price', 'deal_price')


class LabCustomSerializer(serializers.Serializer):
    # lab = serializers.SerializerMethodField()
    lab = LabModelSerializer()
    price = serializers.IntegerField(default=None)
    distance = serializers.IntegerField(source='distance.m')
    pickup_available = serializers.IntegerField(default=0)

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

    class Meta:
        model = CommonDiagnosticCondition
        fields = ('id', 'name', )


class PromotedLabsSerializer(serializers.ModelSerializer):
    # lab = LabModelSerializer()
    id = serializers.ReadOnlyField(source='lab.id')
    name = serializers.ReadOnlyField(source='lab.name')

    class Meta:
        model = PromotedLab
        fields = ('id', 'name', )


class LabAppointmentModelSerializer(serializers.ModelSerializer):
    type = serializers.ReadOnlyField(default="lab")

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
        if data['status'] == LabAppointment.RESCHEDULED_PATIENT:
            self.reschedule_validation(instance, data)
            instance.time_slot_start = data.get("start_time", instance.time_slot_start)
            instance.time_slot_end = data.get("end_time", instance.time_slot_end)
        elif data['status'] == LabAppointment.CANCELED:
            self.cancel_validation(instance, data)
        else:
            raise serializers.ValidationError("Invalid Status")
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
    lab = serializers.PrimaryKeyRelatedField(queryset=Lab.objects.all())
    test_ids = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=LabTest.objects.all()))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    start_date = serializers.CharField()
    start_time = serializers.FloatField()
    end_date = serializers.CharField(required=False)
    end_time = serializers.FloatField(required=False)

    def validate(self, data):

        self.test_lab_id_validator(data)

        self.profile_validator(data)

        self.time_slot_validator(data)

        return data

    def create(self, data):

        self.num_appointment_validator(data)

        appointment_data = dict()
        appointment_data['lab'] = Lab.objects.get(pk=data["lab"])
        appointment_data['profile'] = UserProfile.objects.get(pk=data["profile"])

        lab_test_queryset = AvailableLabTest.objects.filter(lab=data["lab"], test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab').annotate(total_mrp=Sum("mrp"), total_deal_price=Sum("deal_price"))

        total_deal_price = total_mrp = 0
        if temp_lab_test:
            total_mrp = temp_lab_test[0].get("total_mrp", 0)
            total_deal_price = temp_lab_test[0].get("total_deal_price", 0)

        appointment_data['price'] = total_mrp
        appointment_data['time_slot_start'] = data["start_time"]
        appointment_data['time_slot_end'] = data["end_time"]
        profile_detail = dict()
        profile_model = appointment_data["profile"]
        profile_detail["name"] = profile_model.name
        profile_detail["gender"] = profile_model.gender
        profile_detail["dob"] = profile_model.dob
        profile_detail["profile_image"] = profile_model.profile_image
        appointment_data['profile_detail'] = json.dumps(profile_detail)

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
                                               status__in=ACTIVE_APPOINTMENT_STATUS).exists())
        if count >= 2:
            raise serializers.ValidationError("More than 2 appointment with the lab")

    @staticmethod
    def test_lab_id_validator(data):
        if not data['test_ids']:
            raise serializers.ValidationError(" No Test Ids given")
        avail_test_queryset = AvailableLabTest.objects.filter(lab=data["lab_id"], test__in=data['test_ids']).values(
            'id')

        if len(avail_test_queryset) != len(data['test_ids']):
            raise serializers.ValidationError("Test Ids or lab Id is incorrect")

    @staticmethod
    def profile_validator(data):
        profile_queryset = UserProfile.objects.filter(pk=data['profile_id'])
        if not profile_queryset:
            raise serializers.ValidationError("Profile Id is incorrect")

    @staticmethod
    def time_slot_validator(data):
        start_dt = CreateAppointmentSerializer.form_time_slot(data.get('start_date'), data.get('start_time'))
        if start_dt > data['end_time']:
            raise serializers.ValidationError("Invalid Time Slot")

        day_of_week = start_dt.weekday()
        start_hour = start_dt.hour
        end_hour = int(data['end_time'])
        # end_hour = data['end_time'].hour
        lab_timing_queryset = LabTiming.objects.filter(lab=data['lab'], day=day_of_week, start__lte=start_hour,
                                                       end__gte=end_hour)
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
