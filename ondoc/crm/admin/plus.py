from django.contrib import admin
from django import forms
from django.db.models import Count, Q
from django.db.models import F
from rest_framework import serializers
from dal import autocomplete
from ondoc.authentication.models import User
from ondoc.plus.models import PlusProposer, PlusPlans, PlusThreshold, PlusUser, PlusPlanContent, PlusPlanParameters, \
    PlusPlanParametersMapping, PlusPlanUtmSources, PlusPlanUtmSourceMapping
from import_export.admin import ImportExportMixin, ImportExportModelAdmin, base_formats
import nested_admin
from import_export import fields, resources
from datetime import datetime
from django.db import transaction
from django.conf import settings


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
    fields = ('source', 'source_details')
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


class PlusPlansAdmin(admin.ModelAdmin):
    model = PlusPlans
    inlines = [PlusPlanContentInline, PlusPlanParametersMappingInline, PlusPlanUtmSourceMappingInline]
    display = ("plan_name", "proposer", "internal_name", "mrp", "deal_price", "tenure", "enabled", "is_live", "total_allowed_members", "is_selected", )
    list_display = ('plan_name', 'proposer', 'mrp', "deal_price")


class PlusThresholdAdmin(admin.ModelAdmin):
    model = PlusThreshold
    display = ("plus_plan", "opd_amount_limit", "lab_amount_limit", "package_amount_limit", "custom_validation", "enabled", "is_live",)
    list_display = ('plus_plan', 'opd_amount_limit', 'lab_amount_limit')


class PlusUserAdmin(admin.ModelAdmin):
    model = PlusUser
    display = ("user", "plan", "purchase_date", "expire_date", "status", "matrix_lead_id")
    readonly_fields = ("user", "plan", "purchase_date", "expire_date", "status", "matrix_lead_id")
    list_display = ('user', 'purchase_date')
