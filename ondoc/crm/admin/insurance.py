from django.contrib import admin
from django.db import models
from ondoc.insurance.models import Insurer, InsurerFloat, InsurancePlans, InsuranceThreshold

class InsurerAdmin(admin.ModelAdmin):

    list_display = ['name', 'is_disabled', 'is_live']
    list_filter = ['name']


class InsurerFloatAdmin(admin.ModelAdmin):
    list_display = ['insurer']



class InsurancePlansAdmin(admin.ModelAdmin):

    list_display = ['insurer', 'type', 'amount']


class InsuranceThresholdAdmin(admin.ModelAdmin):

    list_display = ('insurer', 'insurance_plan')
