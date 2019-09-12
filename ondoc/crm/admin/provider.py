from dal import autocomplete
from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from django.utils.safestring import mark_safe
from import_export import fields, resources

from ondoc.provider import models as prov_models
from ondoc.diagnostic import models as diag_models
from django import forms
from django.db.models import Q
from django.conf import settings
from ondoc.api.v1 import utils as v1_utils
from import_export.admin import ImportExportMixin, base_formats
import logging
logger = logging.getLogger(__name__)


class AvailableLabTestAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return diag_models.AvailableLabTest.objects.none()
        queryset = diag_models.AvailableLabTest.objects.filter(is_b2b=True)
        if self.q:
            queryset = queryset.filter(Q(test__name__istartswith=self.q) | Q(lab_pricing_group__group_name__istartswith=self.q))
        return queryset.distinct()


class PartnerLabTestSampleDetailForm(forms.ModelForm):

    class Meta:
        model = prov_models.PartnerLabTestSampleDetails
        fields = ('__all__')
        widgets = {
            'available_lab_test': autocomplete.ModelSelect2(url='available-lab-test-autocomplete', forward=[]),
        }


class PartnerLabTestSampleDetailAdmin(admin.ModelAdmin):
    list_display = ('id', 'available_lab_test', 'sample')
    autocomplete_fields = ['sample']

    readonly_fields = []

    form = PartnerLabTestSampleDetailForm


class PartnerLabTestSampleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'created_at', 'updated_at')
    readonly_fields = []
    search_fields = ['name']


class TestSamplesLabAlertAdmin(admin.ModelAdmin):
    list_display = ('name', )


class ReportsInline(admin.TabularInline):
    model = prov_models.PartnerLabTestSamplesOrderReportMapping
    extra = 0
    can_delete = True
    verbose_name = "Report"
    verbose_name_plural = "Reports"
    readonly_fields = []
    fields = ['report']
    autocomplete_fields = []


class PartnerLabSamplesCollectOrderAdmin(admin.ModelAdmin):

    list_display = ('id', 'offline_patient', 'hospital', 'doctor', 'lab')
    readonly_fields = ['offline_patient', 'patient_details', 'hospital', 'doctor', 'lab', 'available_lab_tests',
                       'collection_datetime', 'samples', 'selected_tests_details', 'lab_alerts']
    search_fields = ['offline_patient']
    inlines = [
        ReportsInline,
    ]

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
