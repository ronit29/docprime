from django.contrib import admin
from .models import LabOnboardingToken, Lab, AvailableLabTest, LabTestPricingGroup, LabPricingGroup
from django_tables2 import RequestConfig
import django_tables2 as tables
from .forms import LabForm as LabTestPricingForm
from .tables import LabTestTable
from ondoc.crm.admin.lab import LabCityFilter
from django.shortcuts import render
from ondoc.crm.constants import constants


class LabPricingGroupAdmin(admin.ModelAdmin):
    change_form_template = 'labtest.html'
    add_form_template = 'admin/change_form.html'
    list_display = ('group_name', )
    search_fields = ['group_name', ]
    # list_filter = ('data_status', 'onboarding_status',LabCityFilter)

    #def has_change_permission(self, request, obj=None):
    #    if super().has_change_permission(request, obj):
    #        return True
    #    return False    

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

        RequestConfig(request).configure(table)

        extra_context = {'labtesttable' :table,'form':form,'id':object_id,'request':request,'lab_group':existing}
        return super().change_view(request, object_id, extra_context=extra_context)

admin.site.register(LabOnboardingToken)
admin.site.register(LabPricingGroup, LabPricingGroupAdmin)