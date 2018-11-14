from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
import nested_admin
from ondoc.authentication.models import BillingAccount, SPOCDetails, DoctorNumber
from .forms import BillingAccountFormSet, BillingAccountForm, SPOCDetailsForm
from reversion.admin import VersionAdmin



class BillingAccountInline(GenericTabularInline, nested_admin.NestedTabularInline):
    form = BillingAccountForm
    formset = BillingAccountFormSet
    can_delete = False
    extra = 0
    model = BillingAccount
    show_change_link = False
    readonly_fields = ['merchant_id']
    fields = ['merchant_id', 'type', 'account_number', 'ifsc_code', 'pan_number', 'pan_copy', 'account_copy', 'enabled']


class SPOCDetailsInline(GenericTabularInline):
    can_delete = True
    extra = 0
    form = SPOCDetailsForm
    model = SPOCDetails
    show_change_link = False
    fields = ['name', 'std_code', 'number', 'email', 'details', 'contact_type']


class DoctorNumberAdmin(VersionAdmin):
    list_display = ('doctor', 'phone_number', 'updated_at')
    search_fields = ['phone_number', 'doctor']
    date_hierarchy = 'created_at'
    autocomplete_fields = ['doctor']

admin.site.register(DoctorNumber, DoctorNumberAdmin)
