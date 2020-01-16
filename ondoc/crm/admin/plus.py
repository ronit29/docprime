from django.contrib import admin
from django import forms
from django.db.models import Count, Q
from django.db.models import F
from rest_framework import serializers
from dal import autocomplete
from ondoc.authentication.models import User
from ondoc.diagnostic.models import LabAppointment
from ondoc.doctor.models import OpdAppointment
from ondoc.plus.models import PlusProposer, PlusPlans, PlusThreshold, PlusUser, PlusPlanContent, PlusPlanParameters, \
    PlusPlanParametersMapping, PlusPlanUtmSources, PlusPlanUtmSourceMapping, PlusMembers
from import_export.admin import ImportExportMixin, ImportExportModelAdmin, base_formats
import nested_admin
from import_export import fields, resources
from datetime import datetime
from django.db import transaction
from django.conf import settings
from django.utils import timezone
from django.conf import settings
from datetime import timedelta


class PlusProposerAdmin(admin.ModelAdmin):
    model = PlusProposer
    display = ("name", "min_float", "logo", "website", "phone_number", "email", "address", "company_name",
               "intermediary_name", "intermediary_code", "intermediary_contact_number", "gstin_number", "signature",
               "is_live", "enabled", "plus_document, merchant_code")
    list_display = ('name', 'is_live')


class PlusPlanParametersAdmin(admin.ModelAdmin):
    model = PlusPlanParameters
    fields = ('key', 'details')
    list_display = ('key',)


class PlusPlanUtmSourceAdmin(admin.ModelAdmin):
    model = PlusPlanUtmSources
    fields = ('source', 'source_details', 'create_lead')
    list_display = ('source',)


class PlusPlanUtmSourceMappingInline(admin.TabularInline):
    model = PlusPlanUtmSourceMapping
    fields = ('plus_plan', 'utm_source')
    extra = 0


class PlusPlanParametersMappingInline(admin.TabularInline):
    model = PlusPlanParametersMapping
    fields = ('plus_plan', 'parameter', 'value')
    extra = 0


class PlusPlanContentInline(admin.TabularInline):
    model = PlusPlanContent
    fields = ('title', 'content')
    extra = 0


class PlusPlansForm(forms.ModelForm):
    is_corporate = forms.NullBooleanField(required=False)
    is_retail = forms.NullBooleanField(required=False)

    def clean(self):
        is_corporate = self.cleaned_data.get('is_corporate')
        is_retail = self.cleaned_data.get('is_retail')

        if (is_retail and is_corporate) or (self.instance.is_retail and is_corporate) or (is_corporate and self.instance.is_retail):
            raise forms.ValidationError(
                'Retail and Corporate plan can not be clubbed together')

    class Meta:
        fields = '__all__'


class PlusPlansAdmin(admin.ModelAdmin):
    form = PlusPlansForm
    model = PlusPlans
    inlines = [PlusPlanContentInline, PlusPlanParametersMappingInline, PlusPlanUtmSourceMappingInline]
    display = ("plan_name", "proposer", "internal_name", "mrp", "deal_price", "tenure", "enabled", "is_live",
               "total_allowed_members", "is_selected", "is_retail", "default_single_booking", "is_corporate",
               "corporate_group", "corporate_upper_limit_criteria", "corporate_doctor_upper_limit",
               "corporate_lab_upper_limit")
    list_display = ('plan_name', 'mrp', "deal_price", "is_gold", "is_selected", "default_single_booking")


class PlusThresholdAdmin(admin.ModelAdmin):
    model = PlusThreshold
    display = ("plus_plan", "opd_amount_limit", "lab_amount_limit", "package_amount_limit", "custom_validation", "enabled", "is_live",)
    list_display = ('plus_plan', 'opd_amount_limit', 'lab_amount_limit')


class PlusUserAdminForm(forms.ModelForm):
    status = forms.ChoiceField(choices=PlusUser.STATUS_CHOICES, required=True)

    def clean(self):
        status = self.cleaned_data.get('status')

        if status:
            status = int(status)

        if status == PlusUser.CANCELLED and self.instance.plan.is_corporate:
            raise forms.ValidationError('Corporate Plus User can not be Cancelled.')

    def clean_status(self):
        status = self.cleaned_data.get('status')

        if status:
            status = int(status)

        if status != self.instance.status:

            # if status == PlusUser.CANCELLED and  timezone.now() > self.instance.created_at + timedelta(days=settings.VIP_CANCELLATION_PERIOD):
            #     raise forms.ValidationError('Membership can only be cancelled within the period of %d days' % settings.VIP_CANCELLATION_PERIOD)

            if status != PlusUser.CANCELLED:
                raise forms.ValidationError('Membership can only be cancelled. Nothing else.')

            if self.instance.status == PlusUser.CANCELLED:
                raise forms.ValidationError('Membership is already cancelled. Cannot be changed now.')

            # if status == PlusUser.CANCELLED and status != self.instance.status:
            #     cancel_dict = self.instance.can_be_cancelled()
            #     if not cancel_dict.get('can_be_cancelled', False):
            #         raise forms.ValidationError(cancel_dict.get('reason'))

        return status


class PlusOpdAppointmentInline(admin.TabularInline):
    model = OpdAppointment
    fields = ('id', 'status', 'time_slot_start', 'doctor', 'matrix_lead_id')
    readonly_fields = fields
    can_delete = False
    extra = 0


class PlusLabAppointmentInline(admin.TabularInline):
    model = LabAppointment
    fields = ('id', 'status', 'time_slot_start', 'lab', 'matrix_lead_id')
    readonly_fields = fields
    can_delete = False
    extra = 0


class PlusUserAdmin(admin.ModelAdmin):
    form = PlusUserAdminForm
    model = PlusUser
    inlines = [PlusOpdAppointmentInline, PlusLabAppointmentInline]
    fields = ("user", "plan", "purchase_date", "expire_date", "status", "matrix_lead_id")
    readonly_fields = ("user", "plan", "purchase_date", "matrix_lead_id")
    list_display = ('user', 'purchase_date')


class PlusMemberAdmin(admin.ModelAdmin):
    model = PlusMembers
    fields = ("first_name", "last_name", "dob", "email", "relation", "pincode", "address", "gender", "phone_number",
              "profile", "title", "middle_name", "city", "district", "state", "state_code", "plus_user", "city_code",
              "district_code", "is_primary_user")
    readonly_fields = ("relation", "phone_number", "profile", "city", "district", "state", "state_code", "plus_user",
                       "city_code", "district_code", "is_primary_user")
    list_display = ("first_name", "last_name", "plus_user", "is_primary_user")


class PlusUserUploadAdmin(admin.ModelAdmin):
    list_display = ('id', 'file', 'amount', 'paid_through')

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('file',)
        return self.readonly_fields


class CorporateAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'address', 'corporate_group')


class CorporateGroupAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'type')