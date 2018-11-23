from django.contrib import admin
from rest_framework import serializers
from ondoc.api.v1.insurance.serializers import InsuranceTransactionSerializer, InsuredTransactionIdsSerializer


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

class UserInsuranceAdmin(admin.ModelAdmin):

    def user_policy_number(self, obj):
        return str(obj.insurance_transaction.policy_number)

    list_display = ['insurance_plan', 'user_policy_number', 'user']
    readonly_fields = ['insurance_plan', 'user', 'user_policy_number']

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