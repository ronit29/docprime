from django.contrib import admin
from django import forms
from django.db.models import Count, Q
from django.db.models import F
from rest_framework import serializers
from dal import autocomplete
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer
from ondoc.crm.constants import constants
from ondoc.doctor.models import OpdAppointment, DoctorPracticeSpecialization, PracticeSpecialization, Hospital
from ondoc.diagnostic.models import LabAppointment, LabTest, Lab
from ondoc.insurance.models import InsurancePlanContent, InsurancePlans, InsuredMembers, UserInsurance, StateGSTCode, \
     ThirdPartyAdministrator, InsuranceEligibleCities, InsuranceCity, InsuranceDistrict, InsuranceDeal, \
    InsurerPolicyNumber, InsuranceLead, EndorsementRequest, InsuredMemberDocument, InsuranceEligibleCities,\
    InsuranceThreshold, UserBank, InsuredMemberHistory, UserBankDocument
from import_export.admin import ImportExportMixin, ImportExportModelAdmin, base_formats
import nested_admin
from import_export import fields, resources
from datetime import datetime
from ondoc.insurance.models import InsuranceDisease
from django.db import transaction
from django.conf import settings


class InsurerAdmin(admin.ModelAdmin):

    list_display = ['name', 'enabled', 'is_live']
    list_filter = ['name']
    search_fields = ['name']


class InsurerFloatAdmin(admin.ModelAdmin):
    list_display = ['insurer']
    readonly_fields = ['insurer', 'current_float']


class InsurancePlanContentInline(admin.TabularInline):
    model = InsurancePlanContent
    fields = ('title', 'content')
    extra = 0
    # can_delete = False
    # show_change_link = False
    # can_add = False
    # readonly_fields = ("first_name", 'last_name', 'relation', 'dob', 'gender', )


class InsurerPolicyNumberInline(admin.TabularInline):
    model = InsurerPolicyNumber
    fields = ('insurer', 'insurer_policy_number')
    extra = 0


class InsurancePlanAdminForm(forms.ModelForm):

    is_selected = forms.BooleanField(required=False)

    def clean_is_selected(self):
        is_selected = self.cleaned_data.get('is_selected', False)
        insurer = self.cleaned_data.get('insurer')
        if is_selected and insurer:
            if self.instance and self.instance.id:
                if insurer.plans.filter(is_selected=True).exclude(id=self.instance.id).exists():
                    raise forms.ValidationError('Only one plan can be marked is_selected true for 1 Insurer.')
            else:
                if insurer.plans.filter(is_selected=True).exists():
                    raise forms.ValidationError('Only one plan can be marked is_selected true for 1 Insurer.')

        return is_selected


class InsuranceThresholdInline(admin.TabularInline):
    model = InsuranceThreshold
    #fields = ('__all__',)
    extra = 0


class InsurancePlansAdmin(admin.ModelAdmin):

    list_display = ['insurer', 'name','internal_name', 'amount', 'is_selected','get_policy_prefix']
    inlines = [InsurancePlanContentInline, InsurerPolicyNumberInline,InsuranceThresholdInline]
    search_fields = ['name']
    form = InsurancePlanAdminForm


class InsuranceThresholdAdmin(admin.ModelAdmin):

    list_display = ['insurance_plan']


# class InsuranceTransaction

class InsuredMembersInline(admin.TabularInline):
    model = InsuredMembers
    fields = ("first_name", 'last_name', 'relation', 'dob', 'gender', )
    extra = 0
    can_delete = False
    show_change_link = False
    can_add = False
    readonly_fields = ("first_name", 'last_name', 'relation', 'dob', 'gender', )


class UserBankInline(admin.TabularInline):
    model = UserBank
    fields = ('insurance', 'bank_name', 'account_number', 'account_holder_name', 'ifsc_code', 'bank_address',)
    extra = 0
    can_delete = False
    show_change_link = False
    can_add = True
    readonly_fields = ('insurance',)


class UserBankDocumentInline(admin.TabularInline):
    model = UserBankDocument
    fields = ('insurance', 'document_image',)
    extra = 0
    can_delete = False
    show_change_link = False
    can_add = True
    readonly_fields = ('insurance',)


