from rest_framework import serializers
from rest_framework.fields import CharField
from django.db.models import Q
from ondoc.doctor.models import (OpdAppointment, Doctor, Hospital, DoctorHospital, DoctorClinicTiming, DoctorAssociation,
                                 DoctorAward, DoctorDocument, DoctorEmail, DoctorExperience, DoctorImage,
                                 DoctorLanguage, DoctorMedicalService, DoctorMobile, DoctorQualification, DoctorLeave,
                                 Prescription, PrescriptionFile, Specialization, DoctorSearchResult, HealthTip,
                                 CommonMedicalCondition,CommonSpecialization, DoctorSpecialization,
                                 GeneralSpecialization)
from ondoc.authentication.models import UserProfile
from django.contrib.staticfiles.templatetags.staticfiles import static
from ondoc.api.v1.auth.serializers import UserProfileSerializer
from ondoc.api.v1.utils import is_valid_testing_data
from django.utils import timezone
from django.contrib.auth import get_user_model
import math
import datetime
import pytz
User = get_user_model()


class CommaSepratedToListField(CharField):
    def __init__(self, **kwargs):
        self.typecast_to = kwargs.pop('typecast_to', int)
        super(CommaSepratedToListField, self).__init__(**kwargs)

    def to_internal_value(self, data):
        return list(map(self.typecast_to, data.strip(",").split(",")))

    def to_representation(self, value):
        return list(map(self.typecast_to, value.strip(",").split(",")))


class OTPSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField()


class AppointmentFilterSerializer(serializers.Serializer):
    CHOICES = ['all', 'previous', 'upcoming', 'pending']

    range = serializers.ChoiceField(choices=CHOICES, required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True), required=False)
    date = serializers.DateField(required=False)


class AppointmentFilterUserSerializer(serializers.Serializer):
    CHOICES = ['all', 'previous', 'upcoming', 'pending']

    range = serializers.ChoiceField(choices=CHOICES, required=False)
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.all(), required=False)
    profile_id = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all(), required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.all(), required=False)
    date = serializers.DateField(required=False)


class OpdAppointmentSerializer(serializers.ModelSerializer):
    DOCTOR_TYPE = 'doctor'
    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')
    patient_name = serializers.ReadOnlyField(source='profile.name')
    # patient_dob = serializers.ReadOnlyField(source='profile.dob')
    patient_gender = serializers.ReadOnlyField(source='profile.gender'),
    patient_image = serializers.SerializerMethodField()
    patient_thumbnail = serializers.SerializerMethodField()
    doctor_thumbnail = serializers.SerializerMethodField()
    type = serializers.ReadOnlyField(default='doctor')
    allowed_action = serializers.SerializerMethodField()

    def get_allowed_action(self, obj):
        request = self.context.get('request')
        return obj.allowed_action(request.user.user_type, request)

    class Meta:
        model = OpdAppointment
        fields = ('id', 'doctor_name', 'hospital_name', 'patient_name', 'patient_image', 'type',
                  'allowed_action', 'effective_price', 'deal_price', 'status', 'time_slot_start',
                  'time_slot_end', 'doctor_thumbnail', 'patient_thumbnail')

    def get_patient_image(self, obj):
        if obj.profile.profile_image:
            return obj.profile.profile_image.url
        else:
            return ""

    def get_patient_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.profile.profile_image:
            photo_url = obj.profile.profile_image.url
            return request.build_absolute_uri(photo_url)
        else:
            return None

    def get_doctor_thumbnail(self, obj):
        request = self.context.get('request')
        if obj.doctor.images.all():
            photo_url = (
                obj.doctor.images.all()[0].cropped_image.url if obj.doctor.images.all()[0].cropped_image else None)
            return request.build_absolute_uri(photo_url) if photo_url else None
        else:
            return None
            # url = static('doctor_images/no_image.png')
            # return request.build_absolute_uri(url)





class OpdAppModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = OpdAppointment
        fields = '__all__'


class OpdAppTransactionModelSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    profile_detail = serializers.JSONField()
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    booked_by = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    fees = serializers.DecimalField(max_digits=10, decimal_places=2)
    mrp = serializers.DecimalField(max_digits=10, decimal_places=2)
    deal_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    time_slot_start = serializers.DateTimeField()
    payment_type = serializers.IntegerField()


class OpdAppointmentPermissionSerializer(serializers.Serializer):
    appointment = OpdAppointmentSerializer()
    permission = serializers.IntegerField()


class CreateAppointmentSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))
    profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    start_date = serializers.CharField()
    start_time = serializers.FloatField()
    end_date = serializers.CharField(required=False)
    end_time = serializers.FloatField(required=False)
    time_slot_start = serializers.DateTimeField(required=False)    
    payment_type = serializers.ChoiceField(choices=OpdAppointment.PAY_CHOICES)

    # time_slot_end = serializers.DateTimeField()

    def validate(self, data):
        ACTIVE_APPOINTMENT_STATUS = [OpdAppointment.BOOKED, OpdAppointment.ACCEPTED,
                                     OpdAppointment.RESCHEDULED_PATIENT, OpdAppointment.RESCHEDULED_DOCTOR]
        MAX_APPOINTMENTS_ALLOWED = 3
        MAX_FUTURE_DAY = 40
        request = self.context.get("request")
        time_slot_start = (self.form_time_slot(data.get('start_date'), data.get('start_time'))
                           if not data.get("time_slot_start") else data.get("time_slot_start"))

        time_slot_end = None

        if not is_valid_testing_data(request.user, data["doctor"]):
            raise serializers.ValidationError("Both User and Doctor should be for testing")

        if data.get('end_date') and data.get('end_time'):
            time_slot_end = self.form_time_slot(data.get('end_date'), data.get('end_time'))

        if not request.user.user_type == User.CONSUMER:
            raise serializers.ValidationError("Not allowed to create appointment")

        if not UserProfile.objects.filter(user=request.user, pk=int(data.get("profile").id)).exists():
            raise serializers.ValidationError("Invalid profile id")

        if time_slot_start < timezone.now():
            raise serializers.ValidationError("Cannot book in past")

        delta = time_slot_start - timezone.now()
        if delta.days > MAX_FUTURE_DAY:
            raise serializers.ValidationError("Cannot book appointment more than "+str(MAX_FUTURE_DAY)+" days ahead")

        time_slot_hour = round(float(time_slot_start.hour) + (float(time_slot_start.minute) * 1 / 60), 2)

        doctor_leave = DoctorLeave.objects.filter(deleted_at__isnull=True, doctor=data.get('doctor'), start_date__lte=time_slot_start.date(), end_date__gte=time_slot_start.date(), start_time__lte=time_slot_start.time(), end_time__gte=time_slot_start.time()).exists()

        if doctor_leave:
            raise serializers.ValidationError("Doctor is on leave")


        if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=data.get('doctor'),
                                                 doctor_clinic__hospital=data.get('hospital'),
                                                 day=time_slot_start.weekday(), start__lte=time_slot_hour,
                                                 end__gte=time_slot_hour).exists():
            raise serializers.ValidationError("Invalid Time slot")

        if OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, doctor=data.get('doctor'), profile=data.get('profile')).exists():
            raise serializers.ValidationError('A previous appointment with this doctor already exists. Cancel it before booking new Appointment.')

        if OpdAppointment.objects.filter(status__in=ACTIVE_APPOINTMENT_STATUS, profile = data.get('profile')).count()>=MAX_APPOINTMENTS_ALLOWED:
            raise serializers.ValidationError('Max'+str(MAX_APPOINTMENTS_ALLOWED)+' active appointments are allowed')

        return data

    @staticmethod
    def form_time_slot(date_str, time):
        date, temp = date_str.split("T")
        date_str = str(date)
        min, hour = math.modf(time)
        min *= 60
        if min < 10:
            min = "0" + str(int(min))
        else:
            min = str(int(min))
        time_str = str(int(hour))+":"+str(min)
        date_time_field = str(date_str) + "T" + time_str
        dt_field = datetime.datetime.strptime(date_time_field, "%Y-%m-%dT%H:%M")
        defined_timezone = str(timezone.get_default_timezone())
        dt_field = pytz.timezone(defined_timezone).localize(dt_field)
        # dt_field = pytz.utc.localize(dt_field)
        return dt_field


class SetAppointmentSerializer(serializers.Serializer):
    doctor = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))
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


class OTPFieldSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    otp = serializers.IntegerField(max_value=9999)


class OTPConfirmationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    otp = serializers.IntegerField(max_value=9999)

    def validate(self, attrs):
        if not OpdAppointment.objects.filter(id=attrs['id']).filter(otp=attrs['otp']).exists():
            raise serializers.ValidationError("Invalid OTP")
        return attrs


