from rest_framework import serializers
from django.db.models import Q
from ondoc.doctor.models import (OpdAppointment, Doctor, Hospital, UserProfile, DoctorHospital)
from django.utils import timezone


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField()


class OpdAppointmentSerializer(serializers.ModelSerializer):

    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')
    patient_name = serializers.ReadOnlyField(source='profile.name')
    patient_dob = serializers.ReadOnlyField(source='profile.dob')
    patient_gender = serializers.ReadOnlyField(source='profile.gender'),
    patient_image = serializers.SerializerMethodField()

    class Meta:
        model = OpdAppointment
        exclude = ('created_at', 'updated_at',)

    def get_patient_image(self, obj):
        if obj.profile.profile_image:
            return obj.profile.profile_image
        else:
            return None


class SetAppointmentSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all())
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    time_slot_start = serializers.DateTimeField()
    time_slot_end = serializers.DateTimeField()

    def validate(self, data):
        request = self.context.get("request")
        user_profile = UserProfile.objects.filter(pk=int(data.get("profile").id)).first()
        if not user_profile:
            raise serializers.ValidationError("Profile does not exists.")
        if not user_profile.user == request.user:
            raise serializers.ValidationError("Profile of user is not correct")
        if OpdAppointment.objects.filter(~Q(status=OpdAppointment.REJECTED),
                                         profile=data.get('profile').id).count() >= 3:
            raise serializers.ValidationError("Can not create more than 3 appointments at a time.")
        return data


class UpdateStatusSerializer(serializers.Serializer):
    DOCTOR_ALLOWED_CHOICES = [OpdAppointment.ACCEPTED, OpdAppointment.RESCHEDULED]
    PATIENT_ALLOWED_CHOICES = [OpdAppointment.REJECTED, OpdAppointment.RESCHEDULED]
    STATUS_CHOICES = ((OpdAppointment.ACCEPTED, "Accepted"),
                      (OpdAppointment.RESCHEDULED, "Rescheduled"),
                      (OpdAppointment.REJECTED, "Rejected"))
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    time_slot_start = serializers.DateTimeField(required=False)
    time_slot_end = serializers.DateTimeField(required=False)

    def validate(self, data):
        request = self.context.get("request")
        opd_appointment = self.context.get("opd_appointment")
        current_datetime = timezone.now()
        if request.user.user_type == 2 and not (data.get('status') in self.DOCTOR_ALLOWED_CHOICES):
            raise serializers.ValidationError("Not a valid status for the user.")
        if request.user.user_type == 3 and (not data.get('status') in self.PATIENT_ALLOWED_CHOICES):
            raise serializers.ValidationError("Not a valid status for the user.")
        if request.user.user_type == 2 and data.get('status') == OpdAppointment.ACCEPTED and (
                current_datetime > opd_appointment.time_slot_start):
            raise serializers.ValidationError("Can not accept appointment after time slot has passed.")
        if request.user.user_type == 2 and data.get('status') == OpdAppointment.RESCHEDULED and (
                current_datetime > opd_appointment.time_slot_start):
            raise serializers.ValidationError("Can not reschedule appointment after time slot has passed.")
        if request.user.user_type == 3 and data.get('status') == OpdAppointment.RESCHEDULED:
            if not (data.get('time_slot_start')):
                raise serializers.ValidationError("time_slot_start is required.")
            if not (data.get('time_slot_end')):
                raise serializers.ValidationError("time_slot_end is required.")
            if DoctorHospital.objects.filter(doctor=opd_appointment.doctor, hospital=opd_appointment.hospital).filter(
                    day=data.get('time_slot_start').weekday(), start__lte=data.get("time_slot_start").hour,
                    end__gte=data.get("time_slot_end").hour).exists():
                raise serializers.ValidationError("Doctor is not available.")
        return data
