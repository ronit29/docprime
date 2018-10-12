from django.contrib import admin
from django.db import models
from ondoc.insurance.models import Insurer, InsurerFloat, InsurancePlans, InsuranceThreshold

class InsurerAdmin(admin.ModelAdmin):

    list_display = ['name', 'is_disabeld', 'is_live']
    list_filter = ['name']


class InsurerFloatAdmin(admin.ModelAdmin):
    list_display = ['insurer']



class InsurancePlansAdmin(admin.ModelAdmin):

    list_display = ['insurer', 'type', 'amount']


class InsuranceThresholdAdmin(admin.ModelAdmin):
    # query_set = Insurer.objects.all().first()
    # if query_set:
    #     name = query_set.name
    model = InsuranceThreshold
    list_display = ('insurer', 'insurance_plan')
