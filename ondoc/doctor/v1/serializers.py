# from django.contrib.auth.models import User, Group
from rest_framework import serializers
from ondoc.doctor.models import (
        Doctor, Specialization, MedicalService, DoctorImage,
        DoctorQualification, DoctorImage, DoctorHospital, DoctorExperience,
    ) 


class DoctorExperienceSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorExperience
        fields = ('doctor', 'hospital', 'start_year', 'end_year', )


class DoctorHospitalSerializer(serializers.ModelSerializer):
    doctor = serializers.ReadOnlyField(source='doctor.name')
    hospital = serializers.ReadOnlyField(source='hospital.name')

    class Meta:
        model = DoctorHospital
        fields = ('doctor', 'hospital', 'day', 'start', 'end', 'fees', )


class DoctorQualificationSerializer(serializers.ModelSerializer):
    qualification = serializers.ReadOnlyField(source='qualification.name')
    specialization = serializers.ReadOnlyField(source='specialization.name')

    class Meta:
        model = DoctorQualification
        fields = ('qualification', 'specialization', )


class DoctorImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = DoctorImage
        fields = ('name', )


class DoctorSerializer(serializers.ModelSerializer):
    profile_img = DoctorImageSerializer(read_only=True, many = True)
    qualificationSpecialization = DoctorQualificationSerializer(read_only=True, many = True)
    availability = DoctorHospitalSerializer(read_only=True, many = True)
    pastExperience = DoctorExperienceSerializer(read_only=True, many = True)

    class Meta:
        model = Doctor
        fields = ('id', 'name', 'practice_duration', 'profile_img', 'qualificationSpecialization',
                 'email', 'availability', 'pastExperience' )


class SpecializationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specialization
        fields = ('id', 'name', )


class MedicalServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = MedicalService
        fields = ('id', 'name', )

