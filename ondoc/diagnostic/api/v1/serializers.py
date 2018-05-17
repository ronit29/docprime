from rest_framework import serializers
from ondoc.diagnostic.models import (LabTest, AvailableLabTest, Lab, LabAppointment, LabTiming, PromotedLab,
                                     CommonTest, CommonDiagnosticCondition)
from ondoc.authentication.models import UserProfile
from django.db.models import Count, Sum
from django.db.models import Q

import datetime
import pytz

utc = pytz.UTC


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


class LabModelSerializer(serializers.ModelSerializer):

    lat = serializers.SerializerMethodField()
    long = serializers.SerializerMethodField()

    def get_lat(self, obj):
        return obj.location.y

    def get_long(self, obj):
        return obj.location.x

    class Meta:
        model = Lab
        # fields = '__all__'
        exclude = ('created_at', 'updated_at', 'location', 'location_error', )


class AvailableLabTestSerializer(serializers.ModelSerializer):
    test = LabTestSerializer()

    class Meta:
        model = AvailableLabTest
        # fields = '__all__'
        exclude = ('lab', 'agreed_price', 'deal_price')


class LabCustomSerializer(serializers.Serializer):
    lab = serializers.SerializerMethodField()
    price = serializers.IntegerField()

    def get_lab(self, obj):
        queryset = Lab.objects.get(pk=obj['lab'])
        serializer = LabModelSerializer(queryset)
        return serializer.data


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
        now = datetime.datetime.now().replace(tzinfo=utc)
        if instance.time_slot_start < now and data['start_time'] < now:
            raise serializers.ValidationError("Cannot Reschedule")

    def cancel_validation(self, instance, data):
        now = datetime.datetime.now().replace(tzinfo=utc)
        if instance.time_slot_start < now:
            raise serializers.ValidationError("Cannot Cancel")


class LabAppointmentCreateSerializer(serializers.Serializer):
    lab_id = serializers.IntegerField()
    test_ids = serializers.ListField(child=serializers.IntegerField())
    profile_id = serializers.IntegerField()
    start_time = serializers.DateTimeField()
    end_time = serializers.DateTimeField()

    def validate(self, data):

        self.test_lab_id_validator(data)

        self.profile_validator(data)

        self.time_slot_validator(data)

        return data

    def create(self, data):

        self.num_appointment_validator(data)

        appointment_data = dict()
        appointment_data['lab'] = Lab.objects.get(pk=data["lab_id"])
        appointment_data['profile'] = UserProfile.objects.get(pk=data["profile_id"])

        lab_test_queryset = AvailableLabTest.objects.filter(lab=data["lab_id"], test__in=data['test_ids'])
        temp_lab_test = lab_test_queryset.values('lab').annotate(total_mrp=Sum("mrp"), total_deal_price=Sum("deal_price"))

        total_deal_price = total_mrp = 0
        if temp_lab_test:
            total_mrp = temp_lab_test[0].get("total_mrp", 0)
            total_deal_price = temp_lab_test[0].get("total_deal_price", 0)

        appointment_data['price'] = total_mrp
        appointment_data['time_slot_start'] = data["start_time"]
        appointment_data['time_slot_end'] = data["end_time"]

        queryset = LabAppointment.objects.create(**appointment_data)
        queryset.lab_test.add(*lab_test_queryset)

        return queryset

    def update(self, instance, data):
        pass

    @staticmethod
    def num_appointment_validator(data):
        count = LabAppointment.objects.filter(lab=data['lab_id'], profile=data['profile_id']).\
            exclude(status=LabAppointment.REJECTED).count()
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
        if data['start_time'] > data['end_time']:
            raise serializers.ValidationError("Invalid Time Slot")

        day_of_week = data['start_time'].weekday()
        start_hour = data['start_time'].hour
        end_hour = data['end_time'].hour
        lab_timing_queryset = LabTiming.objects.filter(lab=data['lab_id'], day=day_of_week, start__lte=start_hour,
                                                       end__gte=end_hour)
        if not lab_timing_queryset:
            raise serializers.ValidationError("No time slot available")


class LabTimingModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = LabTiming
        fields = ('id', 'day', 'start', 'end')