class InsuredMemberResource(resources.ModelResource):
    purchase_date = fields.Field()
    expiry_date = fields.Field()
    policy_number = fields.Field()
    insurance_plan = fields.Field()
    premium_amount = fields.Field()
    nominee_name = fields.Field()
    nominee_address = fields.Field()
    sum_insured = fields.Field()
    age = fields.Field()
    account_holder_name = fields.Field()
    account_number = fields.Field()
    ifsc = fields.Field()
    aadhar_number = fields.Field()
    diabetes = fields.Field()
    heart_diseases = fields.Field()
    cancer = fields.Field()
    pregnancy = fields.Field()
    customer_consent_recieved = fields.Field()
    coi = fields.Field()

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):
        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(kwargs.get('to_date'), '%Y-%m-%d').date()]
        return InsuredMembers.objects.filter(created_at__date__range=date_range).prefetch_related('user_insurance')

    class Meta:
        model = InsuredMembers
        fields = ('id', 'title', 'first_name', 'middle_name', 'last_name', 'dob', 'gender', 'relation', 'email',
                  'phone_number', 'address', 'town', 'district', 'state', 'pincode')
        export_order = ('id', 'title', 'first_name', 'middle_name', 'last_name', 'dob', 'gender',
                        'relation', 'email', 'phone_number', 'address', 'town', 'district', 'state', 'pincode',
                        'purchase_date', 'expiry_date', 'policy_number', 'insurance_plan', 'premium_amount',
                        'nominee_name', 'nominee_address', 'sum_insured', 'age', 'account_holder_name', 'account_number'
                        ,'ifsc', 'aadhar_number', 'diabetes', 'heart_diseases', 'cancer', 'pregnancy',
                        'customer_consent_recieved', 'coi')

    def dehydrate_dob(self, insured_members):
        dob = insured_members.dob
        return str(dob.strftime('%d/%m/%Y'))

    def dehydrate_gender(self, insured_members):
        gender = str(insured_members.gender)
        if gender == "m":
            return "Male"
        elif gender == "f":
            return "Female"
        else:
            return "Other"

    def dehydrate_purchase_date(self, insured_members):
        return str(insured_members.user_insurance.purchase_date.date())

    def dehydrate_expiry_date(self, insured_members):
        return str(insured_members.user_insurance.expiry_date.date())

    def dehydrate_policy_number(self, insured_members):
        return str(insured_members.user_insurance.policy_number)

    def dehydrate_insurance_plan(self, insured_members):
        return insured_members.user_insurance.insurance_plan.name

    def dehydrate_premium_amount(self, insured_members):
        return insured_members.user_insurance.insurance_plan.amount

    def dehydrate_nominee_name(self, insured_members):
        return "legal heir"

    def dehydrate_nominee_address(self, insured_members):
        return ""

    def dehydrate_sum_insured(self, insured_members):
        return ""

    def dehydrate_age(self, insured_members):
        return int((datetime.now().date() - insured_members.dob).days/365)

    def dehydrate_account_holder_name(self, insured_members):
        return ""

    def dehydrate_account_number(self, insured_members):
        return ""

    def dehydrate_ifsc(self, insured_members):
        return ""

    def dehydrate_aadhar_number(self, insured_members):
        return ""

    def dehydrate_diabetes(self, insured_members):
        diseases = InsuranceDisease.objects.filter(disease__iexact='diabetes').first()
        if diseases:
            return str(diseases.affected_members.filter(member=insured_members).exists())
        return "False"

    def dehydrate_heart_diseases(self, insured_members):
        diseases = InsuranceDisease.objects.filter(disease__iexact='Heart Disease').first()
        if diseases:
            return str(diseases.affected_members.filter(member=insured_members).exists())
        return "False"

    def dehydrate_cancer(self, insured_members):
        diseases = InsuranceDisease.objects.filter(disease__iexact='Cancer').first()
        if diseases:
            return str(diseases.affected_members.filter(member=insured_members).exists())
        return "False"

    def dehydrate_pregnancy(self, insured_members):
        diseases = InsuranceDisease.objects.filter(disease__iexact='Pregnancy').first()
        if diseases:
            return str(diseases.affected_members.filter(member=insured_members).exists())
        return "False"

    def dehydrate_customer_consent_recieved(self, insured_members):
        return ""

    def dehydrate_coi(self, insured_members):
        # return insured_members.user_insurance.coi.url

        return insured_members.user_insurance.coi.url if insured_members.user_insurance.coi is not None and \
                                                                          insured_members.user_insurance.coi.name else ''


