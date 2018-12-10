# from django.contrib.auth.models import User, Group
from collections import OrderedDict, defaultdict
import json 
import datetime
from rest_framework import serializers
from .services import RestructureDataService
from datetime import datetime

from ondoc.doctor.models import (
        Doctor, Specialization, MedicalService, DoctorImage, Symptoms,
        DoctorQualification, DoctorImage, DoctorHospital, DoctorExperience, DoctorLanguage, OpdAppointment, Hospital, DoctorEmail, DoctorMobile, DoctorMedicalService, DoctorAssociation, DoctorAward, DoctorLeave
    )


class DoctorExperienceSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorExperience
        fields = ('hospital', 'start_year', 'end_year', )


class DoctorEmailSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorEmail
        fields = ('email', 'is_primary')


class DoctorAssociationSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorAssociation
        fields = ('name', 'id')


class DoctorMobileSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorMobile
        fields = ('number', 'is_primary')


class DoctorAwardSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorAward
        fields = ('name', 'year')


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
        
        data['doctor'] = self.context['doctor']
        data['hospital'] = self.context['hospital']
        
        return data

    class Meta:
        model = DoctorHospital
        fields = ('doctor', 'hospital', 'address', 'hospital_id', 'day', 'start', 'end', 'fees', )


class DoctorQualificationSerializer(serializers.ModelSerializer):
    qualification = serializers.ReadOnlyField(source='qualification.name')
    specialization = serializers.ReadOnlyField(source='specialization.name')
    college = serializers.ReadOnlyField(source='college.name')

    class Meta:
        model = DoctorQualification
        fields = ('passing_year' , 'qualification', 'specialization', 'college')


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


class ArticleAuthorSerializer(DoctorSerializer):
    class Meta:
        model = Doctor
        fields = ('id', 'name')


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

    name = serializers.ReadOnlyField(source='service.name')
    description = serializers.ReadOnlyField(source='service.name')

    class Meta:
        model = DoctorMedicalService
        fields = ('id', 'name', 'description')


class SymptomsSerializer(serializers.ModelSerializer):

    class Meta:
        model = Symptoms
        fields = ('id', 'name', )


class DoctorProfileSerializer(serializers.ModelSerializer):
    
    images = DoctorImageSerializer(read_only=True, many = True)
    qualifications = DoctorQualificationSerializer(read_only=True, many = True)
    languages = DoctorLanguageSerializer(read_only=True, many = True)
    availability = DoctorHospitalSerializer(read_only=True, many = True)
    emails = DoctorEmailSerializer(read_only=True, many = True)
    mobiles = DoctorMobileSerializer(read_only=True, many = True)
    medical_services = MedicalServiceSerializer(read_only=True, many = True)
    experiences = DoctorExperienceSerializer(read_only=True, many = True)
    associations = DoctorAssociationSerializer(read_only=True, many = True)
    awards = DoctorAwardSerializer(read_only=True, many = True)

    def to_representation(self, doctor):
        parent_rep = super().to_representation(doctor)
        try:
            parent_rep['images'] = parent_rep['images'][0]
        except KeyError as e:
            return parent_rep

        return parent_rep

    class Meta:
        model = Doctor
        fields = ( 'id', 'name', 'gender', 'about', 'license', 'additional_details', 'emails', 'practicing_since', 'images', 'languages', 'qualifications', 'availability', 'mobiles', 'medical_services', 'experiences', 'associations', 'awards', 'appointments')


class OpdAppointmentSerializer(serializers.ModelSerializer):

    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')
    patient_name = serializers.ReadOnlyField(source='profile.name')
    patient_dob = serializers.ReadOnlyField(source='profile.dob')
    patient_gender = serializers.ReadOnlyField(source='profile.gender')
    patient_image = serializers.ReadOnlyField(source='profile.profile_image.url')

    def create(self, validated_data):
        return OpdAppointment.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance

    def validate(self, data):

        data['doctor'] = self.context['doctor']
        data['hospital'] = self.context['hospital']
        data['profile'] = self.context['profile']
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
        fields = ('id', 'name', 'address', 'location', 'operational_since', 'building', 'pin_code', 'state', 'city', 'locality', 'hospital_type')


class DoctorLeaveSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='doctor.name')

    def create(self, validated_data):
        return DoctorLeave.objects.create(**validated_data)

    def update(self, instance, validated_data):
        instance.status = validated_data.get('status', instance.status)
        instance.save()
        return instance

    def validate(self, data):
        data['doctor'] = self.context['doctor']
        return data

    class Meta:
        model = DoctorLeave
        fields = ('id', 'start_time', 'end_time', 'start_date', 'end_date', 'doctor_name')

