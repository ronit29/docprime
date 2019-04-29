from django.contrib import admin
from django import forms
from django.db.models import Count, Q
from django.db.models import F
from rest_framework import serializers
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer
from ondoc.crm.constants import constants
from ondoc.doctor.models import OpdAppointment, DoctorPracticeSpecialization, PracticeSpecialization, Hospital
from ondoc.diagnostic.models import LabAppointment, LabTest, Lab
from ondoc.insurance.models import InsurancePlanContent, InsurancePlans, InsuredMembers, UserInsurance, StateGSTCode, \
    InsuranceCity, InsuranceDistrict, InsuranceDeal, InsurerPolicyNumber, InsuranceLead
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
        if request.user.is_member_of(constants['INSURANCE_GROUP']):
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
        return str(appointment.time_slot_start.date())

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

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):

        request = kwargs.get('request')
        date_range = [datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]
        if request.user.is_member_of(constants['INSURANCE_GROUP']):
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
                        'name_of_tests', 'address_of_center', 'amount_to_be_paid', 'booking_date', 'status',
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
        return str(appointment.time_slot_start.date())

    def dehydrate_name_of_diagnostic_center(self, appointment):
        return str(appointment.lab.name)

    def dehydrate_provider_code_of_the_center(self, appointment):
        return str(appointment.lab.id)

    def dehydrate_name_of_tests(self, appointment):
        return ", ".join(list(map(lambda test: test.name, appointment.tests.all())))

    def dehydrate_address_of_center(self, appointment):
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
    matrix_lead = fields.Field()

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
                        'coi', 'matrix_lead')

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
        return str(insurance.purchase_date.date())

    def dehydrate_expiry_date(self, insurance):
        return str(insurance.expiry_date.date())

    def dehydrate_policy_number(self, insurance):
        return str(insurance.policy_number)

    def dehydrate_amount(self, insurance):
        return str(insurance.premium_amount)

    def dehydrate_receipt_number(self, insurance):
        return str(insurance.receipt_number)

    def dehydrate_coi(self, insurance):
        return str(insurance.coi)

    def dehydrate_matrix_lead(self, insurance):
        return str(insurance.matrix_lead_id)


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

    status_choices = [(UserInsurance.ACTIVE, "Active"), (UserInsurance.CANCELLED, "Cancelled"), (UserInsurance.ONHOLD, "Onhold")]
    status = forms.ChoiceField(choices=status_choices, required=True)
    onhold_reason = forms.CharField(max_length=400, required=False)

    def clean(self):
        super().clean()
        data = self.cleaned_data
        status = data.get('status')
        onhold_reason = data.get('onhold_reason')
        if int(status) == UserInsurance.ONHOLD:
            if not onhold_reason:
                raise forms.ValidationError("In Case of ONHOLD status, Onhold reason is mandatory")
        elif int(status) == UserInsurance.CANCELLED:
            insured_opd_completed_app_count = OpdAppointment.get_insured_completed_appointment(self.instance)
            insured_lab_completed_app_count = LabAppointment.get_insured_completed_appointment(self.instance)
            if insured_lab_completed_app_count > 0:
                raise forms.ValidationError('Lab appointment with insurance have been completed, '
                                            'Cancellation could not proceed')
            if insured_opd_completed_app_count > 0:
                raise forms.ValidationError('OPD appointment with insurance have been completed, '
                                            'Cancellation could not proceed')

    class Meta:
        fields = '__all__'


class UserInsuranceAdmin(ImportExportMixin, admin.ModelAdmin):
    resource_class = (UserInsuranceDoctorResource, UserInsuranceLabResource, UserInsuranceResource)
    export_template_name = "export_insurance_report.html"
    formats = (base_formats.XLS,)
    model = UserInsurance

    def user_policy_number(self, obj):
        return str(obj.policy_number)

    def user_name(self, obj):
        from ondoc.authentication.models import UserProfile
        user_profile = UserProfile.objects.filter(user=obj.user).first()
        return str(user_profile.name)

    # def city_name(self, obj):
    #     cities = InsuranceCity.objects.all().values_list('name', flat=True)
    #     return cities

    list_display = ['id', 'insurance_plan', 'user_name', 'user', 'policy_number', 'purchase_date','merchant_payout']
    fields = ['insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount', 'merchant_payout', 'status', 'onhold_reason']
    readonly_fields = ('insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount', 'merchant_payout')
    inlines = [InsuredMembersInline]
    form = UserInsuranceForm

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
        print('data is here')
        # if request.user.is_member_of(constants['INSURANCE_GROUP']):
        if obj.status == UserInsurance.ACTIVE:
            super(UserInsuranceAdmin, self).save_model(request, obj, form, change)
        elif obj.status == UserInsurance.ONHOLD:
            if obj.onhold_reason:
                super(UserInsuranceAdmin, self).save_model(request, obj, form, change)
        elif obj.status == UserInsurance.CANCELLED:
            response = obj.process_cancellation()
            if response.get('success', None):
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


class InsurerPolicyNumberAdmin(admin.ModelAdmin):
    model = InsurerPolicyNumber
    fields = ('insurer', 'insurer_policy_number')
    list_display = ('insurer', 'insurer_policy_number', 'created_at')


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
        else:
            return ""

    def dehydrate_phone_number(self, obj):
        return str(obj.user.phone_number)

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

    def name(self, obj):
        user = obj.user
        from ondoc.authentication.models import UserProfile
        user_profile = UserProfile.objects.filter(user=user, is_default_user=True).first()
        if user_profile:
            return str(user_profile.name)
        else:
            return ""

    def phone_number(self, obj):
        return str(obj.user.phone_number)

    def status(self, obj):
        user_insurance = UserInsurance.objects.filter(user=obj.user).order_by('-id').first()
        if user_insurance:
            return "Booked"
        else:
            return "New"

    list_display = ('id', 'name',  'phone_number', 'status', 'matrix_lead_id', 'created_at', 'updated_at')

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