class InsuredMembersAdmin(ImportExportMixin, nested_admin.NestedModelAdmin):
    resource_class = InsuredMemberResource
    export_template_name = "export_template_name.html"
    formats = (base_formats.XLS,)
    list_display = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number']
    readonly_fields = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number', 'relation', 'profile']

    def get_export_queryset(self, request):
        super().get_export_queryset(request)

    def get_export_data(self, file_format, queryset, *args, **kwargs):
        """
        Returns file_format representation for given queryset.
        """
        kwargs['from_date'] = kwargs.get('request').POST.get('from_date')
        kwargs['to_date'] = kwargs.get('request').POST.get('to_date')
        request = kwargs.pop("request")
        resource_class = self.get_export_resource_class()
        data = resource_class(**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        export_data = file_format.export_data(data)
        return export_data

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class UserInsuranceDoctorResource(resources.ModelResource):
    appointment_id = fields.Field()
    policy_number = fields.Field()
    member_id = fields.Field()
    name = fields.Field()
    relationship_with_proposer = fields.Field()
    date_of_consultation = fields.Field()
    name_of_doctor = fields.Field()
    provider_code_of_doctor = fields.Field()
    speciality_of_doctor = fields.Field()
    diagnosis = fields.Field()
    icd_code_of_diagnosis = fields.Field()
    name_of_clinic = fields.Field()
    address_of_clinic = fields.Field()
    pan_card_of_clinic = fields.Field()
    existing_condition = fields.Field()
    amount_to_be_paid = fields.Field()
    bank_detail_of_center = fields.Field()
    gst_number_of_center = fields.Field()
    booking_date = fields.Field()
    status = fields.Field()

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):
        request = kwargs.get('request')
        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]
        if request and request.user.is_member_of(constants['INSURANCE_GROUP']):
            appointment = OpdAppointment.objects.filter(~Q(status=OpdAppointment.CANCELLED),
                                                        created_at__date__range=date_range,
                                                        insurance__isnull=False).prefetch_related('insurance')
        else:
            appointment = OpdAppointment.objects.filter(created_at__date__range=date_range,
                                                        status=OpdAppointment.COMPLETED,
                                                        insurance__isnull=False).prefetch_related('insurance')
        return appointment

    class Meta:
        model = UserInsurance
        fields = ()
        export_order = ('appointment_id', 'policy_number', 'member_id', 'name', 'relationship_with_proposer', 'date_of_consultation',
                        'name_of_doctor', 'provider_code_of_doctor', 'speciality_of_doctor', 'diagnosis',
                        'icd_code_of_diagnosis', 'name_of_clinic', 'address_of_clinic', 'amount_to_be_paid',
                        'booking_date', 'status', 'pan_card_of_clinic',
                        'existing_condition', 'bank_detail_of_center', 'gst_number_of_center')

    def get_insured_member(self, profile):
        insured_member = InsuredMembers.objects.filter(profile_id=profile).first()
        if insured_member:
            return insured_member
        else:
            return None

    def get_merchant_details(self, content_type, obj):
        from ondoc.authentication.models import AssociatedMerchant
        from ondoc.authentication.models import Merchant
        associate_merchant_obj = AssociatedMerchant.objects.filter(content_type_id=content_type.id,
                                                                   object_id=obj.id).first()
        if associate_merchant_obj:
            merchant_obj = Merchant.objects.filter(id=associate_merchant_obj.merchant_id).first()
            return merchant_obj
        else:
            None

    def dehydrate_appointment_id(self, appointment):
        return str(appointment.id)

    def dehydrate_appointment_type(self,appointment):
        return "Doctor"

    def dehydrate_policy_number(self, appointment):
        return str(appointment.insurance.policy_number)

    def dehydrate_member_id(self, appointment):
        member = self.get_insured_member(appointment.profile_id)
        if member:
            return str(member.id)
        else:
            return ""

    def dehydrate_name(self, appointment):
        member = self.get_insured_member(appointment.profile_id)
        if member:
            return str(member.first_name)
        else:
            return ""

    def dehydrate_relationship_with_proposer(self, appointment):
        member = self.get_insured_member(appointment.profile_id)
        if member:
            return str(member.relation)
        else:
            return ""

    def dehydrate_date_of_consultation(self, appointment):
        return str(appointment.time_slot_start)

    def dehydrate_name_of_doctor(self, appointment):
        return str(appointment.doctor.name)

    def dehydrate_provider_code_of_doctor(self, appointment):
        doctor = appointment.doctor
        hospital = appointment.hospital
        return str(doctor.id) + "-" + str(hospital.id)

    def dehydrate_speciality_of_doctor(self, appointment):
        doctor = appointment.doctor
        doctor_specialization_ids = DoctorPracticeSpecialization.objects.filter(doctor_id=doctor).values_list(
            'specialization_id', flat=True)
        specializations = PracticeSpecialization.objects.filter(id__in=doctor_specialization_ids).values_list(
            'name', flat=True)
        spd = []
        for sp in specializations:
            spd.append(sp)
        doctor_specialization = ','.join(map(str, spd))
        return doctor_specialization

    def dehydrate_diagnosis(self, appointment):
        return ""

    def dehydrate_icd_code_of_diagnosis(self, appointment):
        return ""

    def dehydrate_name_of_clinic(self, appointment):
        return str(appointment.hospital.name)

    def dehydrate_address_of_clinic(self, appointment):
        building = str(appointment.hospital.building)
        sublocality = str(appointment.hospital.sublocality)
        locality = str(appointment.hospital.locality)
        city = str(appointment.hospital.city)
        state = str(appointment.hospital.state)
        pincode = str(appointment.hospital.pin_code)
        return building + " " + sublocality + " " + locality + " " + city + " " + state + " " + pincode

    def dehydrate_pan_card_of_clinic(self, appointment):
        return ""

    def dehydrate_existing_condition(self, appointment):
        return ""

    def dehydrate_amount_to_be_paid(self, appointment):
        return str(appointment.fees)

    def dehydrate_bank_detail_of_center(self, appointment):
        # from django.contrib.contenttypes.models import ContentType
        # content_type = ContentType.objects.get_for_model(Hospital)
        # center_details = self.get_merchant_details(content_type, appointment.hospital)
        # if center_details:
        #     beneficiary_name = center_details.beneficiary_name
        #     account_number = center_details.account_number
        #     ifsc_code = center_details.ifsc_code
        #     return str(beneficiary_name) + "," + str(account_number), + "," + ifsc_code
        # else:
        #     return ""
        return ""

    def dehydrate_gst_number_of_center(self, appointment):
        return ""

    def dehydrate_booking_date(self, appointment):
        return str(appointment.created_at.date())

    def dehydrate_status(self, appointment):
        if appointment.status == 1:
            return "CREATED"
        elif appointment.status == 2:
            return "BOOKED"
        elif appointment.status == 3 or appointment.status == 4:
            return "RESCHEDULE"
        elif appointment.status == 5:
            return "ACCEPTED"
        elif appointment.status == 7:
            return "COMPLETED"
        else:
            return ""


