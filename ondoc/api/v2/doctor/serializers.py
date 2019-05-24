from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db.models import Q
import logging
from django.conf import settings
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         DoctorNumber, Address, GenericAdmin, UserSecretKey,
                                         UserPermission, Address, GenericAdmin, GenericLabAdmin)
from ondoc.doctor import models as doc_models
from ondoc.procedure.models import Procedure
from ondoc.diagnostic.models import LabAppointment
from ondoc.api.v1.doctor import serializers as v1_serializers
from ondoc.api.v1.diagnostic import serializers as v1_diagnostic_serailizers

from dateutil.relativedelta import relativedelta
from django.utils import timezone
logger = logging.getLogger(__name__)
User = get_user_model()


class DoctorBlockCalenderSerializer(serializers.Serializer):
    INTERVAL_CHOICES = tuple([value for value in doc_models.DoctorLeave.INTERVAL_MAPPING.values()])
    interval = serializers.ChoiceField(required=False, choices=INTERVAL_CHOICES)
    start_date = serializers.DateField()
    start_time = serializers.TimeField(required=False)
    end_date = serializers.DateField()
    end_time = serializers.TimeField(required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Doctor.objects.all())
    hospital_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Hospital.objects.all())

    def validate(self, attrs):
        doctor = attrs.get("doctor_id")
        hospital = attrs.get("hospital_id")
        interval = attrs.get("interval")
        start_time = attrs.get("start_time")
        end_time = attrs.get("end_time")
        if doctor and hospital and (hospital not in doctor.hospitals.all()):
            raise serializers.ValidationError("incorrect hospital id or doctor id")
        if start_time and not end_time:
            raise serializers.ValidationError("end time is required with start time")
        if not start_time and end_time:
            raise serializers.ValidationError("start time is required with end time")
        if not interval and not (start_time and end_time):
            raise serializers.ValidationError("neither interval nor start time,end time found")
        return attrs


class DoctorProfileSerializer(serializers.ModelSerializer):
    images = v1_serializers.DoctorImageSerializer(read_only=True, many=True)
    qualifications = v1_serializers.DoctorQualificationSerializer(read_only=True, many=True)
    general_specialization = v1_serializers.DoctorPracticeSpecializationSerializer(read_only=True, many=True, source='doctorpracticespecializations')
    languages = v1_serializers.DoctorLanguageSerializer(read_only=True, many=True)
    availability = serializers.SerializerMethodField(read_only=True)
    emails = v1_serializers.DoctorEmailSerializer(read_only=True, many=True)
    mobiles = v1_serializers.DoctorMobileSerializer(read_only=True, many=True)
    medical_services = v1_serializers.MedicalServiceSerializer(read_only=True, many=True)
    experiences = v1_serializers.DoctorExperienceSerializer(read_only=True, many=True)
    associations = v1_serializers.DoctorAssociationSerializer(read_only=True, many=True)
    awards = v1_serializers.DoctorAwardSerializer(read_only=True, many=True)
    display_name = serializers.ReadOnlyField(source='get_display_name')
    thumbnail = serializers.SerializerMethodField()

    def get_availability(self, obj):
        data = doc_models.DoctorClinicTiming.objects.filter(doctor_clinic__doctor=obj).select_related("doctor_clinic__doctor",
                                                                                           "doctor_clinic__hospital")
        return v1_serializers.DoctorHospitalSerializer(data, context=self.context, many=True).data

    def get_thumbnail(self, obj):
        request = self.context.get('request')
        thumbnail = obj.get_thumbnail()
        if thumbnail:
            return request.build_absolute_uri(thumbnail) if thumbnail else None
        else:
            return None

    class Meta:
        model = doc_models.Doctor
        fields = (
            'id', 'name', 'display_name', 'gender', 'about', 'license', 'emails', 'practicing_since', 'images',
            'languages', 'qualifications', 'general_specialization', 'availability', 'mobiles', 'medical_services',
            'experiences', 'associations', 'awards', 'appointments', 'hospitals', 'thumbnail', 'signature', 'is_live')


class DoctorLeaveValidateQuerySerializer(serializers.Serializer):
    doctor_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Doctor.objects.all())
    hospital_id = serializers.PrimaryKeyRelatedField(required=False, queryset=doc_models.Hospital.objects.all())


