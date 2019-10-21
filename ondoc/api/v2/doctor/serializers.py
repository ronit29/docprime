from rest_framework import serializers
from rest_framework.fields import UUIDField
from django.contrib.auth import get_user_model
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
import logging
from django.conf import settings
from ondoc.authentication.models import (OtpVerifications, User, UserProfile, Notification, NotificationEndpoint,
                                         DoctorNumber, Address, GenericAdmin, UserSecretKey,
                                         UserPermission, Address, GenericAdmin, GenericLabAdmin)
from ondoc.doctor import models as doc_models
from ondoc.diagnostic import models as diag_models
from ondoc.procedure.models import Procedure
from ondoc.diagnostic.models import LabAppointment
from ondoc.notification.models import NotificationAction
from ondoc.api.v1.doctor import serializers as v1_serializers
from ondoc.api.v1.diagnostic import serializers as v1_diagnostic_serailizers

from dateutil.relativedelta import relativedelta
from django.utils import timezone
logger = logging.getLogger(__name__)
from uuid import UUID
from ondoc.provider import models as provider_models
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
    via_sms = serializers.BooleanField(default=True, required=False)
    via_whatsapp = serializers.BooleanField(default=False, required=False)
    request_source = serializers.CharField(required=False, max_length=200)

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


class EncryptedHospitalsSerializer(serializers.Serializer):
    hospital_id = serializers.PrimaryKeyRelatedField(queryset=doc_models.Hospital.objects.all())
    encrypted_hospital_id = serializers.CharField(required=False, allow_blank=True)


class ConsentIsEncryptSerializer(serializers.Serializer):
    is_encrypted = serializers.BooleanField(required=False)
    hospitals = serializers.ListField(child=EncryptedHospitalsSerializer(many=False))
    hint = serializers.CharField(required=False, allow_blank=True)
    encryption_key = serializers.CharField(required=False, allow_blank=True)
    # decrypt = serializers.BooleanField(required=False)
    email = serializers.EmailField(required=False, allow_blank=True, max_length=100)
    phone_numbers = serializers.ListField(child=serializers.IntegerField(validators=[MaxValueValidator(9999999999), MinValueValidator(1000000000)]), allow_empty=True, required=False)
    google_drive = serializers.EmailField(required=False, allow_blank=True, max_length=100)
    is_consent_received = serializers.BooleanField()

    def validate(self, attrs):
        if attrs:
            if 'is_encrypted' in attrs and not attrs.get('is_encrypted'):
                if not attrs.get('encryption_key'):
                    raise serializers.ValidationError('Encryption Key Not Found!')
                else:
                    for hospital in attrs['hospitals']:
                        if not (hasattr(hospital['hospital_id'], 'encrypt_details') and hospital['hospital_id'].encrypt_details.is_valid):
                            raise serializers.ValidationError('decrypt called for unencrypted hospital')
            else:
                existing_valid_details_indexes = list()
                for index, hospital in enumerate(attrs['hospitals']):
                    if hasattr(hospital['hospital_id'], 'encrypt_details') and hospital['hospital_id'].encrypt_details.is_valid:
                        existing_valid_details_indexes.append(index)
                for index in sorted(existing_valid_details_indexes, reverse=True):
                    del attrs['hospitals'][index]
                if not attrs['hospitals']:
                    raise serializers.ValidationError('encrypted data already present for given hospitals')
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
                                              min_value=0)
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
                                              min_value=0)
    discount_amount = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    discount_percentage = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True,
                                                   min_value=0, max_value=100)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    generate_invoice = serializers.BooleanField(default=False)
    is_encrypted = serializers.BooleanField(required=False, default=False)
    invoice_serial_id = serializers.CharField(required=False, max_length=100)

    def validate(self, attrs):
        selected_invoice_items = attrs.get('selected_invoice_items')
        received_subtotal_amount = attrs['sub_total_amount']
        received_tax_amount = attrs.get('tax_amount')
        received_discount_amount = attrs.get('discount_amount')
        received_total_amount = attrs['total_amount']

        if attrs.get('payment_status') == doc_models.PartnersAppInvoice.PAID:
            attrs['due_date'] = None
            if not attrs.get('payment_type'):
                raise serializers.ValidationError('payment type is required for payment status - paid')
        if attrs.get('payment_status') == doc_models.PartnersAppInvoice.PENDING and not attrs.get('due_date'):
            raise serializers.ValidationError('due date is required for payment status - pending')
        if attrs.get('generate_invoice') and not attrs.get('invoice_title'):
            raise serializers.ValidationError('invoice title is missing for invoice generation')
        if ( attrs.get("is_encrypted") or attrs.get("invoice_serial_id") ) and not ( attrs.get("is_encrypted") and attrs.get("invoice_serial_id") ):
            raise serializers.ValidationError("is_encrypted and invoice_serial_id both are required together.")
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
    appointment_id = serializers.PrimaryKeyRelatedField(read_only=True, pk_field=UUIDField(format='hex_verbose'))

    class Meta:
        model = doc_models.PartnersAppInvoice
        fields = ('id', 'created_at', 'updated_at', 'invoice_serial_id', 'consultation_fees', 'selected_invoice_items',
                  'payment_status', 'payment_type', 'due_date', 'invoice_title', 'sub_total_amount', 'tax_amount',
                  'tax_percentage', 'discount_amount', 'discount_percentage', 'total_amount', 'is_invoice_generated',
                  'is_valid', 'is_edited', 'edited_by', 'appointment_id', 'encoded_url', 'is_encrypted')


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


class ProviderEncryptResponseModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = doc_models.ProviderEncrypt
        fields = "__all__"


class EConsultCreateBodySerializer(serializers.Serializer):
    validity = serializers.DateTimeField(allow_null=True, required=False)
    doctor = serializers.IntegerField()
    patient = serializers.CharField()
    fees = serializers.FloatField(required=False)

    def validate(self, attrs):
        super().validate(attrs)
        e_consult_filter_dynamic_kwargs = dict()
        attrs['offline_p'] = True
        try:
            patient_id = UUID(attrs.get('patient'), version=4)
            patient = doc_models.OfflinePatients.objects.filter(id=patient_id).first()
            attrs['offline_p'] = True
            e_consult_filter_dynamic_kwargs['offline_patient'] = patient
        except ValueError:
            patient_id = attrs.get('patient')
            patient = UserProfile.objects.filter(id=patient_id).first()
            attrs['offline_p'] = False
            e_consult_filter_dynamic_kwargs['online_patient'] = patient
        if not patient:
            raise serializers.ValidationError("Patient not Found!")
        attrs['patient_obj'] = patient
        doc = doc_models.Doctor.objects.filter(id=attrs.get('doctor')).first()
        if not doc:
            raise serializers.ValidationError("Doctor not Found!")
        attrs['doctor_obj'] = doc
        e_consultation = provider_models.EConsultation.objects.filter(**e_consult_filter_dynamic_kwargs, doctor=doc,
                                                                      status__in=[
                                                                          provider_models.EConsultation.CREATED,
                                                                          provider_models.EConsultation.BOOKED,
                                                                          provider_models.EConsultation.RESCHEDULED_DOCTOR,
                                                                          provider_models.EConsultation.RESCHEDULED_PATIENT,
                                                                          provider_models.EConsultation.ACCEPTED]).order_by('-updated_at').first()
        if e_consultation:
            attrs['e_consultation'] = e_consultation
        return attrs