class UserInsuranceLabResource(resources.ModelResource):
    appointment_id = fields.Field()
    policy_number = fields.Field()
    member_id = fields.Field()
    name = fields.Field()
    relationship_with_proposer = fields.Field()
    date_of_consultation = fields.Field()
    name_of_diagnostic_center = fields.Field()
    provider_code_of_the_center = fields.Field()
    name_of_tests = fields.Field()
    address_of_center = fields.Field()
    pan_card_of_center = fields.Field()
    existing_condition = fields.Field()
    amount_to_be_paid = fields.Field()
    bank_detail_of_center = fields.Field()
    gst_number_of_center = fields.Field()
    booking_date = fields.Field()
    status = fields.Field()
    number_of_tests = fields.Field()

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):

        request = kwargs.get('request')
        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]
        if request and request.user.is_member_of(constants['INSURANCE_GROUP']):
            appointment = LabAppointment.objects.filter(~Q(status=LabAppointment.CANCELLED),
                                                        created_at__date__range=date_range,
                                                        insurance__isnull=False).prefetch_related('insurance')
        else:
            appointment = LabAppointment.objects.filter(created_at__date__range=date_range,
                                                        status=LabAppointment.COMPLETED,
                                                        insurance__isnull=False).prefetch_related('insurance')
        return appointment

    class Meta:
        model = UserInsurance
        fields = ()
        export_order = ('appointment_id', 'policy_number', 'member_id', 'name', 'relationship_with_proposer',
                        'date_of_consultation', 'name_of_diagnostic_center', 'provider_code_of_the_center',
                        'name_of_tests', 'number_of_tests', 'address_of_center', 'amount_to_be_paid', 'booking_date', 'status',
                        'bank_detail_of_center', 'gst_number_of_center', 'pan_card_of_center', 'existing_condition')

    def get_insured_member(self, profile):
        insured_member = InsuredMembers.objects.filter(profile_id=profile).first()
        if insured_member:
            return insured_member
        else:
            return None

    def dehydrate_appointment_id(self, appointment):
        return str(appointment.id)

    def dehydrate_appointment_type(self,appointment):
        return "Lab"

    def dehydrate_policy_number(self, appointment):
        return str(appointment.insurance.policy_number)

    def dehydrate_member_id(self, appointment):
        member = self.get_insured_member(appointment.profile_id)
        if member:
            return str(member.id)
        else:
            return ""

    def dehydrate_name(self, appointment):
        member = self.get_insured_member(appointment.profile_id)
        if member:
            return str(member.first_name)
        else:
            return ""

    def dehydrate_relationship_with_proposer(self, appointment):
        member = self.get_insured_member(appointment.profile_id)
        if member:
            return str(member.relation)
        else:
            return ""

    def dehydrate_date_of_consultation(self, appointment):
        return str(appointment.time_slot_start)

    def dehydrate_name_of_diagnostic_center(self, appointment):
        return appointment.lab.name if appointment.lab else ""

    def dehydrate_provider_code_of_the_center(self, appointment):
        return str(appointment.lab.id) if appointment.lab else ""

    def dehydrate_name_of_tests(self, appointment):
        return ", ".join(list(map(lambda test: test.name, appointment.tests.all())))

    def dehydrate_number_of_tests(self, appointment):
        return str(appointment.tests.all().count())

    def dehydrate_address_of_center(self, appointment):
        if not appointment.lab:
            return ''
        building = str(appointment.lab.building)
        sublocality = str(appointment.lab.sublocality)
        locality = str(appointment.lab.locality)
        city = str(appointment.lab.city)
        state = str(appointment.lab.state)
        pincode = str(appointment.lab.pin_code)
        return building + " " + sublocality + " " + locality + " " + city + " " + state + " " + pincode

    def dehydrate_pan_card_of_center(self, appointment):
        # from django.contrib.contenttypes.models import ContentType
        # content_type = ContentType.objects.get_for_model(Lab)
        # center_details = self.get_merchant_details(content_type, appointment.lab)
        # if center_details:
        #     return str(center_details.pan_number)
        # else:
        #     ""
        return ""

    def dehydrate_existing_condition(self, appointment):
        return ""

    def dehydrate_amount_to_be_paid(self, appointment):
        return str(appointment.agreed_price)

    def dehydrate_bank_detail_of_center(self, appointment):
        # from django.contrib.contenttypes.models import ContentType
        # content_type = ContentType.objects.get_for_model(Lab)
        # center_details = self.get_merchant_details(content_type, appointment.lab)
        # if center_details:
        #     beneficiary_name = center_details.beneficiary_name
        #     account_number = center_details.account_number
        #     ifsc_code = center_details.ifsc_code
        #     return str(beneficiary_name) + "," + str(account_number), + "," + ifsc_code
        # else:
        #     return ""
        return ""

    def dehydrate_gst_number_of_center(self, appointment):
        return ""

    def dehydrate_booking_date(self, appointment):
        return str(appointment.created_at)

    def dehydrate_status(self, appointment):
        if appointment.status == 1:
            return "CREATED"
        elif appointment.status == 2:
            return "BOOKED"
        elif appointment.status == 3 or appointment.status == 4:
            return "RESCHEDULE"
        elif appointment.status == 5:
            return "ACCEPTED"
        elif appointment.status == 7:
            return "COMPLETED"
        else:
            return ""


