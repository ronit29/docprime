from django.contrib import admin
from django import forms
from rest_framework import serializers
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer
from ondoc.insurance.models import InsurancePlanContent, InsurancePlans, InsuredMembers, UserInsurance
from import_export.admin import ImportExportMixin, ImportExportModelAdmin, base_formats
import nested_admin
from import_export import fields, resources
from datetime import datetime


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

class InsurancePlansAdmin(admin.ModelAdmin):

    list_display = ['insurer', 'name', 'amount']
    inlines = [InsurancePlanContentInline]


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
    hypertension_diabetes = fields.Field()
    heart_diseases = fields.Field()
    liver_kidney_diseases = fields.Field()
    cancer = fields.Field()
    gynaecological_condition = fields.Field()
    other = fields.Field()
    illness_or_injury_in_last_6_month = fields.Field()
    customer_consent_recieved = fields.Field()

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
        export_order = ('id', 'purchase_date', 'title', 'first_name', 'middle_name', 'last_name', 'dob', 'gender', 'relation', 'email',
                        'phone_number', 'address', 'town', 'district', 'state', 'pincode')

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

    def dehydrate_hypertension_diabetes(self, insured_members):
        return ""

    def dehydrate_heart_diseases(self, insured_members):
        return ""

    def dehydrate_liver_kidney_diseases(self, insured_members):
        return ""

    def dehydrate_cancer(self, insured_members):
        return ""

    def dehydrate_gynaecological_condition(self, insured_members):
        return ""

    def dehydrate_other(self, insured_members):
        return ""

    def dehydrate_illness_or_injury_in_last_6_month(self, insured_members):
        return ""

    def dehydrate_customer_consent_recieved(self, insured_members):
        return ""


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


class UserInsuranceAdmin(admin.ModelAdmin):

    def user_policy_number(self, obj):
        return str(obj.policy_number)

    list_display = ['insurance_plan', 'user_policy_number', 'user']
    fields = ['insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount']
    readonly_fields = ('insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount',)
    inlines = [InsuredMembersInline]
    # form = UserInsuranceForm

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

# class InsurancePlanContentForm(forms.ModelForm):
#     content = forms.CharField(widget=forms.Textarea, required=False)
#     plan = forms.ModelChoiceField(queryset=InsurancePlans.objects.all(),widget=forms.Select)
#     title = forms.ChoiceField(choices=InsurancePlanContent.PossibleTitles.as_choices())
#
#     class Media:
#         extend=False
#         js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'insurance/js/init.js')
#         css = {'all':('insurance/css/style.css',)}


# class InsurancePlanContentAdmin(admin.ModelAdmin):
#     model = InsurancePlanContent
#     fields = ('plan', 'title', 'content')
#     list_display = ('plan', 'title',)
#
#