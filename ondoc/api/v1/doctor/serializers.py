from rest_framework import serializers
from django.db.models import Q
from ondoc.doctor.models import (OpdAppointment, Doctor, Hospital, UserProfile, DoctorHospital, DoctorAssociation,
                                 DoctorAward, DoctorDocument, DoctorEmail, DoctorExperience, DoctorImage, DoctorLanguage
                                 , DoctorMedicalService, DoctorMobile, DoctorQualification)
from django.utils import timezone
from django.contrib.auth import get_user_model
User = get_user_model()


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField()

class AppointmentFilterSerializer(serializers.Serializer):
    CHOICES = ['all', 'previous', 'upcoming', 'pending']

    range = serializers.ChoiceField(choices=CHOICES, required=False)
    hospital_id = serializers.IntegerField(required=False)

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


class CreateAppointmentSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all())
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all())
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    time_slot_start = serializers.DateTimeField()
    time_slot_end = serializers.DateTimeField()

    def validate(self, data):
        ACTIVE_APPOINTMENT_STATUS = [OpdAppointment.CREATED, OpdAppointment.ACCEPTED, OpdAppointment.RESCHEDULED]
        MAX_APPOINTMENTS_ALLOWED = 3
        MAX_FUTURE_DAY = 7
        request = self.context.get("request")
        time_slot_start = data.get("time_slot_start")
        time_slot_end = data.get("time_slot_end")

        if not request.user.user_type == User.CONSUMER:
            raise serializers.ValidationError("Not allowed to create appointment")

        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            raise serializers.ValidationError("Invalid profile id")

        if time_slot_start<timezone.now():
            raise serializers.ValidationError("Cannot book in past")

        delta = time_slot_start - timezone.now()
        if delta.days > MAX_FUTURE_DAY:
            raise serializers.ValidationError("Cannot book appointment more than "+str(MAX_FUTURE_DAY)+" days ahead")


        if not DoctorHospital.objects.filter(doctor=data.get('doctor'), hospital=data.get('hospital'),
            day=time_slot_start.weekday(),start__lte=time_slot_start.hour, end__gte=time_slot_start.hour).exists():
            raise serializers.ValidationError("Invalid slot")

        if OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, doctor = data.get('doctor')).exists():
            raise serializers.ValidationError('Cannot book appointment with same doctor again')

        if OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile = data.get('profile')).count()>=MAX_APPOINTMENTS_ALLOWED:
            raise serializers.ValidationError('Max'+str(MAX_APPOINTMENTS_ALLOWED)+' active appointments are allowed')

        return data


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
        if request.user.user_type == User.DOCTOR and not (data.get('status') in self.DOCTOR_ALLOWED_CHOICES):
            raise serializers.ValidationError("Not a valid status for the user.")
        if request.user.user_type == User.CONSUMER and (not data.get('status') in self.PATIENT_ALLOWED_CHOICES):
            raise serializers.ValidationError("Not a valid status for the user.")
        if request.user.user_type == User.DOCTOR and data.get('status') == OpdAppointment.ACCEPTED and (
                current_datetime > opd_appointment.time_slot_start):
            raise serializers.ValidationError("Can not accept appointment after time slot has passed.")
        if request.user.user_type == User.DOCTOR and data.get('status') == OpdAppointment.RESCHEDULED and (
                current_datetime > opd_appointment.time_slot_start):
            raise serializers.ValidationError("Can not reschedule appointment after time slot has passed.")
        if request.user.user_type == User.CONSUMER and data.get('status') == OpdAppointment.RESCHEDULED:
            if not (data.get('time_slot_start')):
                raise serializers.ValidationError("time_slot_start is required.")
            if not (data.get('time_slot_end')):
                raise serializers.ValidationError("time_slot_end is required.")
            if (not DoctorHospital
                    .objects.filter(doctor=opd_appointment.doctor, hospital=opd_appointment.hospital)
                    .filter(day=data.get('time_slot_start').weekday(), start__lte=data.get("time_slot_start").hour,
                            end__gte=data.get("time_slot_end").hour).exists()):
                raise serializers.ValidationError("Doctor is not available.")
        return data


class DoctorImageSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorImage
        fields = ('name', )