class DoctorLeaveSerializer(serializers.ModelSerializer):
    interval = serializers.CharField(read_only=True)
    start_time = serializers.TimeField(write_only=True)
    end_time = serializers.TimeField(write_only=True)
    leave_start_time = serializers.FloatField(read_only=True, source='start_time_in_float')
    leave_end_time = serializers.FloatField(read_only=True, source='end_time_in_float')
    doctor_id = serializers.IntegerField(read_only=True)
    hospital_id = serializers.IntegerField(read_only=True)
    doctor_name = serializers.ReadOnlyField(source='doctor.get_display_name')
    hospital_name = serializers.ReadOnlyField(source='hospital.name')

    class Meta:
        model = doc_models.DoctorLeave
        exclude = ('created_at', 'updated_at', 'deleted_at')


class PracticeSpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.PracticeSpecialization
        fields = '__all__'


class QualificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Qualification
        fields = '__all__'


class LanguageSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Language
        fields = '__all__'


class MedicalServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.MedicalService
        fields = '__all__'


class ProcedureSerializer(serializers.ModelSerializer):
    class Meta:
        model = Procedure
        fields = '__all__'


class SpecializationSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Specialization
        fields = '__all__'


class ProviderSignupValidations:

    @staticmethod
    def provider_signup_lead_exists(attrs):
        return doc_models.ProviderSignupLead.objects.filter(phone_number=attrs['phone_number'],
                                                            user__isnull=False).exists()

    @staticmethod
    def admin_exists(attrs):
        return GenericAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists()

    @staticmethod
    def lab_admin_exists(attrs):
        return GenericLabAdmin.objects.filter(phone_number=attrs['phone_number'], is_disabled=False).exists()

    @staticmethod
    def user_exists(attrs):
        provider_signup_lead_exists = ProviderSignupValidations.provider_signup_lead_exists(attrs)
        admin_exists = ProviderSignupValidations.admin_exists(attrs)
        lab_admin_exists = ProviderSignupValidations.lab_admin_exists(attrs)
        return (admin_exists or lab_admin_exists or provider_signup_lead_exists)


class GenerateOtpSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000,max_value=9999999999)

    def validate(self, attrs):
        if ProviderSignupValidations.user_exists(attrs):
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        return attrs


class OtpVerificationSerializer(serializers.Serializer):
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    otp = serializers.IntegerField(min_value=100000,max_value=999999)

    def validate(self, attrs):
        if not OtpVerifications.objects.filter(phone_number=attrs['phone_number'], code=attrs['otp'], is_expired=False,
                   created_at__gte=timezone.now() - relativedelta(minutes=OtpVerifications.OTP_EXPIRY_TIME)).exists():
            raise serializers.ValidationError("Invalid OTP")
        if ProviderSignupValidations.user_exists(attrs):
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        return attrs


class ProviderSignupLeadDataSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    email = serializers.EmailField()
    type = serializers.ChoiceField(choices=doc_models.ProviderSignupLead.TYPE_CHOICES)

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        phone_number = attrs.get("phone_number")
        if ProviderSignupValidations.user_exists(attrs):
            raise serializers.ValidationError("Phone number already registered. Please try logging in.")
        if not (user and int(user.phone_number) == int(phone_number)):
            raise serializers.ValidationError("either user is missing or user and phone number mismatch")
        return attrs


class ConsentIsDocprimeSerializer(serializers.Serializer):
    is_docprime = serializers.BooleanField()

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        if not (user and doc_models.ProviderSignupLead.objects.filter(user=user).exists()):
            raise serializers.ValidationError("Provider not found")
        return attrs


class ConsentIsEncryptSerializer(serializers.Serializer):
    is_encrypted = serializers.BooleanField()
    hospital_id = serializers.IntegerField()
    encrypted_hospital_id = serializers.CharField()
    encryption_hint = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs and attrs['hospital_id']:
            queryset = doc_models.Hospital.objects.filter(id=attrs['hospital_id']).first()
            if not queryset:
                raise serializers.ValidationError('Hospital Not Found!')
            attrs['hosp'] = queryset
            return attrs


class BulkCreateDoctorSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    online_consultation_fees = serializers.IntegerField(required=False, min_value=0, allow_null=True)
    license = serializers.CharField(max_length=200, allow_blank=True, required=False)
    phone_number = serializers.IntegerField(required=False, min_value=5000000000, max_value=9999999999, allow_null=True)
    is_appointment = serializers.BooleanField(default=False)
    is_billing = serializers.BooleanField(default=False)
    is_superuser = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if (attrs.get('is_appointment') or attrs.get('is_billing') or attrs.get('is_superuser')) and not attrs.get('phone_number'):
            raise serializers.ValidationError('permission type or super user access given, but phone number not provided')
        return attrs


class CreateDoctorSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    doctors = serializers.ListField(child=BulkCreateDoctorSerializer(many=False))


class BulkCreateGenericAdminSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    phone_number = serializers.IntegerField(min_value=5000000000, max_value=9999999999)
    is_appointment = serializers.BooleanField(default=False)
    is_billing = serializers.BooleanField(default=False)
    is_superuser = serializers.BooleanField(default=False)

    def validate(self, attrs):
        if not (attrs.get('is_appointment') or attrs.get('is_billing') or attrs.get('is_superuser')):
            raise serializers.ValidationError('permission type or super user access not given')
        return attrs


class CreateGenericAdminSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    staffs = serializers.ListField(child=BulkCreateGenericAdminSerializer(many=False))


class CreateHospitalSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200)
    city = serializers.CharField(required=False, max_length=40)
    state = serializers.CharField(required=False, max_length=40)
    country = serializers.CharField(required=False, max_length=40)
    contact_number = serializers.IntegerField(required=False, min_value=5000000000, max_value=9999999999)
    doctors = serializers.ListField(required=False, child=BulkCreateDoctorSerializer(many=False))
    staffs = serializers.ListField(required=False, child=BulkCreateGenericAdminSerializer(many=False),
                                           allow_empty=True)
    is_listed_on_docprime = serializers.BooleanField(default=False)


class DoctorModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Doctor
        fields = ('id', 'name', 'online_consultation_fees', 'source_type', 'license')


class HospitalModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.Hospital
        fields = ('id', 'name', 'city', 'state', 'country', 'source_type')


class DoctorClinicModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.DoctorClinic
        fields = ('id', 'doctor', 'hospital', 'enabled')


class DoctorMobileModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = doc_models.DoctorMobile
        fields = ('id', 'doctor', 'number', 'is_primary')


class GenericAdminModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = GenericAdmin
        fields = ('id', 'phone_number', 'permission_type', 'name', 'doctor', 'hospital', 'super_user_permission', 'entity_type')


class UpdateHospitalConsent(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    is_listed_on_docprime = serializers.BooleanField()

    def validate(self, attrs):
        if attrs.get('is_listed_on_docprime') == False:
            raise serializers.ValidationError('the flag for hospital consent needs to be true')
        if attrs.get('hospital_id').is_listed_on_docprime is None:
            raise serializers.ValidationError('hospital added through agent, not by provider')
        # if attrs.get('hospital_id').is_listed_on_docprime is True:
        #     raise serializers.ValidationError('hospital already listed on docprime')
        return attrs


class GeneralInvoiceItemsSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=300)
    item = serializers.CharField(max_length=200)
    base_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    description = serializers.CharField(max_length=500, required=False, allow_null=True, allow_blank=True)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    tax_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True,
                                              min_value=0, max_value=100)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True,
                                                   min_value=0, max_value=100)
    hospital_ids = serializers.ListField(child=serializers.IntegerField())
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Doctor.objects.all(), required=False)

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None
        doctor = attrs.get("doctor_id")
        hospital_ids = set(attrs.get("hospital_ids"))
        hospitals = doc_models.Hospital.objects.filter(id__in=hospital_ids)
        general_invoice_item = doc_models.GeneralInvoiceItems.objects.filter(id=attrs.get('id')).first()
        received_tax_amount = attrs.get('tax_amount')
        received_discount_amount = attrs.get('discount_amount')

        if len(hospitals) != len(hospital_ids):
            raise serializers.ValidationError("one or more invalid hospital ids not found")
        manageable_hospitals = doc_models.Hospital.objects.filter(manageable_hospitals__user=request.user).distinct()
        if not (set(hospitals) <= set(manageable_hospitals)):
            raise serializers.ValidationError("hospital_ids include hospitals not manageable by current user")
        attrs['hospitals'] = hospitals

        if not doctor:
            admin = GenericAdmin.objects.filter(Q(user=user, hospital__in=hospitals),
                                                Q(Q(super_user_permission=True) |
                                                  Q(permission_type=GenericAdmin.APPOINTMENT)))
        else:
            if not doc_models.DoctorClinic.objects.filter(doctor=doctor, hospital__in=hospitals).exists():
                raise serializers.ValidationError("doctor_id not available in any of the hospital_ids")
            admin = GenericAdmin.objects.filter(Q(user=user, hospital__in=hospitals),
                                                Q(Q(super_user_permission=True) |
                                                  Q(Q(permission_type=GenericAdmin.APPOINTMENT),
                                                    Q(doctor__isnull=True) | Q(doctor=doctor))))
        if user and not admin.exists():
            raise serializers.ValidationError('user not admin for given hospitals or the appointment doctor_id, if present')
        attrs['user'] = user if user else None

        if general_invoice_item:
            attrs['general_invoice_item'] = general_invoice_item

        if attrs.get('tax_percentage'):
            calculated_tax_amount = attrs.get('base_price') * attrs.get('tax_percentage', 0) / 100
            calculated_tax_amount = round(calculated_tax_amount, doc_models.GeneralInvoiceItems.DECIMAL_PLACES)
            if not received_tax_amount:
                raise serializers.ValidationError("tax_amount is also required with tax_percentage")
            elif received_tax_amount != calculated_tax_amount:
                raise serializers.ValidationError("incorrect tax amount for given tax percentage")

        if attrs.get('discount_percentage'):
            calculated_discount_amount = (attrs.get('base_price') + attrs.get('tax_amount', 0)) * attrs.get('discount_percentage', 0) / 100
            calculated_discount_amount = round(calculated_discount_amount, doc_models.GeneralInvoiceItems.DECIMAL_PLACES)
            if not received_discount_amount:
                raise serializers.ValidationError("discount_amount is also required with discount_percentage")
            elif received_discount_amount != calculated_discount_amount:
                raise serializers.ValidationError("incorrect discount amount for given discount percentage")

        if (attrs.get('base_price') + attrs.get('tax_amount', 0) - attrs.get('discount_amount', 0)) < 0:
            raise serializers.ValidationError("calculated price is negative, too much discount")

        return attrs


class GeneralInvoiceItemsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = doc_models.GeneralInvoiceItems
        fields = ('id', 'item', 'base_price', 'description', 'tax_amount', 'tax_percentage', 'discount_amount',
                  'discount_percentage', 'hospitals')


class SelectedInvoiceItemsSerializer(serializers.Serializer):
    invoice_item = serializers.PrimaryKeyRelatedField(queryset=doc_models.GeneralInvoiceItems.objects.all())
    quantity = serializers.IntegerField(min_value=1)
    calculated_price = serializers.DecimalField(max_digits=10, decimal_places=2)

    def validate(self, attrs):
        invoice_item = attrs['invoice_item']
        quantity = attrs['quantity']
        calculated_price = attrs['calculated_price']
        rounded_calculated_price = round(calculated_price, doc_models.GeneralInvoiceItems.DECIMAL_PLACES)

        computed_price = invoice_item.get_computed_price()
        rounded_computed_price = round(quantity * computed_price, doc_models.GeneralInvoiceItems.DECIMAL_PLACES)

        if rounded_calculated_price != rounded_computed_price:
            raise serializers.ValidationError(
                'calculated price for invoice_item with ID - {} is incorrect or not in coordination with item computed price'.format(
                    invoice_item.id))

        return attrs



class SelectedInvoiceItemsJSONSerializer(serializers.Serializer):
    invoice_item = GeneralInvoiceItemsModelSerializer(many=False)
    quantity = serializers.IntegerField(min_value=1)
    calculated_price = serializers.DecimalField(max_digits=10, decimal_places=2)


class SelectedInvoiceItemsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = doc_models.SelectedInvoiceItems
        fields = '__all__'