class EConsultListSerializer(serializers.ModelSerializer):
    doctor_name = serializers.ReadOnlyField(source='doctor.name')
    patient_name = serializers.SerializerMethodField()
    validity_status = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    doctor_auto_login_url = serializers.SerializerMethodField()
    patient_auto_login_url = serializers.SerializerMethodField()
    video_chat_url = serializers.SerializerMethodField()
    patient_phone_number = serializers.SerializerMethodField()

    def get_patient_type(self, obj):
        patient = None
        if obj.offline_patient:
            patient = obj.offline_patient
        elif obj.online_patient:
            patient = obj.online_patient
        return patient

    def get_patient_name(self, obj):
        patient = self.get_patient_type(obj)
        return patient.name

    def get_patient_id(self, obj):
        patient = self.get_patient_type(obj)
        return str(patient.id)

    def get_validity_status(self, obj):
        validity_status = 'past'
        if obj.validity and obj.validity > timezone.now():
            validity_status = 'current'
        return validity_status

    def get_doctor_auto_login_url(self, obj):
        request = self.context.get('request')
        return obj.rc_group.doctor_login_url if (obj.rc_group and request.user.user_type == User.DOCTOR) else None

    def get_patient_auto_login_url(self, obj):
        request = self.context.get('request')
        return obj.rc_group.patient_login_url if (obj.rc_group and request.user.user_type == User.CONSUMER) else None

    def get_video_chat_url(self, obj):
        return obj.get_video_chat_url()

    def get_patient_phone_number(self, obj):
        patient, patient_number = obj.get_patient_and_number()
        return patient_number

    class Meta:
        model = provider_models.EConsultation
        fields = ('id', 'doctor_name', 'doctor_id', 'patient_id', 'patient_name', 'fees', 'validity', 'payment_status',
                        'created_at', 'link', 'status', 'validity_status', 'validity', 'doctor_auto_login_url',
                        'patient_auto_login_url', 'video_chat_url', 'patient_phone_number')


class ConsumerEConsultListSerializer(EConsultListSerializer):
    doctor_qualification = serializers.SerializerMethodField()
    doctor_thumbnail = serializers.SerializerMethodField()

    def get_doctor_thumbnail(self, obj):
        request = self.context.get('request')
        return request.build_absolute_uri(obj.doctor.get_thumbnail()) if obj.doctor.get_thumbnail() else None

    def get_doctor_qualification(self, obj):
        ret_obj = list()
        qualifications = obj.doctor.qualifications.all()
        for qual in qualifications:
            ret_obj.append({
                "qualification": qual.qualification.name,
                "specialization": qual.specialization.name,
                "college": qual.college.name,
                "passing_year": qual.passing_year
            })
        return ret_obj

    class Meta:
        model = provider_models.EConsultation
        fields = ('id', 'doctor_name', 'doctor_id', 'patient_id', 'patient_name', 'fees', 'validity', 'payment_status',
                  'created_at', 'link', 'status', 'validity_status', 'validity', 'doctor_auto_login_url',
                  'patient_auto_login_url', 'video_chat_url', 'patient_phone_number', 'doctor_qualification',
                  'doctor_thumbnail')


class EConsultTransactionModelSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    user = serializers.PrimaryKeyRelatedField(queryset=User.objects.all())
    # profile = serializers.PrimaryKeyRelatedField(queryset=UserProfile.objects.all())
    price = serializers.DecimalField(max_digits=10, decimal_places=2)
    effective_price = serializers.DecimalField(max_digits=10, decimal_places=2)
    # status = serializers.IntegerField()
    # coupon = serializers.ListField(child=serializers.IntegerField(), required=False, default=[])
    cashback = serializers.DecimalField(max_digits=10, decimal_places=2)
    extra_details = serializers.JSONField(required=False)
    # coupon_data = serializers.JSONField(required=False)


class EConsultSerializer(serializers.Serializer):
    id = serializers.IntegerField(min_value=1)

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        consult_id = attrs['id']
        e_consultation = provider_models.EConsultation.objects.select_related('doctor', 'offline_patient', 'online_patient', 'rc_group') \
                                                              .prefetch_related('doctor__rc_user',
                                                                                'offline_patient__rc_user',
                                                                                'offline_patient__user',
                                                                                'offline_patient__patient_mobiles',
                                                                                'online_patient__rc_user',
                                                                                'online_patient__user') \
                                                              .filter(id=consult_id, created_by=user,
                                                                      status__in=[provider_models.EConsultation.BOOKED,
                                                                                  provider_models.EConsultation.CREATED]).first()
        if not e_consultation:
            raise serializers.ValidationError('Valid consultation not found for given id')
        attrs['e_consultation'] = e_consultation
        return attrs


