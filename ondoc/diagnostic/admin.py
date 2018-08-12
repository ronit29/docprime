from django.contrib import admin
from .models import LabOnboardingToken, Lab, AvailableLabTest, LabTestPricingGroup, LabPricingGroup
from django_tables2 import RequestConfig
import django_tables2 as tables
from .forms import LabForm as LabTestPricingForm
from .tables import LabTestTable
from ondoc.crm.admin.lab import LabCityFilter
from django.shortcuts import render
from ondoc.crm.constants import constants
from django import forms
from decimal import Decimal
import math

class LabPricingForm(forms.ModelForm):
    pathology_agreed_price_percentage = forms.DecimalField(required=False, min_value=20,max_value=100)
    pathology_deal_price_percentage = forms.DecimalField(required=False, min_value=20, max_value=100)
    radiology_agreed_price_percentage = forms.DecimalField(required=False, min_value=20,max_value=100)
    radiology_deal_price_percentage = forms.DecimalField(required=False, min_value=20,max_value=100)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data;
        pap = data.get('pathology_agreed_price_percentage');
        pdp = data.get('pathology_deal_price_percentage');
        rap = data.get('radiology_agreed_price_percentage');
        rdp = data.get('radiology_deal_price_percentage');

        if(pdp and pap and pdp<pap):
            raise forms.ValidationError("Deal price percent cannot be less than agreed price percent")

        if(rdp and rap and rdp<rap):
            raise forms.ValidationError("Deal price percent cannot be less than agreed price percent")

class LabPricingGroupAdmin(admin.ModelAdmin):
    change_form_template = 'labtest.html'
    add_form_template = 'admin/change_form.html'
    form = LabPricingForm
    list_display = ('group_name', )
    search_fields = ['group_name', ]
    readonly_fields = ['pathology_deal_price_percentage','radiology_deal_price_percentage']

    # list_filter = ('data_status', 'onboarding_status',LabCityFilter)

    #def has_change_permission(self, request, obj=None):
    #    if super().has_change_permission(request, obj):
    #        return True
    #    return False    

    def save_model(self, request, obj, form, change):
        pap = obj.pathology_agreed_price_percentage
        rap = obj.radiology_agreed_price_percentage
        multiplier = Decimal(1.2)

        if pap:
            obj.pathology_deal_price_percentage = min(math.ceil(multiplier*pap),100.0)

        if rap:
            obj.radiology_deal_price_percentage = min(math.ceil(multiplier*rap),100.0)
        super().save_model(request, obj, form, change)


    def get_queryset(self, request):
        return LabPricingGroup.objects.all()

    def change_view(self, request, object_id=None, extra_context=None):
        if not object_id:
            return render(request, 'access_denied.html')

        existing = None
        existing = LabPricingGroup.objects.get(pk=object_id)
        if not existing:
            return render(request, 'access_denied.html')
        form = LabTestPricingForm(instance=existing, prefix="lab")
        table = LabTestTable(AvailableLabTest.objects.filter(lab_pricing_group=existing
                                                             ).prefetch_related('lab','test').order_by('-updated_at'))

        RequestConfig(request, paginate=False).configure(table)

        extra_context = {'labtesttable' :table,'form':form,'id':object_id,'request':request,'lab_group':existing}
        return super().change_view(request, object_id, extra_context=extra_context)

admin.site.register(LabOnboardingToken)
admin.site.register(LabPricingGroup, LabPricingGroupAdmin)