class UpdateStatusSerializer(serializers.Serializer):
    status = serializers.IntegerField()
    time_slot_start = serializers.DateTimeField(required=False)
    time_slot_end = serializers.DateTimeField(required=False)
    start_date = serializers.CharField(required=False)
    start_time = serializers.FloatField(required=False)


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
    doctor = serializers.ReadOnlyField(source='doctor_clinic.doctor.name')
    hospital_name = serializers.ReadOnlyField(source='doctor_clinic.hospital.name')
    address = serializers.ReadOnlyField(source='doctor_clinic.hospital.get_address')
    hospital_id = serializers.ReadOnlyField(source='doctor_clinic.hospital.pk')
    hospital_thumbnail = serializers.SerializerMethodField()
    day = serializers.SerializerMethodField()
    discounted_fees = serializers.IntegerField(read_only=True, allow_null=True, source='deal_price')
    lat = serializers.SerializerMethodField(read_only=True)
    long = serializers.SerializerMethodField(read_only=True)

    def get_lat(self, obj):
        if obj.doctor_clinic.hospital.location:
            return obj.doctor_clinic.hospital.location.y
        return None

    def get_long(self, obj):
        if obj.doctor_clinic.hospital.location:
            return obj.doctor_clinic.hospital.location.x
        return None

    def get_hospital_thumbnail(self, instance):
        request = self.context.get("request")
        return request.build_absolute_uri(
            instance.doctor_clinic.hospital.get_thumbnail()) if instance.doctor_clinic.hospital.get_thumbnail() else None

    def get_day(self, attrs):
        day  = attrs.day
        return dict(DoctorClinicTiming.DAY_CHOICES).get(day)

    def validate(self, data):
        data['doctor'] = self.context['doctor']
        data['hospital'] = self.context['hospital']

        return data

    class Meta:
        model = DoctorClinicTiming
        fields = ('doctor', 'hospital_name', 'address', 'hospital_id', 'start', 'end', 'day', 'deal_price',
                  'discounted_fees', 'hospital_thumbnail', 'mrp', 'lat', 'long', 'id', )
        # fields = ('doctor', 'hospital_name', 'address', 'hospital_id', 'start', 'end', 'day', 'deal_price', 'fees',
        #           'discounted_fees', 'hospital_thumbnail', 'mrp',)


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


class GeneralSpecializationSerializer(serializers.ModelSerializer):

    class Meta:
        model = GeneralSpecialization
        fields = ('name', )


class DoctorSpecializationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(read_only=True, source='specialization.name')

    class Meta:
        model = DoctorSpecialization
        fields = ('name', )


class DoctorProfileSerializer(serializers.ModelSerializer):
    images = DoctorImageSerializer(read_only=True, many=True)
    qualifications = DoctorQualificationSerializer(read_only=True, many=True)
    general_specialization = DoctorSpecializationSerializer(read_only=True, many=True, source='doctorspecializations')
    languages = DoctorLanguageSerializer(read_only=True, many=True)
    availability = serializers.SerializerMethodField(read_only=True)
    emails = DoctorEmailSerializer(read_only=True, many=True)
    mobiles = DoctorMobileSerializer(read_only=True, many=True)
    medical_services = MedicalServiceSerializer(read_only=True, many=True)
    experiences = DoctorExperienceSerializer(read_only=True, many=True)
    associations = DoctorAssociationSerializer(read_only=True, many=True)
    awards = DoctorAwardSerializer(read_only=True, many=True)
    thumbnail = serializers.SerializerMethodField()

    # def get_general_specialization(self, obj):
    #     return DoctorSpecializationSerializer(obj.doctorspecializations.all(), many=True).data

    def get_availability(self, obj):
        data = DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj).select_related("doctor_clinic__doctor",
                                                                                           "doctor_clinic__hospital")
        return DoctorHospitalSerializer(data, context=self.context, many=True).data

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        default_image_url = static('doctor_images/no_image.png')
        if obj.images.all().exists():
            image = obj.images.all().first()
            if not image.cropped_image:
                return None
                # return request.build_absolute_uri(default_image_url)
            return request.build_absolute_uri(image.cropped_image.url)
        else:
            return None
            # return request.build_absolute_uri(default_image_url)


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
            'languages', 'qualifications', 'general_specialization', 'availability', 'mobiles', 'medical_services',
            'experiences', 'associations', 'awards', 'appointments', 'hospitals', 'thumbnail',)