class EConsultCommunicationSerializer(serializers.Serializer):
    rc_group_id = serializers.CharField(max_length=64)
    notification_types = serializers.ListField(child=serializers.IntegerField(min_value=1))
    sender_rc_user_id = serializers.CharField(max_length=64, required=False, allow_blank=True)
    receiver_rc_user_names = serializers.ListField(child=serializers.CharField(max_length=64), allow_empty=True, required=False)
    comm_types = serializers.MultipleChoiceField(choices=NotificationAction.NOTIFICATION_CHOICES, allow_empty=True, required=False)

    def validate(self, attrs):
        rc_group_id = attrs.get('rc_group_id')
        notification_types = attrs.get('notification_types')
        sender_rc_user_id = attrs.get('sender_rc_user_id')
        receiver_rc_user_names = attrs.get('receiver_rc_user_names')
        if NotificationAction.E_CONSULT_NEW_MESSAGE_RECEIVED in notification_types and not receiver_rc_user_names:
            raise serializers.ValidationError("receiver rocket chat user_names are required for new message notification")
        rc_group = provider_models.RocketChatGroups.objects.prefetch_related('econsultations',
                                                                             'econsultations__doctor',
                                                                             'econsultations__offline_patient',
                                                                             'econsultations__online_patient',
                                                                             'econsultations__offline_patient__user',
                                                                             'econsultations__online_patient__user',
                                                                             'econsultations__doctor__rc_user',
                                                                             'econsultations__offline_patient__rc_user',
                                                                             'econsultations__online_patient__rc_user',
                                                                             'econsultations__offline_patient__patient_mobiles',
                                                                             )\
                                                           .filter(group_id=rc_group_id).first()
        if not rc_group:
            raise serializers.ValidationError("rocket chat group not found.")
        e_consultation = rc_group.econsultations.all().order_by('-created_at')[0]
        patient, phone_number = e_consultation.get_patient_and_number()
        patient_rc_user = patient.rc_user
        doctor_rc_user = e_consultation.doctor.rc_user
        receiver_rc_users = list()
        sender_rc_user = None
        for rc_user in (doctor_rc_user, patient_rc_user):
            if rc_user.username in receiver_rc_user_names:
                receiver_rc_users.append(rc_user)
            elif rc_user.response_data['user']['_id'] == sender_rc_user_id:
                sender_rc_user = rc_user
        attrs['e_consultation'] = e_consultation
        attrs['patient'] = patient
        attrs['patient_rc_user'] = patient_rc_user
        attrs['doctor_rc_user'] = doctor_rc_user
        attrs['receiver_rc_users'] = receiver_rc_users
        attrs['sender_rc_user'] = sender_rc_user
        return attrs


class PartnerLabTestsListSerializer(serializers.Serializer):

    hospital_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    lab_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        filter_kwargs = dict()
        hospital_id = attrs.get('hospital_id')
        if hospital_id:
            filter_kwargs['hospital_id'] = hospital_id
        lab_id = attrs.get('lab_id')
        if lab_id:
            filter_kwargs['lab_id'] = lab_id
        hospital_lab_mapping_objs = provider_models.PartnerHospitalLabMapping.objects \
                                                                    .select_related('hospital', 'lab') \
                                                                    .prefetch_related(
                                                                        'lab__lab_pricing_group',
                                                                        'lab__lab_pricing_group__available_lab_tests',
                                                                        'lab__lab_pricing_group__available_lab_tests__sample_details',
                                                                        'lab__lab_pricing_group__available_lab_tests__sample_details__sample',
                                                                    ) \
                                                                    .filter(hospital__manageable_hospitals__phone_number=user.phone_number,
                                                                            **filter_kwargs,
                                                                            lab__is_b2b=True).distinct()
        hosp_lab_list = list()
        for mapping in hospital_lab_mapping_objs:
            if not mapping.lab.lab_pricing_group:
                raise serializers.ValidationError('Lab Pricing group needs to be set for the lab')
            hosp_lab_list.append({'hospital': mapping.hospital, 'lab': mapping.lab})
        attrs['hosp_lab_list'] = hosp_lab_list
        return attrs


