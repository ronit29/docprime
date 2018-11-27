from django.contrib import admin
from django import forms
from rest_framework import serializers
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer
from ondoc.insurance.models import InsurancePlanContent, InsurancePlans, InsuredMembers


class InsurerAdmin(admin.ModelAdmin):

    list_display = ['name', 'enabled', 'is_live']
    list_filter = ['name']


class InsurerFloatAdmin(admin.ModelAdmin):
    list_display = ['insurer']


class InsurancePlansAdmin(admin.ModelAdmin):

    list_display = ['insurer', 'name', 'amount']


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


class UserInsuranceAdmin(admin.ModelAdmin):

    def user_policy_number(self, obj):
        return str(obj.policy_number)

    list_display = ['insurance_plan', 'user_policy_number', 'user']
    fields = ['insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount']
    readonly_fields = ('insurance_plan', 'user', 'purchase_date', 'expiry_date', 'policy_number', 'premium_amount',)
    inlines = [InsuredMembersInline]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class InsuredMembersAdmin(admin.ModelAdmin):

    list_display = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number']
    readonly_fields = ['first_name', 'last_name', 'dob', 'email', 'address', 'pincode', 'gender', 'phone_number', 'relation', 'profile']

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class InsurancePlanContentForm(forms.ModelForm):
    content = forms.CharField(widget=forms.Textarea, required=False)
    plan = forms.ModelChoiceField(queryset=InsurancePlans.objects.all(),widget=forms.Select)
    title = forms.ChoiceField(choices=InsurancePlanContent.PossibleTitles.as_choices())

    class Media:
        extend=False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'insurance/js/init.js')
        css = {'all':('insurance/css/style.css',)}


class InsurancePlanContentAdmin(admin.ModelAdmin):
    form = InsurancePlanContentForm
    model = InsurancePlanContent
    list_display = ('plan', 'title',)

