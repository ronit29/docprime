from dal import autocomplete
from django.contrib import admin
from django import forms
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.tmp_storages import MediaStorage
from import_export import widgets
from ondoc.provider import models as prov_models
from ondoc.diagnostic import models as diag_models
from ondoc.notification import tasks as notification_tasks
from ondoc.notification.models import NotificationAction
from django.db.models import Q
import logging
import json
logger = logging.getLogger(__name__)


class JSONWidget(widgets.Widget):
    """
    Widget for a JSON object (especially required for jsonb fields in PostgreSQL database.)
    :param value: Defaults to JSON format.
    The widget covers two cases: Proper JSON string with double quotes, else it
    tries to use single quotes and then convert it to proper JSON.
    """

    def clean(self, value, row=None, *args, **kwargs):
        val = super().clean(value)
        if val:
            try:
                return json.loads(val)
            except json.decoder.JSONDecodeError:
                return json.loads(val.replace("'", "\""))

    def render(self, value, obj=None):
        if value:
            return json.dumps(value)


class AvailableLabTestAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return diag_models.AvailableLabTest.objects.none()
        queryset = diag_models.AvailableLabTest.objects.filter(enabled=True, lab_pricing_group__labs__is_b2b=True)
        if self.q:
            queryset = queryset.filter(Q(test__name__istartswith=self.q) | Q(lab_pricing_group__group_name__istartswith=self.q))
        return queryset.distinct()


class PartnerLabTestSampleDetailForm(forms.ModelForm):

    class Meta:
        model = prov_models.PartnerLabTestSampleDetails
        fields = ('sample', 'available_lab_test', 'volume', 'volume_unit', 'is_fasting_required', 'report_tat', 'reference_value', 'material_required', 'instructions')
        widgets = {
            'available_lab_test': autocomplete.ModelSelect2(url='available-lab-test-autocomplete', forward=[]),
        }


class PartnerLabTestSampleDetailResource(resources.ModelResource):
    tmp_storage_class = MediaStorage
    sample_id = fields.Field(column_name='sample_id',
                             attribute='sample',
                             widget=widgets.ForeignKeyWidget(prov_models.PartnerLabTestSamples))

    available_lab_test_id = fields.Field(column_name='available_lab_test_id',
                                         attribute='available_lab_test',
                                         widget=widgets.ForeignKeyWidget(diag_models.AvailableLabTest))

    material_required = fields.Field(column_name='material_required',
                                     attribute='material_required',
                                     widget=JSONWidget())

    class Meta:
        model = prov_models.PartnerLabTestSampleDetails
        fields = ('id', 'sample_id', 'available_lab_test_id', 'volume', 'volume_unit', 'is_fasting_required',
                  'report_tat', 'reference_value', 'material_required', 'instructions')


class PartnerLabTestSampleDetailAdmin(ImportExportModelAdmin):
    resource_class = PartnerLabTestSampleDetailResource
    list_display = ('id', 'available_lab_test', 'sample')
    autocomplete_fields = ['sample']
    readonly_fields = []
    form = PartnerLabTestSampleDetailForm


class PartnerLabTestSampleResource(resources.ModelResource):
    tmp_storage_class = MediaStorage

    class Meta:
        model = prov_models.PartnerLabTestSamples
        fields = ('id', 'name', 'code')


class PartnerLabTestSampleAdmin(ImportExportModelAdmin):
    resource_class = PartnerLabTestSampleResource
    list_display = ('id', 'name', 'code', 'created_at', 'updated_at')
    readonly_fields = []
    search_fields = ['name']


class TestSamplesLabAlertAdmin(admin.ModelAdmin):
    list_display = ('name', )


class ReportsInlineFormset(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if self.instance.status in [prov_models.PartnerLabSamplesCollectOrder.PARTIAL_REPORT_GENERATED,
                                    prov_models.PartnerLabSamplesCollectOrder.REPORT_GENERATED,
                                    prov_models.PartnerLabSamplesCollectOrder.REPORT_VIEWED] and \
                (not self.cleaned_data or len(self.cleaned_data) == len(self.deleted_forms)):
            raise forms.ValidationError("Report file required.")
        if self.instance.status < self.instance.PARTIAL_REPORT_GENERATED and self.cleaned_data:
            raise forms.ValidationError("Reports can't be uploaded for present status")


class ReportsInline(admin.TabularInline):
    model = prov_models.PartnerLabTestSamplesOrderReportMapping
    extra = 0
    can_delete = True
    verbose_name = "Report"
    verbose_name_plural = "Reports"
    readonly_fields = []
    fields = ['report']
    autocomplete_fields = []
    formset = ReportsInlineFormset


class PartnerLabSamplesCollectOrderForm(forms.ModelForm):

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        if 'status' in self.changed_data and not self.instance.status_update_checks(cleaned_data['status']):
            raise forms.ValidationError("Incorrect Status Update")
        return cleaned_data


class PartnerLabSamplesCollectOrderAdmin(admin.ModelAdmin):

    list_display = ('id', 'offline_patient', 'hospital', 'doctor', 'lab')
    readonly_fields = ['offline_patient', 'patient_details', 'hospital', 'doctor', 'lab', 'available_lab_tests',
                       'collection_datetime', 'samples', 'selected_tests_details', 'lab_alerts']
    search_fields = ['offline_patient']
    inlines = [
        ReportsInline,
    ]
    form = PartnerLabSamplesCollectOrderForm

    def get_queryset(self, request):
        return super(PartnerLabSamplesCollectOrderAdmin, self).get_queryset(request)\
                                                              .prefetch_related('available_lab_tests__lab_pricing_group',
                                                                                'available_lab_tests__lab_pricing_group__labs',
                                                                                'available_lab_tests__test')

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_related(self, request, form, formsets, change):
        super(type(self), self).save_related(request, form, formsets, change)
        report_list = list()
        for formset in formsets:
            if isinstance(formset, ReportsInlineFormset):
                report_list = [(request.build_absolute_uri(report_mapping.report.url)) for report_mapping in formset.instance.reports.all()]
        if form.cleaned_data.get('status') in [prov_models.PartnerLabSamplesCollectOrder.PARTIAL_REPORT_GENERATED,
                                               prov_models.PartnerLabSamplesCollectOrder.REPORT_GENERATED]:
            notification_tasks.send_partner_lab_notifications.apply_async(kwargs={'order_id': form.instance.id,
                                                                                  'notification_type': NotificationAction.PARTNER_LAB_REPORT_UPLOADED,
                                                                                  'report_list': report_list},
                                                                          countdown=3)