class SampleCollectOrderCreateOrUpdateSerializer(serializers.Serializer):

    id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    offline_patient_id = serializers.UUIDField(required=False)
    hospital_id = serializers.IntegerField(min_value=1, required=False)
    lab_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    doctor_id = serializers.IntegerField(min_value=1, required=False)
    lab_test_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False)
    collection_datetime = serializers.DateTimeField(required=False, allow_null=True)
    lab_alerts = serializers.ListField(child=serializers.PrimaryKeyRelatedField(queryset=provider_models.TestSamplesLabAlerts.objects.all()), allow_empty=True, required=False)
    barcode_details = serializers.DictField(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=provider_models.PartnerLabSamplesCollectOrder.STATUS_CHOICES)
    only_status_update = serializers.BooleanField(default=False)

    def validate(self, attrs):
        request = self.context.get('request')
        user = request.user
        if not attrs.get('only_status_update') and not (attrs.get('offline_patient_id') and attrs.get('hospital_id') and attrs.get('doctor_id') and attrs.get('lab_test_ids')):
            raise serializers.ValidationError('either patient id or hospital id or doctor id or lab_test_ids missing')
        id = attrs.get('id')
        order_obj = provider_models.PartnerLabSamplesCollectOrder.objects.filter(id=id).first()
        if id and not order_obj:
            raise serializers.ValidationError('invalid order id')
        if attrs.get('status') and order_obj and not order_obj.status_update_checks(attrs.get('status')):
            raise serializers.ValidationError("incorrect status update")
        if attrs.get('only_status_update'):
            if not attrs.get('id'):
                raise serializers.ValidationError('Order id is required for just status update')
            else:
                attrs['order_obj'] = order_obj
                return attrs
        offline_patient_id = attrs.get('offline_patient_id')
        offline_patient = doc_models.OfflinePatients.objects.filter(id=offline_patient_id).first()
        if not offline_patient:
            raise serializers.ValidationError('invalid offline_patient_id')
        if not (offline_patient.name and offline_patient.gender and offline_patient.get_patient_mobile()) or \
                not (offline_patient.dob or offline_patient.calculated_dob):
            raise serializers.ValidationError('patient details incomplete')
        hospital_id = attrs.get('hospital_id')
        filter_kwargs = dict()
        lab_id = attrs.get('lab_id')
        if lab_id:
            filter_kwargs['lab_id'] = lab_id
        doctor_id = attrs.get('doctor_id')
        lab_test_ids = attrs.get('lab_test_ids')
        hospital_lab_mapping_obj = provider_models.PartnerHospitalLabMapping.objects \
                                                                             .select_related('hospital', 'lab') \
                                                                             .prefetch_related('hospital__hospital_doctors',
                                                                                               'hospital__hospital_doctors__doctor',
                                                                                               'lab__lab_pricing_group',
                                                                                               'lab__lab_pricing_group__available_lab_tests',
                                                                                               'lab__lab_pricing_group__available_lab_tests__sample_details',
                                                                                               'lab__lab_pricing_group__available_lab_tests__sample_details__sample',
                                                                                               ) \
                                                                             .filter(hospital__manageable_hospitals__phone_number=user.phone_number,
                                                                                     hospital_id=hospital_id,
                                                                                     **filter_kwargs,
                                                                                     lab__is_b2b=True).first()
        if not hospital_lab_mapping_obj:
            raise serializers.ValidationError('Hospital Lab mapping not found')
        hospital = hospital_lab_mapping_obj.hospital
        lab = hospital_lab_mapping_obj.lab
        all_available_lab_tests = lab.lab_pricing_group.available_lab_tests.all()
        doctor = None
        for mapping in hospital.hospital_doctors.all():
            if mapping.doctor.id == doctor_id:
                doctor = mapping.doctor
                break
        if not doctor:
            raise serializers.ValidationError('Hospital Doctor Mapping not found')
        available_lab_tests = list()
        for obj in all_available_lab_tests:
            if obj.test.id in lab_test_ids and hasattr(obj, 'sample_details') and obj.enabled:
                available_lab_tests.append(obj)
        if not available_lab_tests:
            raise serializers.ValidationError("no valid test found.")
        attrs['order_obj'] = order_obj
        attrs['offline_patient'] = offline_patient
        attrs['hospital'] = hospital
        attrs['doctor'] = doctor
        attrs['lab'] = lab
        attrs['available_lab_tests'] = available_lab_tests
        return attrs