class UserInsuranceResource(resources.ModelResource):
    id = fields.Field()
    insurance_plan = fields.Field()
    user_name = fields.Field()
    phone_number = fields.Field()
    purchase_date = fields.Field()
    expiry_date = fields.Field()
    policy_number = fields.Field()
    amount = fields.Field()
    receipt_number = fields.Field()
    coi = fields.Field()
    status = fields.Field()
    matrix_lead = fields.Field()
    pg_order_no = fields.Field()

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):

        request = kwargs.get('request')
        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]

        insurance = UserInsurance.objects.filter(created_at__date__range=date_range)
        return insurance

    class Meta:
        model = UserInsurance
        fields = ()
        export_order = ('id', 'insurance_plan', 'user_name', 'phone_number', 'purchase_date', 'expiry_date',
                        'policy_number', 'amount', 'receipt_number',
                        'coi', 'status', 'matrix_lead')

    def dehydrate_id(self, insurance):
        return str(insurance.id)

    def dehydrate_insurance_plan(self, insurance):
        return str(insurance.insurance_plan.name)

    def dehydrate_user_name(self, insurance):
        from ondoc.authentication.models import UserProfile
        profile = UserProfile.objects.filter(user=insurance.user).first()
        if profile:
            return str(profile.name)
        else:
            return ""

    def dehydrate_phone_number(self, insurance):
        return str(insurance.user.phone_number)

    def dehydrate_purchase_date(self, insurance):
        return str(insurance.purchase_date)

    def dehydrate_expiry_date(self, insurance):
        return str(insurance.expiry_date.date())

    def dehydrate_policy_number(self, insurance):
        return str(insurance.policy_number)

    def dehydrate_amount(self, insurance):
        return str(insurance.premium_amount)

    def dehydrate_receipt_number(self, insurance):
        return str(insurance.receipt_number)

    def dehydrate_coi(self, insurance):
        return insurance.coi.url if insurance.coi is not None and insurance.coi.name else ''

    def dehydrate_status(self, insurance):
        if insurance.status == 1:
            return "ACTIVE"
        elif insurance.status == 2:
            return "CANCELLED"
        elif insurance.status == 3:
            return "EXPIRED"
        elif insurance.status == 4:
            return "ONHOLD"
        elif insurance.status == 5:
            return "CANCEL_INITIATE"

    def dehydrate_matrix_lead(self, insurance):
        return str(insurance.matrix_lead_id)

    def dehydrate_pg_order_no(self, insurance):
        from ondoc.account.models import Order
        order = Order.objects.filter(reference_id=insurance.id).first()
        if not order:
            return ""
        transaction = order.getTransactions()
        if not transaction:
            return ""
        return str(transaction.first().order_no)


class CustomDateInput(forms.DateInput):
    input_type = 'date'


# class UserInsuranceForm(forms.ModelForm):
#     start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder': 'Select a date'}))
#     end_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder': 'Select a date'}))
#
#     def clean(self):
#         cleaned_data = super().clean()
#         start = cleaned_data.get("start_date")
#         end = cleaned_data.get("end_date")
#         if start and end and start >= end:
#             raise forms.ValidationError("Start Date should be less than end Date")

class UserInsuranceForm(forms.ModelForm):

    status_choices = [(UserInsurance.ACTIVE, "Active"), (UserInsurance.CANCEL_INITIATE, 'Cancel Initiate'),
                      (UserInsurance.CANCELLED, "Cancelled")]
    case_choices = [(UserInsurance.REFUND, "Refundable"), (UserInsurance.NO_REFUND, "Non-Refundable")]
    cancel_after_utilize_choices = [('YES', 'Yes'), ('NO', 'No')]
    status = forms.ChoiceField(choices=status_choices, required=True)
    cancel_after_utilize_insurance = forms.ChoiceField(choices=cancel_after_utilize_choices, initial='NO',  widget=forms.RadioSelect())
    cancel_reason = forms.CharField(max_length=400, required=False)
    cancel_case_type = forms.ChoiceField(choices=case_choices, initial=UserInsurance.REFUND)


    def clean(self):
        super().clean()
        data = self.cleaned_data
        status = data.get('status')
        case_type = data.get('cancel_after_utilize_insurance')
        cancel_reason = data.get('cancel_reason')
        cancel_case_type = data.get('cancel_case_type')
        # if int(status) == UserInsurance.ONHOLD:
        #     if not onhold_reason:
        #         raise forms.ValidationError("In Case of ONHOLD status, Onhold reason is mandatory")
        if case_type=="NO" and (int(status) == UserInsurance.CANCEL_INITIATE or int(status) == UserInsurance.CANCELLED):
            if not cancel_reason:
                raise forms.ValidationError('For Cancel Initiation, Cancel reason is mandatory')
            if not self.instance.is_bank_details_exist():
                raise forms.ValidationError('For Cancel Initiation, Bank details is mandatory')
            insured_opd_completed_app_count = OpdAppointment.get_insured_completed_appointment(self.instance)
            insured_lab_completed_app_count = LabAppointment.get_insured_completed_appointment(self.instance)
            if insured_lab_completed_app_count > 0:
                raise forms.ValidationError('Lab appointment with insurance have been completed, '
                                            'Cancellation could not proceed')
            if insured_opd_completed_app_count > 0:
                raise forms.ValidationError('OPD appointment with insurance have been completed, '
                                            'Cancellation could not proceed')
        if case_type == "YES" and (int(status) == UserInsurance.CANCEL_INITIATE or int(status) == UserInsurance.CANCELLED):
            if not cancel_reason:
                raise forms.ValidationError('For Cancel Initiation, Cancel reason is mandatory')
            if int(cancel_case_type) == UserInsurance.REFUND and not self.instance.is_bank_details_exist():
                raise forms.ValidationError('In Case of Refundable Bank details are mandatory, please upload bank details')
        if int(status) == UserInsurance.CANCELLED and not self.instance.status == UserInsurance.CANCEL_INITIATE:
            raise forms.ValidationError('Cancellation is only allowed for cancel initiate status')
        if self.instance.status == UserInsurance.CANCELLED:
            raise forms.ValidationError('Cancelled Insurance could not be changed')

    class Meta:
        fields = '__all__'


