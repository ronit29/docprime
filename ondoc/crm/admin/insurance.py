from django.contrib import admin
from django import forms
from rest_framework import serializers
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer
from ondoc.insurance.models import InsurancePlanContent, InsurancePlans, InsuredMembers, UserInsurance
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
import nested_admin
from import_export import fields, resources


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

    def export(self, queryset=None):
        queryset = self.get_queryset()
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self):
        return InsuredMembers.objects.all().prefetch_related('user_insurance')

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


class InsuredMembersAdmin(ImportExportMixin, nested_admin.NestedModelAdmin):
    resource_class = InsuredMemberResource
    list_display = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number']
    readonly_fields = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number', 'relation', 'profile']

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