class SelectedTestsDetailsSerializer(serializers.ModelSerializer):
    b2c_rate = serializers.SerializerMethodField()
    lab_test_id = serializers.IntegerField(source="test.id")
    lab_test_name = serializers.CharField(source="test.name")
    lab_test_is_package = serializers.BooleanField(source="test.is_package")
    lab_test_package_details = serializers.SerializerMethodField()

    def get_b2c_rate(self, obj):
        return int(obj.mrp) if obj.mrp else 0
        # return int(obj.get_deal_price())

    def get_lab_test_package_details(self, obj):
        details = list()
        if obj.test.is_package and hasattr(obj.test, 'packages'):
            for package_mapping in obj.test.packages.all():
                details.append({"test_id": package_mapping.lab_test.id, "test_name": package_mapping.lab_test.name})
        return details

    class Meta:
        model = diag_models.AvailableLabTest
        fields = ('lab_test_id', 'lab_test_name', 'b2c_rate', 'lab_test_is_package', 'lab_test_package_details')


class PartnerLabTestSampleDetailsModelSerializer(serializers.ModelSerializer):
    sample_details_id = serializers.IntegerField(source="id")
    name = serializers.CharField(source="sample.name")
    code = serializers.CharField(source="sample.code")

    class Meta:
        model = provider_models.PartnerLabTestSampleDetails
        fields = ('sample_details_id', 'name', 'code', 'material_required', 'volume', 'volume_unit',
                  'is_fasting_required', 'report_tat', 'reference_value', 'instructions')


class LabTestSamplesCollectionBarCodeModelSerializer(PartnerLabTestSampleDetailsModelSerializer):
    barcode = serializers.SerializerMethodField()
    barcode_scan_time = serializers.SerializerMethodField()

    def get_barcode_details(self, obj):
        all_barcode_details = self.context.get('barcode_details')
        if all_barcode_details and type(all_barcode_details) is dict and obj.sample.name in all_barcode_details:
            return all_barcode_details.get(obj.sample.name)
        return None

    def get_barcode(self, obj):
        barcode_details = self.get_barcode_details(obj)
        if type(barcode_details) is dict:
            return barcode_details.get('barcode')
        return None

    def get_barcode_scan_time(self, obj):
        barcode_details = self.get_barcode_details(obj)
        if type(barcode_details) is dict:
            return barcode_details.get('barcode_scan_time')
        return None

    class Meta:
        model = provider_models.PartnerLabTestSampleDetails
        fields = ('sample_details_id', 'name', 'code', 'material_required', 'volume', 'volume_unit',
                  'is_fasting_required', 'report_tat', 'reference_value', 'instructions', 'barcode',
                  'barcode_scan_time')


class PartnerLabSamplesCollectOrderModelSerializer(serializers.ModelSerializer):
    lab_reports = serializers.SerializerMethodField()

    def get_lab_reports(self, obj):
        request = self.context.get('request')
        report_mappings = obj.reports.all()
        response = list()
        for mapping in report_mappings:
            response.append(request.build_absolute_uri(mapping.report.url))
        return response

    class Meta:
        model = provider_models.PartnerLabSamplesCollectOrder
        fields = ('id', 'created_at', 'updated_at', 'status', 'collection_datetime', 'samples', 'offline_patient',
                  'lab', 'hospital', 'doctor', 'lab_alerts', 'selected_tests_details', 'lab_reports')


class TestSamplesLabAlertsModelSerializer(serializers.ModelSerializer):

    class Meta:
        model = provider_models.TestSamplesLabAlerts
        fields = ('id', 'name')
