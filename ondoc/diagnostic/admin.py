from django.contrib import admin
from .models import LabOnboardingToken, Lab, AvailableLabTest, LabPricing
from django_tables2 import RequestConfig
import django_tables2 as tables
from .forms import LabForm as LabTestPricingForm
from .tables import LabTestTable
from ondoc.crm.admin.lab import LabCityFilter


class LabTestPricingAdmin(admin.ModelAdmin):
    change_form_template = 'labtest.html'
    list_display = ('name', 'updated_at','onboarding_status','data_status')
    list_filter = ('data_status', 'onboarding_status',LabCityFilter)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.groups.filter(name='lab_pricing_team').exists():
            return True
        return False    

    def get_queryset(self, request):
        return Lab.objects.all()

    def change_view(self, request, object_id=None, extra_context=None):
        if not object_id:
            return render(request, 'access_denied.html')

        existing = None
        existing = Lab.objects.get(pk=object_id)
        if not existing:
            return render(request, 'access_denied.html')
        form = LabTestPricingForm(instance=existing, prefix="lab")
        table = LabTestTable(AvailableLabTest.objects.filter(lab=object_id).prefetch_related('lab','test').order_by('-updated_at'))

        RequestConfig(request).configure(table)

        extra_context = {'labtesttable' :table,'form':form,'id':object_id,'request':request,'lab':existing}
        return super().change_view(request, object_id, extra_context=extra_context)

admin.site.register(LabOnboardingToken)
admin.site.register(LabPricing, LabTestPricingAdmin)