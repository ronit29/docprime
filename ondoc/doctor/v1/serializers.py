# from django.contrib.auth.models import User, Group
from collections import OrderedDict, defaultdict
import json 
import datetime
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
    address = serializers.ReadOnlyField(source='hospital.address')
    hospital_id = serializers.ReadOnlyField(source='hospital.pk')

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
        
        try:
            parent_rep['availability'] = self.reform_availability(parent_rep['availability'])
        except KeyError as e:
            return parent_rep

        # reform timings in a particular day
        for hospital in parent_rep['availability']:
            hospital['days'] = self.reform_timings(hospital['days'])
        return parent_rep


    def reform_timings(self, days):
        sorted_results_by_days = defaultdict(list)
        result = []

        # sorting results by hospital id
        for avl in days:
            sorted_results_by_days[avl['day']].append(avl)

        for key,val in sorted_results_by_days.items():
            temp = {"day": key, 'time': []}
            for v in val:
                temp['time'].append({
                    'from': v['start'],
                    'to': v['end'],
                    'fee': v['fees']
                })
            result.append(temp)

        return result


    def reform_availability(self, availability):
        sorted_results_by_hospitals = defaultdict(list)
        result = []

        today = datetime.datetime.today().weekday() + 1
        curr_hour = datetime.datetime.now().hour

        # sorting results by hospital id
        for avl in availability:
            sorted_results_by_hospitals[avl['hospital_id']].append(avl)

        for key,val in sorted_results_by_hospitals.items():
            temp = {"hospital_id": key, 'days': [], 'nextAvailable': []}
            for v in val:
                temp['name'] = v['hospital']
                temp['address'] = v['address']
                temp['days'].append({'day': v['day'], 'start': v['start'], 
                    'end': v['end'], 'fees': v['fees']})

                if v['day'] == today and v['start'] > curr_hour:
                    temp['nextAvailable'].append({
                        'day': 0,
                        'from': v['start'],
                        'to': v['end'],
                        'fee': {
                            'amount': v['fees'],
                            'discounted': 0, 
                        }
                    })
                else:
                    temp['nextAvailable'].append({
                        'day': (v['day'] - today) if v['day'] - today >= 0 else (v['day'] - today + 7),
                        'from': v['start'],
                        'to': v['end'],
                        'fee': {
                            'amount': v['fees'],
                            'discounted': 0, 
                        }
                    })
                sorted(temp['nextAvailable'], key = lambda x: (x['day'], x['from']))
            result.append(temp)

        return result


class SpecializationSerializer(serializers.ModelSerializer):

    class Meta:
        model = Specialization
        fields = ('id', 'name', )


class MedicalServiceSerializer(serializers.ModelSerializer):

    class Meta:
        model = MedicalService
        fields = ('id', 'name', )

