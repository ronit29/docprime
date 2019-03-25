from django.contrib import admin
from django import forms
from django.db.models import Count, Q
from django.db.models import F
from rest_framework import serializers
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer
from ondoc.doctor.models import OpdAppointment
from ondoc.diagnostic.models import LabAppointment
from ondoc.insurance.models import InsurancePlanContent, InsurancePlans, InsuredMembers, UserInsurance, StateGSTCode, \
    InsuranceCity, InsuranceDistrict
from import_export.admin import ImportExportMixin, ImportExportModelAdmin, base_formats
import nested_admin
from import_export import fields, resources
from datetime import datetime
from ondoc.insurance.models import InsuranceDisease
from django.conf import settings


class InsurerAdmin(admin.ModelAdmin):

    list_display = ['name', 'enabled', 'is_live']
    list_filter = ['name']


class InsurerFloatAdmin(admin.ModelAdmin):
    list_display = ['insurer']


class InsurancePlanContentInline(admin.TabularInline):
    model = InsurancePlanContent
    fields = ('title', 'content')
    extra = 0
    # can_delete = False
    # show_change_link = False
    # can_add = False
    # readonly_fields = ("first_name", 'last_name', 'relation', 'dob', 'gender', )


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


class InsurancePlansAdmin(admin.ModelAdmin):

    list_display = ['insurer', 'name', 'amount', 'is_selected']
    inlines = [InsurancePlanContentInline]
    form = InsurancePlanAdminForm


class InsuranceThresholdAdmin(admin.ModelAdmin):

    list_display = ['insurance_plan']


# class InsuranceTransaction

class InsuredMembersInline(admin.TabularInline):
    model = InsuredMembers
    fields = ('first_name', 'last_name', 'relation', 'dob', 'gender',)
    extra = 0
    can_delete = False
    show_change_link = False
    can_add = False
    readonly_fields = ("first_name", 'last_name', 'relation', 'dob', 'gender', )


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
        date_range = [datetime.strptime(kwargs.get('from_date'), '%d-%m-%Y').date(), datetime.strptime(kwargs.get('to_date'), '%d-%m-%Y').date()]
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

        return settings.BASE_URL + insured_members.user_insurance.coi.url if insured_members.user_insurance.coi is not None and \
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

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):

        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]

        appointment = OpdAppointment.objects.filter(created_at__date__range=date_range, status=OpdAppointment.COMPLETED, insurance__isnull=False ).prefetch_related(
                                                'insurance')
        return appointment

    class Meta:
        model = UserInsurance
        fields = ()
        export_order = ('policy_number', 'member_id', 'name', 'relationship_with_proposer', 'date_of_consultation',
                        'name_of_doctor', 'provider_code_of_doctor', 'speciality_of_doctor', 'diagnosis',
                        'icd_code_of_diagnosis', 'name_of_clinic', 'address_of_clinic', 'pan_card_of_clinic',
                        'existing_condition', 'amount_to_be_paid', 'bank_detail_of_center', 'gst_number_of_center')

    def get_insured_member(self, profile):
        insured_member = InsuredMembers.objects.filter(profile_id=profile).first()
        if insured_member:
            return insured_member
        else:
            return None

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
        return str(appointment.time_slot_start.date())

    def dehydrate_name_of_doctor(self, appointment):
        return str(appointment.doctor.name)

    def dehydrate_provider_code_of_doctor(self, appointment):
        return ""

    def dehydrate_speciality_of_doctor(self, appointment):
        return str(appointment.doctor.speciality)
        # return ""
    def dehydrate_diagnosis(self, appointment):
        return ""

    def dehydrate_icd_code_of_diagnosis(self, appointment):
        return ""

    def dehydrate_name_of_clinic(self, appointment):
        return ""

    def dehydrate_address_of_clinic(self, appointment):
        return ""

    def dehydrate_existing_condition(self, appointment):
        return ""

    def dehydrate_amount_to_be_paid(self, appointment):
        return ""

    def dehydrate_bank_detail_of_center(self, appointment):
        return ""

    def dehydrate_gst_number_of_center(self, appointment):
        return ""

class UserInsuranceLabResource(resources.ModelResource):
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

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):

        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]

        appointment = LabAppointment.objects.filter(created_at__date__range=date_range, status=LabAppointment.COMPLETED, insurance__isnull=False).prefetch_related(
                                                'insurance')
        return appointment

    class Meta:
        model = UserInsurance
        fields = ()
        export_order = ('policy_number', 'member_id', 'name', 'relationship_with_proposer', 'date_of_consultation',
                        'name_of_diagnostic_center', 'provider_code_of_the_center', 'name_of_tests', 'address_of_center',
                        'pan_card_of_center', 'existing_condition', 'amount_to_be_paid', 'bank_detail_of_center',
                        'gst_number_of_center')

    def get_insured_member(self, profile):
        insured_member = InsuredMembers.objects.filter(profile_id=profile).first()
        if insured_member:
            return insured_member
        else:
            return None

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
        return str(appointment.time_slot_start.date())

    def dehydrate_name_of_diagnostic_center(self, appointment):
        return str(appointment.lab.name)

    def dehydrate_provider_code_of_the_center(self, appointment):
        return ""

    def dehydrate_name_of_tests(self, appointment):
        # return str(appointment.doctor.speciality)
        return ""
    def dehydrate_address_of_center(self, appointment):
        return ""

    def dehydrate_pan_card_of_center(self, appointment):
        return ""

    def dehydrate_existing_condition(self, appointment):
        return ""

    def dehydrate_amount_to_be_paid(self, appointment):
        return ""

    def dehydrate_bank_detail_of_center(self, appointment):
        return ""

    def dehydrate_gst_number_of_center(self, appointment):
        return ""



class UserInsuranceAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = (UserInsuranceDoctorResource, UserInsuranceLabResource)
    export_template_name = "export_insurance_report.html"
    formats = (base_formats.XLS,)
    model = UserInsurance

    def user_policy_number(self, obj):
        return str(obj.policy_number)

    list_display = ['insurance_plan', 'user_policy_number', 'user']
    fields = ['insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount']
    readonly_fields = ('insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount',)
    inlines = [InsuredMembersInline]
    # form = UserInsuranceForm

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
        resource_class = self.get_export_resource_class()
        # data = resource_class(**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        if kwargs['appointment_type'] == 'Doctor':
            data = resource_class[0](**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)
        else:
            data = resource_class[1](**self.get_export_resource_kwargs(request)).export(queryset, *args, **kwargs)

        export_data = file_format.export_data(data)
        return export_data

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class CustomDateInput(forms.DateInput):
    input_type = 'date'


class UserInsuranceForm(forms.ModelForm):
    start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder': 'Select a date'}))
    end_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder': 'Select a date'}))

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        if start and end and start >= end:
            raise forms.ValidationError("Start Date should be less than end Date")


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
