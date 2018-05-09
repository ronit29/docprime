from rest_framework import serializers
from ondoc.doctor.models import (OpdAppointment, User, Doctor, Hospital, UserProfile)


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField()


class OpdAppointmentSerializer(serializers.ModelSerializer):

    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')
    patient_name = serializers.ReadOnlyField(source='profile.name')
    patient_dob = serializers.ReadOnlyField(source='profile.dob')
    # patient_gender = serializers.ReadOnlyField(source='profile.gender')

    class Meta:
        model = OpdAppointment
        # fields = ('id', 'time_slot_start', 'fees', 'time_slot_end', 'status', 'doctor_name', 'hospital_name', 'patient_name', 'patient_dob', 'patient_gender', 'patient_image')
        fields =  '__all__'


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
        return data