class DoctorQualificationSerializer(serializers.ModelSerializer):
    qualification = serializers.ReadOnlyField(source='qualification.name')
    specialization = serializers.ReadOnlyField(source='specialization.name')
    college = serializers.ReadOnlyField(source='college.name')

    class Meta:
        model = DoctorQualification
        fields = ('passing_year', 'qualification', 'specialization', 'college')


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
    day = serializers.SerializerMethodField()

    def get_day(self, attrs):
        day  = attrs.day
        return dict(DoctorHospital.DAY_CHOICES).get(day)


    def create(self, validated_data):
        return DoctorHospital.objects.create(**validated_data)

    def validate(self, data):
        data['doctor'] = self.context['doctor']
        data['hospital'] = self.context['hospital']

        return data

    class Meta:
        model = DoctorHospital
        fields = ('doctor', 'hospital', 'address', 'hospital_id', 'day', 'start', 'end', 'fees',)


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


class DoctorExperienceSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorExperience
        fields = ('hospital', 'start_year', 'end_year', )


class DoctorAwardSerializer(serializers.ModelSerializer):

    class Meta:
        model = DoctorAward
        fields = ('name', 'year')


class MedicalServiceSerializer(serializers.ModelSerializer):

    name = serializers.ReadOnlyField(source='service.name')
    description = serializers.ReadOnlyField(source='service.name')

    class Meta:
        model = DoctorMedicalService
        fields = ('id', 'name', 'description')


class DoctorProfileSerializer(serializers.ModelSerializer):
    images = DoctorImageSerializer(read_only=True, many=True)
    qualifications = DoctorQualificationSerializer(read_only=True, many=True)
    languages = DoctorLanguageSerializer(read_only=True, many=True)
    availability = DoctorHospitalSerializer(read_only=True, many=True)
    emails = DoctorEmailSerializer(read_only=True, many=True)
    mobiles = DoctorMobileSerializer(read_only=True, many=True)
    medical_services = MedicalServiceSerializer(read_only=True, many=True)
    experiences = DoctorExperienceSerializer(read_only=True, many=True)
    associations = DoctorAssociationSerializer(read_only=True, many=True)
    awards = DoctorAwardSerializer(read_only=True, many=True)

    # def to_representation(self, doctor):
    #     parent_rep = super().to_representation(doctor)
    #     try:
    #         parent_rep['images'] = parent_rep['images'][0]
    #     except KeyError as e:
    #         return parent_rep
    #
    #     return parent_rep

    class Meta:
        model = Doctor
        fields = (
        'id', 'name', 'gender', 'about', 'license', 'emails', 'practicing_since', 'images',
        'languages', 'qualifications', 'availability', 'mobiles', 'medical_services', 'experiences', 'associations',
        'awards', 'appointments')


class HospitalModelSerializer(serializers.ModelSerializer):
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    def get_lat(self, obj):
        loc = obj.location
        if loc:
            return loc.y
        return None

    def get_lng(self, obj):   
        loc = obj.location
        if loc:
            return loc.x
        return None

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'operational_since', 'lat', 'lng', 'registration_number','building', 'sublocality', 'locality', 'city')

class DoctorHospitalModelSerializer(serializers.ModelSerializer):
    hospital = HospitalModelSerializer()
    day = serializers.SerializerMethodField()
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()
    
    def get_day(self, obj):
        day = obj.day
        return dict(DoctorHospital.DAY_CHOICES).get(day)

    def get_start(self, obj):
        start = obj.start
        return dict(DoctorHospital.TIME_SLOT_CHOICES).get(start)

    def get_end(self, obj):
        end = obj.end
        return dict(DoctorHospital.TIME_SLOT_CHOICES).get(end)

    class Meta:
        model = DoctorHospital
        fields = '__all__'
        fields = ('id','day','start','end','fees','hospital')


class DoctorHospitalListSerializer(serializers.Serializer):
    min_fees = serializers.IntegerField()
    hospital = serializers.SerializerMethodField()

    def get_hospital(self, obj):
        queryset = Hospital.objects.get(pk=obj['hospital'])
        serializer = HospitalModelSerializer(queryset)
        return serializer.data
