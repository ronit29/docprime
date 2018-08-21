from django.contrib import admin
from django.contrib.contenttypes.admin import GenericTabularInline
import nested_admin
from ondoc.authentication.models import BillingAccount

from .forms import BillingAccountFormSet, BillingAccountForm
# Register your models here.

class BillingAccountInline(GenericTabularInline, nested_admin.NestedTabularInline):
    form = BillingAccountForm
    formset = BillingAccountFormSet
    can_delete = False
    extra = 0
    model = BillingAccount
    show_change_link = False
    readonly_fields = ['merchant_id']
    fields = ['merchant_id', 'type', 'account_number', 'ifsc_code','pan_number','pan_copy','account_copy', 'enabled']