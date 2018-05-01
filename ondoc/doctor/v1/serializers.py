# from django.contrib.auth.models import User, Group
from collections import OrderedDict, defaultdict
import json 
import datetime
from rest_framework import serializers
from .services import RestructureDataService
from ondoc.doctor.models import (
        Doctor, Specialization, MedicalService, DoctorImage, Symptoms,
        DoctorQualification, DoctorImage, DoctorHospital, DoctorExperience, DoctorLanguage, OpdAppointment, Hospital, UserProfile, Hospital
    ) 


class DoctorExperienceSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorExperience
        fields = ('doctor', 'hospital', 'start_year', 'end_year', )


class DoctorLanguageSerializer(serializers.ModelSerializer):

    language = serializers.ReadOnlyField(source='language.name')

    class Meta:
        model = DoctorLanguage
        fields = ('language', )


class DoctorHospitalSerializer(serializers.ModelSerializer):
    doctor = serializers.ReadOnlyField(source='doctor.name')
    hospital = serializers.ReadOnlyField(source='hospital.name')
    address = serializers.ReadOnlyField(source='hospital.address')
    hospital_id = serializers.ReadOnlyField(source='hospital.pk')

    def create(self, validated_data):
        return DoctorHospital.objects.create(**validated_data)

    def validate(self, data):
        doctor = Doctor.objects.get(id=self.context['doctor_id'])
        hospital = Hospital.objects.get(id=self.context['hospital_id'])

        data['doctor'] = doctor
        data['hospital'] = hospital
        
        return data

    class Meta:
        model = DoctorHospital
        fields = ('doctor', 'hospital', 'address', 'hospital_id', 'day', 'start', 'end', 'fees', )


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


class DoctorApiReformData(DoctorSerializer):
    """Used to restructure api data to match as requirements"""

    def to_representation(self, doctor):
        parent_rep = super().to_representation(doctor)
        restruct_obj = RestructureDataService()
        
        try:
            parent_rep['availability'] = restruct_obj.reform_availability(parent_rep['availability'])
        except KeyError as e:
            return parent_rep

        # reform timings in a particular day
        for hospital in parent_rep['availability']:
            hospital['days'] = restruct_obj.reform_timings(hospital['days'])
        return parent_rep


class SpecializationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specialization
        fields = ('id', 'name', )


class MedicalServiceSerializer(serializers.ModelSerializer):

    class Meta:
        model = MedicalService
        fields = ('id', 'name', )


class SymptomsSerializer(serializers.ModelSerializer):

    class Meta:
        model = Symptoms
        fields = ('id', 'name', )


class DoctorProfileSerializer(serializers.ModelSerializer):
    
    profile_img = DoctorImageSerializer(read_only=True, many = True)
    qualificationSpecialization = DoctorQualificationSerializer(read_only=True, many = True)
    languages = DoctorLanguageSerializer(read_only=True, many = True)
    availability = DoctorHospitalSerializer(read_only=True, many = True)

    class Meta:
        model = Doctor
        fields = ( 'id', 'name', 'gender', 'phone_number', 'email', 'practice_duration', 'profile_img', 'languages', 'qualificationSpecialization', 'availability')


class OpdAppointmentSerializer(serializers.ModelSerializer):

    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')
    patient_name = serializers.ReadOnlyField(source='profile.name')
    patient_dob = serializers.ReadOnlyField(source='profile.dob')
    patient_gender = serializers.ReadOnlyField(source='profile.gender')
    patient_image = serializers.ReadOnlyField(source='profile.profile_image.url')

    def create(self, validated_data):
        return OpdAppointment.objects.create(**validated_data)

    def validate(self, data):
        doctor = Doctor.objects.get(id=self.context['doctor_id'])
        hospital = Hospital.objects.get(id=self.context['hospital_id'])
        profile = UserProfile.objects.get(id=self.context['profile_id'])

        data['doctor'] = doctor
        data['hospital'] = hospital
        data['profile'] = profile
        
        return data

    class Meta:
        model = OpdAppointment
        fields = ('id', 'time_slot_start', 'fees', 'time_slot_end', 'status', 'doctor_name', 'hospital_name', 'patient_name', 'patient_dob', 'patient_gender', 'patient_image')


class HospitalSerializer(serializers.ModelSerializer):

    def create(self, validated_data):
        return Hospital.objects.create(**validated_data)

    def validate(self, data):        
        return data

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'address', 'location', 'years_operational', 'building', 'pin_code', 'state', 'city', 'locality', 'hospital_type')