class HospitalModelSerializer(serializers.ModelSerializer):
    lat = serializers.SerializerMethodField()
    lng = serializers.SerializerMethodField()
    hospital_thumbnail = serializers.SerializerMethodField()

    address = serializers.SerializerMethodField()

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

    def get_hospital_thumbnail(self, obj):
        request = self.context.get("request")
        if not request:
            return obj.get_thumbnail()
        return request.build_absolute_uri(obj.get_thumbnail()) if obj.get_thumbnail() else None

    class Meta:
        model = Hospital
        fields = ('id', 'name', 'operational_since', 'lat', 'lng', 'address', 'registration_number',
                  'building', 'sublocality', 'locality', 'city', 'hospital_thumbnail', )


class DoctorHospitalScheduleSerializer(serializers.ModelSerializer):
    # hospital = HospitalModelSerializer()
    day = serializers.SerializerMethodField()
    start = serializers.SerializerMethodField()
    end = serializers.SerializerMethodField()

    def get_day(self, obj):
        day = obj.day
        return dict(DoctorClinicTiming.DAY_CHOICES).get(day)

    def get_start(self, obj):
        start = obj.start
        return dict(DoctorClinicTiming.TIME_CHOICES).get(start)

    def get_end(self, obj):
        end = obj.end
        return dict(DoctorClinicTiming.TIME_CHOICES).get(end)

    class Meta:
        model = DoctorClinicTiming
        # fields = ('id', 'day', 'start', 'end', 'fees', 'hospital')
        fields = ('day', 'start', 'end', 'fees')


class DoctorHospitalListSerializer(serializers.Serializer):
    min_fees = serializers.IntegerField()
    hospital = HospitalModelSerializer()
    # hospital = serializers.SerializerMethodField()

    def get_hospital(self, obj):
        queryset = Hospital.objects.get(pk=obj['hospital'])
        serializer = HospitalModelSerializer(queryset, context=self.context)
        return serializer.data


class DoctorBlockCalenderSerialzer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    # def validate(self, attrs):
    #     request = self.context.get("request")
    #     if DoctorLeave.objects.filter(doctor=request.user.doctor.id, deleted_at__isnull=True).exists():
    #         raise serializers.ValidationError("Doctor can apply on one leave at a time")
    #     return attrs


class DoctorLeaveSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_time = serializers.TimeField(write_only=True)
    end_time = serializers.TimeField(write_only=True)
    leave_start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    leave_end_time = serializers.FloatField(read_only=True, source='end_time_in_float')

    class Meta:
        model = DoctorLeave
        exclude = ('created_at', 'updated_at', 'deleted_at')


class PrescriptionFileSerializer(serializers.ModelSerializer):

    class Meta:
        model = PrescriptionFile
        fields = ('prescription', 'name')


class PrescriptionFileDeleteSerializer(serializers.Serializer):
    appointment = serializers.PrimaryKeyRelatedField(
        queryset=OpdAppointment.objects.all())
    id = serializers.IntegerField()

    def validate_appointment(self, value):
        request = self.context.get('request')
        if not OpdAppointment.objects.filter(doctor=request.user.doctor).exists():
            raise serializers.ValidationError("Appointment is not correct.")
        return value


class PrescriptionSerializer(serializers.Serializer):
    appointment = serializers.PrimaryKeyRelatedField(queryset=OpdAppointment.objects.all())
    prescription_details = serializers.CharField(allow_blank=True, allow_null=True, required=False, max_length=300)
    name = serializers.FileField()

    def validate_appointment(self, value):
        request = self.context.get('request')
        if not OpdAppointment.objects.filter(doctor=request.user.doctor).exists():
            raise serializers.ValidationError("Appointment is not correct.")
        return value


class DoctorListSerializer(serializers.Serializer):
    SORT_CHOICES = ('fees', 'experience', 'distance', )
    SITTING_CHOICES = [type_choice[1] for type_choice in Hospital.HOSPITAL_TYPE_CHOICES]
    specialization_ids = CommaSepratedToListField(required=False, max_length=100, typecast_to=str)
    longitude = serializers.FloatField(default=77.071848)
    latitude = serializers.FloatField(default=28.450367)
    sits_at = CommaSepratedToListField(required=False, max_length=100, typecast_to=str)
    sort_on = serializers.ChoiceField(choices=SORT_CHOICES, required=False)
    min_fees = serializers.IntegerField(required=False)
    max_fees = serializers.IntegerField(required=False)
    is_female = serializers.BooleanField(required=False)
    is_available = serializers.BooleanField(required=False)
    search_id = serializers.IntegerField(required=False, allow_null=True)
    doctor_name = serializers.CharField(required=False)
    hospital_name = serializers.CharField(required=False)

    def validate_specialization_id(self, value):
        if not Specialization.objects.filter(id__in=value.strip()).count() == len(value.strip()):
            raise serializers.ValidationError("Invalid specialization Id.")
        return value

    def validate_sits_at(self, value):
        if not set(value).issubset(set(self.SITTING_CHOICES)):
            raise serializers.ValidationError("Not a Valid Choice")
        return value