class UserBankAdmin(admin.ModelAdmin):
    model = UserBank
    fields = ['bank_name', 'account_holder_name', 'account_number', 'ifsc_code', 'bank_address']
    list_display = ['id', 'account_holder_name', 'account_number']


class UserBankDocumentAdmin(admin.ModelAdmin):
    model = UserBankDocument
    fields = ['insurance']
    list_display = ['insurance']


class UserInsuranceAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = (UserInsuranceDoctorResource, UserInsuranceLabResource, UserInsuranceResource)
    export_template_name = "export_insurance_report.html"
    formats = (base_formats.XLS,)
    model = UserInsurance
    date_hierarchy = 'created_at'
    list_filter = ['status']

    def user_policy_number(self, obj):
        return str(obj.policy_number)

    def user_name(self, obj):
        from ondoc.authentication.models import UserProfile
        user_profile = UserProfile.objects.filter(user=obj.user).first()
        return str(user_profile.name)

    list_display = ['id', 'insurance_plan', 'user_name', 'user', 'policy_number', 'purchase_date', 'status']
    fields = ['insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount',
              'merchant_payout', 'status', 'cancel_reason', 'cancel_after_utilize_insurance', 'cancel_case_type']
    readonly_fields = ('insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount', 'merchant_payout')
    inlines = [InsuredMembersInline, UserBankInline, UserBankDocumentInline]
    form = UserInsuranceForm
    search_fields = ['id']

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, None)

        queryset = queryset.filter(Q(user__profiles__name__icontains=search_term)).distinct()

        return queryset, use_distinct

    def get_export_queryset(self, request):
        super().get_export_queryset(request)

    def get_export_data(self, file_format, queryset, *args, **kwargs):
        """
        Returns file_format representation for given queryset.
        """
        kwargs['from_date'] = kwargs.get('request').POST.get('from_date')
        kwargs['to_date'] = kwargs.get('request').POST.get('to_date')
        kwargs['appointment_type'] = kwargs.get('request').POST.get('appointment_type')
        request = kwargs.pop("request")
        kwargs['request'] = request
        resource_class = self.get_export_resource_class()
        # data = resource_class(**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        if kwargs['appointment_type'] == 'Doctor':
            data = resource_class[0](**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        elif kwargs['appointment_type'] == 'Lab':
            data = resource_class[1](**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        elif kwargs['appointment_type'] == 'Insurance':
            data = resource_class[2](**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        export_data = file_format.export_data(data)
        return export_data

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        responsible_user = request.user
        obj._responsible_user = responsible_user if responsible_user and not responsible_user.is_anonymous else None
        if request.user.is_member_of(constants['SUPER_INSURANCE_GROUP']):
            if obj.status == UserInsurance.ACTIVE:
                super(UserInsuranceAdmin, self).save_model(request, obj, form, change)
            # elif obj.status == UserInsurance.ONHOLD:
            #     if obj.onhold_reason:
            #         super(UserInsuranceAdmin, self).save_model(request, obj, form, change)
            elif obj.status == UserInsurance.CANCEL_INITIATE:
                response = obj.process_cancellation()
                if response.get('success', None):
                    super(UserInsuranceAdmin, self).save_model(request, obj, form, change)
            elif obj.status == UserInsurance.CANCELLED:
                super(UserInsuranceAdmin, self).save_model(request, obj, form, change)


class InsuranceDiseaseAdmin(admin.ModelAdmin):
    list_display = ['disease']


class StateGSTCodeResource(resources.ModelResource):
    class Meta:
        model = StateGSTCode
        fields = ('id', 'gst_code', 'state_name')


class StateGSTCodeAdmin(ImportExportModelAdmin):
    model = StateGSTCode
    resource_class = StateGSTCodeResource
    fields = ('id', 'gst_code', 'state_name')
    list_display = ('id', 'gst_code', 'state_name')


class InsuranceCityResource(resources.ModelResource):
    class Meta:
        model = InsuranceCity
        fields = ('id', 'city_code', 'city_name', 'state')


class InsuranceCityAdmin(ImportExportModelAdmin):
    model = InsuranceCity
    resource_class = InsuranceCityResource
    fields = ('id', 'city_code', 'city_name', 'state')
    list_display = ('id', 'city_code', 'city_name', 'state')


class InsuranceDistrictResource(resources.ModelResource):
    class Meta:
        model = InsuranceDistrict
        fields = ('id', 'district_code', 'district_name', 'state')


class InsuranceDistrictAdmin(ImportExportModelAdmin):
    model = InsuranceDistrict
    resource_class = InsuranceDistrictResource
    fields = ('id', 'district_code', 'district_name', 'state')
    list_display = ('id', 'district_code', 'district_name', 'state')


# class InsurerPolicyNumberForm(forms.ModelForm):
#
#     class Meta:
#         widgets = {
#             'insurer': autocomplete.ModelSelect2(url='insurer-autocomplete'),
#             'insurance_plan': autocomplete.ModelSelect2(url='insurance-plan-autocomplete', forward=['insurer'])
#         }


class InsurerPolicyNumberAdmin(admin.ModelAdmin):
    model = InsurerPolicyNumber
    fields = ('insurer', 'insurance_plan', 'insurer_policy_number')
    list_display = ('insurer', 'insurance_plan', 'insurer_policy_number', 'created_at')
    # form = InsurerPolicyNumberForm
    # search_fields = ['insurer']
    # autocomplete_fields = ['insurer', 'insurance_plan']


class InsuranceDealAdmin(admin.ModelAdmin):
    # model = InsuranceDeal
    fields = ('deal_id', 'insurer', 'commission', 'tax', 'deal_start_date', 'deal_end_date')
    list_display = ('deal_id', 'insurer', 'commission', 'tax', 'deal_start_date', 'deal_end_date')


class InsuranceLeadResource(resources.ModelResource):
    id = fields.Field()
    name = fields.Field()
    phone_number = fields.Field()
    status = fields.Field()
    matrix_lead_id = fields.Field()
    created_at = fields.Field()
    updated_at = fields.Field()

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):
        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]

        leads = InsuranceLead.objects.filter(created_at__date__range=date_range).order_by('-updated_at')
        return leads

    class Meta:
        model = InsuranceLead
        fields = ()
        export_order = ('id', 'name', 'phone_number', 'status', 'matrix_lead_id', 'created_at', 'updated_at')

    def dehydrate_id(self, obj):
        return str(obj.id)

    def dehydrate_matrix_lead_id(self, obj):
        return str(obj.matrix_lead_id)

    def dehydrate_created_at(self, obj):
        return str(obj.created_at)

    def dehydrate_updated_at(self, obj):
        return str(obj.updated_at)

    def dehydrate_name(self, obj):
        user = obj.user
        from ondoc.authentication.models import UserProfile
        user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
        if user_profile:
            return str(user_profile.name)
        elif obj.extras.get('lead_data'):
            return obj.extras.get('lead_data').get('name', '')
        else:
            return ""

    def dehydrate_phone_number(self, obj):
        user = obj.user
        if user:
            return str(obj.user.phone_number)
        else:
            return str(obj.phone_number)

    def dehydrate_status(self, obj):
        user_insurance = UserInsurance.objects.filter(user=obj.user).order_by('-id').first()
        if user_insurance:
            return "Booked"
        else:
            return "New"


class InsuranceLeadAdmin(ImportExportModelAdmin, admin.ModelAdmin):
    model = InsuranceLead
    resource_class = InsuranceLeadResource
    export_template_name = "export_insurance_lead_report.html"
    formats = (base_formats.XLS,)
    ordering = ('-updated_at',)
    date_hierarchy = 'created_at'

    def name(self, obj):
        user = obj.user
        from ondoc.authentication.models import UserProfile
        user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
        if user_profile:
            return str(user_profile.name)
        elif obj.extras.get('lead_data'):
            return obj.extras.get('lead_data').get('name', '')
        else:
            return ""

    def source(self, obj):
        extras = obj.extras
        return extras.get('source', '')

    def lead_phone_number(self, obj):
        user = obj.user
        if user:
            return str(obj.user.phone_number)
        else:
            return str(obj.phone_number)

    def status(self, obj):
        user_insurance = UserInsurance.objects.filter(user=obj.user).order_by('-id').first()
        if user_insurance:
            return "Booked"
        else:
            return "New"

    list_display = ('id', 'name',  'lead_phone_number', 'status', 'matrix_lead_id', 'source', 'created_at', 'updated_at')

    def get_export_queryset(self, request):
        super().get_export_queryset(request)

    def get_export_data(self, file_format, queryset, *args, **kwargs):
        """
        Returns file_format representation for given queryset.
        """
        kwargs['from_date'] = kwargs.get('request').POST.get('from_date')
        kwargs['to_date'] = kwargs.get('request').POST.get('to_date')
        resource_class = self.get_export_resource_class()
        data = resource_class(**self.get_export_resource_kwargs(kwargs.get('request'))).export(queryset, *args, **kwargs)
        export_data = file_format.export_data(data)
        return export_data

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class InsuranceLeadForm(forms.ModelForm):
    start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder': 'Select a date'}))
    end_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder': 'Select a date'}))

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and start >= end:
            raise forms.ValidationError("Start Date should be less than end Date")


class InsuranceCancelMasterAdmin(admin.ModelAdmin):
    list_display = ['insurer', 'min_days', 'max_days', 'refund_percentage']


class EndorsementRequestForm(forms.ModelForm):

    status_choices = [(EndorsementRequest.PENDING, "Pending"), (EndorsementRequest.APPROVED, 'Approved'),
                      (EndorsementRequest.REJECT, "Reject")]
    status = forms.ChoiceField(choices=status_choices, required=True)
    # coi_choices = [("YES", "Yes"), ("NO", "No")]
    mail_coi_to_customer = forms.BooleanField(initial=False)
    reject_reason = forms.CharField(max_length=150, required=False)

    def clean(self):
        super().clean()
        data = self.cleaned_data
        status = data.get('status')
        coi_status = data.get('mail_coi_to_customer')
        reject_reason = data.get('reject_reason')
        if status == EndorsementRequest.PENDING and coi_status:
            raise forms.ValidationError('Without Approved COI can not be send to customer')
        if status == EndorsementRequest.REJECT and not reject_reason:
            raise forms.ValidationError('For Rejection, reject reason is mandatory')

    class Meta:
        fields = '__all__'


class InsuredMemberDocumentInline(admin.TabularInline):
    model = InsuredMemberDocument

    def member_name(self, obj):
        first_name = obj.member.first_name
        last_name = obj.member.last_name
        return first_name + " " + last_name

    fields = ('member_name', 'document_image',)
    extra = 0
    can_delete = False
    show_change_link = False
    can_add = False
    readonly_fields = ("member_name", 'document_image', )


class InsuredMemberDocumentAdmin(admin.ModelAdmin):
    list_display = ['member', 'document_image']


class EndorsementRequestAdmin(admin.ModelAdmin):

    def member_name(self, obj):
        first_name = obj.member.first_name
        last_name = obj.member.last_name
        return first_name + " " + last_name

    def insurance_id(self, obj):
        return obj.insurance.id

    def old_first_name(self, obj):
        if obj.first_name == obj.member.first_name:
            return ""
        else:
            return obj.member.first_name + "(edited)"
        # return obj.member.first_name
        # old_member_obj.first_name

    def old_last_name(self, obj):
        if obj.last_name == obj.member.last_name:
            return ""
        else:
            return obj.member.last_name + "(edited)"

    def old_dob(self, obj):
        if obj.dob.date() == obj.member.dob.date():
            return ""
        else:
            return obj.member.dob + "(edited)"

    def old_email(self, obj):
        if obj.email == obj.member.email:
            return ""
        else:
            return obj.member.email + "(edited)"

    def old_address(self, obj):
        if obj.address == obj.member.address:
            return ""
        else:
            return obj.member.address + "(edited)"

    def old_pincode(self, obj):
        if obj.pincode == obj.member.pincode:
            return ""
        else:
            obj.member.pincode + "(edited)"

    def old_gender(self, obj):
        if obj.gender == obj.member.gender:
            return ""
        else:
            return obj.member.gender + "(edited)"

    def old_relation(self, obj):
        if obj.relation == obj.member.relation:
            return ""
        else:
            return obj.member.relation + "(edited)"

    def old_town(self,obj):
        if obj.town == obj.member.town:
            return ""
        else:
            return obj.member.town + "(edited)"

    def old_district(self, obj):
        if obj.district == obj.member.district:
            return ""
        else:
            return obj.member.district + "(edited)"

    def old_state(self, obj):
        if obj.state == obj.member.state:
            return ""
        else:
            return obj.member.state + "(edited)"

    def old_middle_name(self, obj):
        if obj.middle_name == obj.member.middle_name:
            return ""
        else:
            return obj.member.middle_name + "(edited)"

    def old_title(self, obj):
        if obj.title == obj.member.title:
            return ""
        else:
            return obj.member.title + "(edited)"

    list_display = ['member_name', 'insurance_id']
    readonly_fields = ['member', 'insurance', 'member_type', 'title', 'old_title', 'first_name', 'old_first_name',
                       'middle_name', 'old_middle_name', 'last_name', 'old_last_name', 'dob', 'old_dob', 'email',
                       'old_email',  'address', 'old_address', 'pincode', 'old_pincode', 'gender', 'old_gender',
                       'phone_number', 'relation', 'old_relation', 'profile', 'town', 'old_town',
                       'district', 'old_district', 'state', 'old_state', 'state_code', 'city_code',
                       'district_code']
    inlines = [InsuredMemberDocumentInline]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @transaction.atomic()
    def save_model(self, request, obj, form, change):
        user = request.user
        obj._user = user if user and not user.is_anonymous else None

        if request.user.is_member_of(constants['SUPER_INSURANCE_GROUP']) or request.user.is_member_of(constants['INSURANCE_GROUP']):
            super().save_model(request, obj, form, change)

            if obj.status == EndorsementRequest.APPROVED:
                obj.process_endorsement()
            elif obj.status == EndorsementRequest.REJECT:
                obj.reject_endorsement()
            if obj.mail_coi_to_customer:
                obj.process_coi()


class InsuredMemberHistoryAdmin(admin.ModelAdmin):
    list_display = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number']
    readonly_fields = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number', 'relation', 'profile']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class InsuranceEligibleCitiesAdmin(admin.ModelAdmin):
    model = InsuranceEligibleCities


class ThirdPartyAdministratorResource(resources.ModelResource):
    class Meta:
        model = ThirdPartyAdministrator
        fields = ['id', 'name']


class ThirdPartyAdministratorAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = ThirdPartyAdministratorResource
    search_fields = ['name']
    list_display = ['id', 'name']