class PartnersAppInvoiceSerialier(serializers.Serializer):
    appointment_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.OfflineOPDAppointments.objects.all())
    consultation_fees = serializers.IntegerField(min_value=0)
    selected_invoice_items = serializers.ListField(child=SelectedInvoiceItemsSerializer(many=False), required=False,
                                                   allow_empty=True)
    payment_status = serializers.ChoiceField(choices=doc_models.PartnersAppInvoice.PAYMENT_STATUS)
    payment_type = serializers.ChoiceField(choices=doc_models.PartnersAppInvoice.PAYMENT_CHOICES, required=False, allow_null=True)
    due_date = serializers.DateField(required=False, allow_null=True)
    sub_total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    invoice_title = serializers.CharField(max_length=300, required=False, allow_blank=True)
    tax_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    tax_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True,
                                              min_value=0, max_value=100)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True,
                                                   min_value=0, max_value=100)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    generate_invoice = serializers.BooleanField(default=False)

    def validate(self, attrs):
        selected_invoice_items = attrs.get('selected_invoice_items')
        received_subtotal_amount = attrs['sub_total_amount']
        received_tax_amount = attrs.get('tax_amount')
        received_discount_amount = attrs.get('discount_amount')
        received_total_amount = attrs['total_amount']

        if attrs.get('payment_status') == doc_models.PartnersAppInvoice.PAID and not attrs.get('payment_type'):
            raise serializers.ValidationError('payment type is required for payment status - paid')
        if attrs.get('payment_status') == doc_models.PartnersAppInvoice.PENDING and not attrs.get('due_date'):
            raise serializers.ValidationError('due date is required for payment status - pending')
        if attrs.get('generate_invoice') and not attrs.get('invoice_title'):
            raise serializers.ValidationError('invoice title is missing for invoice generation')
        if attrs.get('appointment_id'):
            attrs['appointment'] = attrs.pop('appointment_id')

        computed_subtotal_amount = attrs['consultation_fees']
        if selected_invoice_items:
            for item in selected_invoice_items:
                computed_subtotal_amount += item['calculated_price']
        if received_subtotal_amount != computed_subtotal_amount:
            raise serializers.ValidationError("sub_total_amount is incorrect or not in accordance with the item's calculated_price sum")

        if attrs.get('tax_percentage'):
            computed_tax_amount= received_subtotal_amount * attrs.get('tax_percentage', 0) / 100
            computed_tax_amount = round(computed_tax_amount, doc_models.PartnersAppInvoice.DECIMAL_PLACES)
            if not received_tax_amount:
                raise serializers.ValidationError("tax_amount is also required with tax_percentage")
            elif received_tax_amount != computed_tax_amount:
                raise serializers.ValidationError("incorrect tax amount for given tax percentage")

        if attrs.get('discount_percentage'):
            computed_discount_amount = (received_subtotal_amount + attrs.get('tax_amount', 0)) * attrs.get('discount_percentage', 0) / 100
            computed_discount_amount = round(computed_discount_amount, doc_models.GeneralInvoiceItems.DECIMAL_PLACES)
            if not received_discount_amount:
                raise serializers.ValidationError("discount_amount is also required with discount_percentage")
            elif received_discount_amount != computed_discount_amount:
                raise serializers.ValidationError("incorrect discount amount for given discount percentage")

        computed_total_amount = computed_subtotal_amount + attrs.get('tax_amount') - attrs.get('discount_amount')
        if received_total_amount != computed_total_amount:
            raise serializers.ValidationError("incorrect total amount received for given data")

        if received_total_amount < 0:
            raise serializers.ValidationError("total amount is negative, too much discount")

        return attrs


class PartnersAppInvoiceModelSerialier(serializers.ModelSerializer):

    class Meta:
        model = doc_models.PartnersAppInvoice
        fields = ('id', 'created_at', 'updated_at', 'invoice_serial_id', 'consultation_fees', 'selected_invoice_items',
                  'payment_status', 'payment_type', 'due_date', 'invoice_title', 'sub_total_amount', 'tax_amount',
                  'tax_percentage', 'discount_amount', 'discount_percentage', 'total_amount', 'is_invoice_generated',
                  'is_valid', 'is_edited', 'edited_by', 'appointment_id', 'encoded_url')


class ListInvoiceItemsSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all(), required=False)
    doctor_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Doctor.objects.all(), required=False)

    def validate(self, attrs):
        request = self.context.get("request")
        user = request.user if request else None
        hospital = attrs.get('hospital_id')
        doctor = attrs.get('doctor_id')
        # hospital = attrs['appointment_id'].hospital
        # doctor = attrs['appointment_id'].doctor
        if doctor and not hospital:
            raise serializers.ValidationError("hospital_id is required if doctor_id is present")
        if hospital and doctor:
            if not doc_models.DoctorClinic.objects.filter(doctor=doctor, hospital=hospital).exists():
                raise serializers.ValidationError("doctor_id not available in given hospital_id")
            admin = GenericAdmin.objects.filter(Q(user=user, hospital=hospital),
                                                Q(Q(super_user_permission=True) |
                                                  Q(Q(permission_type=GenericAdmin.APPOINTMENT),
                                                    Q(doctor__isnull=True) | Q(doctor=doctor))))
        elif hospital:
            admin = GenericAdmin.objects.filter(Q(user=user, hospital=hospital),
                                                Q(Q(super_user_permission=True) |
                                                  Q(permission_type=GenericAdmin.APPOINTMENT)))
        if hospital and user and not admin.exists():
            raise serializers.ValidationError('user not admin for given data')
        # if admin.exists:
        #     attrs['admin'] = admin
        return attrs


class UpdatePartnersAppInvoiceSerializer(serializers.Serializer):
    invoice_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.PartnersAppInvoice.objects.all())
    data = PartnersAppInvoiceSerialier(many=False)

    def validate(self, attrs):
        super().validate(attrs)
        if not attrs.get('invoice_id').is_valid:
            raise serializers.ValidationError("valid invoice id is required")
        return attrs