class DoctorProfileUserViewSerializer(DoctorProfileSerializer):
    emails = None
    experience_years = serializers.IntegerField(allow_null=True)
    # hospitals = DoctorHospitalSerializer(read_only=True, many=True, source='get_hospitals')
    hospitals = serializers.SerializerMethodField(read_only=True)
    hospital_count = serializers.IntegerField(read_only=True, allow_null=True)
    availability = None

    def get_hospitals(self, obj):
        data = DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj, doctor_clinic__doctor__is_live=True,
                                                 doctor_clinic__hospital__is_live=True).select_related(
            "doctor_clinic__doctor", "doctor_clinic__hospital")
        return DoctorHospitalSerializer(data, context=self.context, many=True).data

    class Meta:
        model = Doctor
        # exclude = ('created_at', 'updated_at', 'onboarding_status', 'is_email_verified',
        #            'is_insurance_enabled', 'is_retail_enabled', 'user', 'created_by', )
        fields = ('about', 'additional_details', 'associations', 'awards', 'experience_years', 'experiences', 'gender',
                  'hospital_count', 'hospitals', 'id', 'images', 'languages', 'name', 'practicing_since', 'qualifications',
                  'general_specialization', 'thumbnail', 'license')



class DoctorAvailabilityTimingSerializer(serializers.Serializer):
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=Doctor.objects.filter(is_live=True))
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=Hospital.objects.filter(is_live=True))


class DoctorTimeSlotSerializer(serializers.Serializer):
    images = DoctorImageSerializer(read_only=True, many=True)
    qualifications = DoctorQualificationSerializer(read_only=True, many=True)
    general_specialization = DoctorSpecializationSerializer(read_only=True, many=True, source='doctorspecializations')

    class Meta:
        model = Doctor
        fields = ('id', 'images', 'qualifications', 'general_specialization', )


class AppointmentRetrieveDoctorSerializer(DoctorProfileSerializer):
    class Meta:
        model = Doctor
        fields = ('id', 'name', 'gender', 'images','about', 'practicing_since',
                  'qualifications', 'general_specialization', 'mobiles',)


class OpdAppointmentBillingSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'otp',
                  'allowed_action', 'effective_price', 'fees', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail', 'payment_type')


class AppointmentRetrieveSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'otp',
                  'allowed_action', 'effective_price', 'deal_price', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail',)



class DoctorAppointmentRetrieveSerializer(OpdAppointmentSerializer):
    profile = UserProfileSerializer()
    hospital = HospitalModelSerializer()
    doctor = AppointmentRetrieveDoctorSerializer()

    class Meta:
        model = OpdAppointment
        fields = ('id', 'patient_image', 'patient_name', 'type', 'profile', 'allowed_action', 'effective_price',
                   'deal_price', 'status', 'time_slot_start', 'time_slot_end',
                  'doctor', 'hospital', 'allowed_action', 'doctor_thumbnail', 'patient_thumbnail',)


class HealthTipSerializer(serializers.ModelSerializer):

    class Meta:
        model = HealthTip
        fields = ('id', 'text',)


class MedicalConditionSerializer(serializers.ModelSerializer):

    id = serializers.ReadOnlyField(source='condition.id')
    name = serializers.ReadOnlyField(source='condition.name')
    specialization = serializers.SerializerMethodField()

    def get_specialization(self, obj):
        spc_id = []
        if obj:
            for spc in obj.condition.specialization.all():
                spc_id.append(spc.id)
        return spc_id

    class Meta:
        model = CommonMedicalCondition
        fields = ('id', 'name', 'specialization')


class CommonSpecializationsSerializer(serializers.ModelSerializer):

    id = serializers.ReadOnlyField(source='specialization.id')
    name = serializers.ReadOnlyField(source='specialization.name')

    class Meta:
        model = CommonSpecialization
        fields = ('id', 'name')


class ConfigGetSerializer(serializers.Serializer):

    os = serializers.CharField(max_length=10)
    ver = serializers.CharField(max_length=10)




