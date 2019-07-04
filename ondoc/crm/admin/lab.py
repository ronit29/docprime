import re

from django.shortcuts import render, HttpResponse, HttpResponseRedirect, redirect
from django.conf.urls import url
from django.conf import settings
import datetime
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats
from django.utils.safestring import mark_safe
from django.contrib.gis import forms
from django.contrib.gis import admin
from django.contrib.admin import SimpleListFilter, TabularInline
from reversion.admin import VersionAdmin
from import_export.admin import ImportExportMixin
from django.db.models import Q, Count
from django.db import models, transaction
from django.utils.dateparse import parse_datetime
from dateutil import tz
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.html import format_html_join
import pytz
from django.contrib import messages
from ondoc.account.models import Order, Invoice
from ondoc.api.v1.utils import util_absolute_url, util_file_name, datetime_to_formated_string
from ondoc.common.models import AppointmentHistory
from ondoc.doctor.models import Hospital, CancellationReason
from ondoc.diagnostic.models import (LabTiming, LabImage,
                                     LabManager, LabAccreditation, LabAward, LabCertification, AvailableLabTest,
                                     LabNetwork, Lab, LabOnboardingToken, LabService, LabDoctorAvailability,
                                     LabDoctor, LabDocument, LabTest, DiagnosticConditionLabTest, LabNetworkDocument,
                                     LabAppointment, HomePickupCharges,
                                     TestParameter, ParameterLabTest, FrequentlyAddedTogetherTests, QuestionAnswer,
                                     LabReport, LabReportFile, LabTestCategoryMapping,
                                     LabTestRecommendedCategoryMapping, LabTestGroupTiming, LabTestGroupMapping,
                                     TestParameterChat, LabTestThresholds)
from ondoc.integrations.models import IntegratorHistory
from ondoc.notification.models import EmailNotification, NotificationAction
from ondoc.prescription.models import AppointmentPrescription
from .common import *
from ondoc.authentication.models import GenericAdmin, User, QCModel, GenericLabAdmin, AssociatedMerchant
from ondoc.crm.admin.doctor import CustomDateInput, TimePickerWidget, CreatedByFilter, AutoComplete, \
    RefundableAppointmentForm
from ondoc.crm.admin.autocomplete import PackageAutoCompleteView
from django.contrib.contenttypes.admin import GenericTabularInline
from ondoc.authentication import forms as auth_forms
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
import logging
import nested_admin
from .common import AssociatedMerchantInline, RemarkInline
from ondoc.location.models import EntityUrls
logger = logging.getLogger(__name__)


class LabTestResource(resources.ModelResource):
    excel_id = fields.Field(attribute='excel_id', column_name='Test ID')
    test_type = fields.Field(attribute='test_type', column_name='Test Type')
    sample_type = fields.Field(attribute='sample_type', column_name='Test SubType')
    #sub_type = fields.Field(attribute='sub_type', column_name='Test SubType')
    name = fields.Field(attribute='name', column_name="Test Name")
    is_package = fields.Field(attribute="is_package", column_name="Package (Y/N)", default="")
    why = fields.Field(attribute='why', column_name="Why This Test")
    pre_test_info = fields.Field(attribute='pre_test_info', column_name="Pre-Test Information")
    preferred_time = fields.Field(attribute='preferred_time', column_name="Preferred Time of day")
    sample_amount = fields.Field(attribute='sample_amount', column_name="Amount of Sample")
    expected_tat = fields.Field(attribute='expected_tat', column_name="Expected TAT")
    sample_collection_instructions = fields.Field(attribute='sample_collection_instructions',
                                                  column_name="How to Collect Sample")
    sample_handling_instructions = fields.Field(attribute='sample_handling_instructions',
                                                column_name="Sample handling before pickup")
    category = fields.Field(attribute='category', column_name='Category')
    home_collection_possible = fields.Field(attribute='home_collection_possible', column_name='Home Collection')
    class Meta:
        model = LabTest
        import_id_fields = ('excel_id',)

    def before_save_instance(self, instance, using_transactions, dry_run):
        instance.test_type = (LabTest.RADIOLOGY if instance.test_type.strip().lower() == 'radiology'
                              else LabTest.PATHOLOGY if instance.test_type.strip().lower() == 'pathology'
                              else None) if instance.test_type else None
        instance.is_package = (True if instance.is_package.strip().lower() == "yes" else False) if instance.is_package else False
        instance.excel_id = instance.excel_id.strip() if instance.excel_id else ""
        instance.sample_type = instance.sample_type.strip().lower() if instance.sample_type else ""
        instance.name = instance.name.strip() if instance.name else ""
        instance.why = instance.why.strip() if instance.why else ""
        instance.pre_test_info = instance.pre_test_info.strip() if instance.pre_test_info else ""
        instance.preferred_time = instance.preferred_time.strip() if instance.preferred_time else ""
        instance.sample_amount = str(instance.sample_amount).strip() if instance.sample_amount else ""
        instance.expected_tat = instance.expected_tat.strip() if instance.expected_tat else ""
        instance.category = instance.category.strip().upper() if instance.category else ""
        instance.sample_handling_instructions = (instance.sample_handling_instructions.strip()
                                                 if instance.sample_handling_instructions else "")
        instance.sample_collection_instructions = (instance.sample_collection_instructions.strip()
                                                   if instance.sample_collection_instructions else "")
        instance.home_collection_possible = (True if instance.home_collection_possible.strip().lower() == "yes" else False) if instance.home_collection_possible else False
        super().before_save_instance(instance, using_transactions, dry_run)

    # def after_save_instance(self, instance, using_transactions, dry_run):
    #     sub_type = instance.sub_type.strip().split(",")
    #     for sub_type_name in sub_type:
    #         obj, created = LabTestSubType.objects.get_or_create(name=sub_type_name.strip())
    #         LabTestSubTypeMapping.objects.get_or_create(lab_test=instance,
    #                                                     test_sub_type=obj)


class LabTimingForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end and start>=end:
            raise forms.ValidationError("Start time should be less than end time")


class LabTimingInline(admin.TabularInline):
    model = LabTiming
    form = LabTimingForm
    extra = 0
    can_delete = True
    show_change_link = False

# class LabImageForm(forms.ModelForm):
#     name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))

class LabImageInline(admin.TabularInline):
    model = LabImage
    # form = LabImageForm
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 3


class LabManagerFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if self.instance.data_status == QCModel.QC_APPROVED and not self.cleaned_data:
            self.instance.is_enable = False
            raise forms.ValidationError("Atleast one Lab Manager required for QC APPROVED or Enable for Online Booking")
        phone_no_flag = False
        if self.cleaned_data and self.instance.network_type == 1:
            for data in self.cleaned_data:
                number_pattern = re.compile("(0/91)?[6-9][0-9]{9}")
                if data.get('number') and number_pattern.match(str(data.get('number'))):
                    phone_no_flag = True
            if phone_no_flag == False:
                raise forms.ValidationError("Atleast one mobile no is required for SPOC Details")


class LabManagerInline(admin.TabularInline):
    model = LabManager
    formset = LabManagerFormSet
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    extra = 0
    can_delete = True
    show_change_link = False


class LabAccreditationInline(admin.TabularInline):
    model = LabAccreditation
    extra = 0
    can_delete = True
    show_change_link = False


class LabAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class LabAwardInline(admin.TabularInline):
    model = LabAward
    form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class LabServiceInline(admin.TabularInline):
    model = LabService
    #form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class LabDoctorInline(admin.TabularInline):
    model = LabDoctor
    # form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False

# class LabDocumentForm(forms.ModelForm):
#     name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))


class DistancePickerWidget(forms.TextInput):

    def render(self, name, value, attrs=None):
        htmlString = u''
        htmlString += u'<div><select name="%s">' % (name)
        instance = 0
        if value:
            instance = int(value)

        for i in range(1, 100):
            if i == instance:
                htmlString += ('<option selected value="%d">%d KM</option>' % (i, i))
            else:
                htmlString += ('<option value="%d">%d KM</option>' % (i, i))

        htmlString +='</select></div>'
        return mark_safe(u''.join(htmlString))


class HomePickupChargesForm(forms.ModelForm):
    distance = forms.CharField(widget=DistancePickerWidget())


class HomePickupChargesFormSet(BaseGenericInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        count = 0
        charge_list = []
        for value in self.cleaned_data:
            count += 1
            if value.get('distance') and value.get('home_pickup_charges'):
                charge_list.append((value.get('home_pickup_charges'), int(value.get('distance'))))
        if charge_list:
            charge_list.sort(key=lambda t: t[1])

            last_iter = None
            for chg in charge_list:
                if not last_iter:
                    last_iter = chg[0]
                else:
                    if chg[0] < last_iter:
                        raise forms.ValidationError("Please correct charges accordingly.")
                    last_iter = chg[0]
            unzip = list(zip(*charge_list))
            if not len(set(unzip[1])) == len(unzip[1]):
                raise forms.ValidationError("Duplicate prices found for same distance.")



class HomePickupChargesInline(GenericTabularInline):
    form = HomePickupChargesForm
    formset = HomePickupChargesFormSet
    model = HomePickupCharges
    extra = 0
    can_delete = True
    show_change_link = False


class GenericLabAdminFormSet(forms.BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        current_lab_network = self.instance.network
        if current_lab_network:
            if current_lab_network.manageable_lab_network_admins.all().exists():
                is_lab_admin_active = False
                for value in self.cleaned_data:
                    if value and not value['DELETE'] and not value['is_disabled']:
                        is_lab_admin_active = True
                        break
                if is_lab_admin_active:
                    raise forms.ValidationError("This lab's network already has admin(s), so disable all admins of the lab.")


class GenericLabAdminInline(admin.TabularInline):
    model = GenericLabAdmin
    formset = GenericLabAdminFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    readonly_fields = ['user']
    verbose_name_plural = "Admins"
    fields = ['user', 'phone_number', 'name', 'lab', 'permission_type', 'super_user_permission', 'is_disabled', 'write_permission']


class LabDocumentFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        choices = dict(LabDocument.CHOICES)
        count = {}
        for key, value in LabDocument.CHOICES:
            count[key] = 0

        for value in self.cleaned_data:
            if value and not value['DELETE']:
                count[value['document_type']] += 1

        for key, value in count.items():
            if not key==LabDocument.ADDRESS and value>1:
                raise forms.ValidationError("Only one "+choices[key]+" is allowed")

        # if not self.instance.network or not self.instance.network.is_billing_enabled:
        #     if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
        #         for key, value in count.items():
        #             if not key==LabDocument.GST and value<1:
        #                 raise forms.ValidationError(choices[key]+" is required")


class LabDocumentInline(admin.TabularInline):
    model = LabDocument
    formset = LabDocumentFormSet
    # form = LabDocumentForm
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

    extra = 0
    can_delete = True
    show_change_link = False


class LabDoctorAvailabilityInline(admin.TabularInline):
    model = LabDoctorAvailability
    #form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


# class GenericAdminInline(admin.TabularInline):
#     model = GenericAdmin
#     extra = 0
#     can_delete = True
#     show_change_link = False
#     readonly_fields = ['user']
#     verbose_name_plural = "Admins"


class LabCertificationInline(admin.TabularInline):
    model = LabCertification
    extra = 0
    can_delete = True
    show_change_link = False


class LabForm(FormCleanMixin):
    about = forms.CharField(widget=forms.Textarea, required=False)
    primary_mobile = forms.CharField(required=True)
    primary_email = forms.EmailField(required=True)
    # city = forms.CharField(required=True)
    lab_priority = forms.IntegerField(required=True)
    operational_since = forms.ChoiceField(required=False, choices=hospital_operational_since_choices)
    home_pickup_charges = forms.DecimalField(required=False, initial=0)
    # onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Lab.ONBOARDING_STATUS)
    # agreed_rate_list = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'application/pdf'}))

    class Meta:
        model = Lab
        exclude = ()
        widgets = {
            'lab_pricing_group': autocomplete.ModelSelect2(url='labpricing-autocomplete'),
            'matrix_state': autocomplete.ModelSelect2(url='matrix-state-autocomplete'),
            'matrix_city': autocomplete.ModelSelect2(url='matrix-city-autocomplete', forward=['matrix_state'])
        }
        # exclude = ('pathology_agreed_price_percentage', 'pathology_deal_price_percentage', 'radiology_agreed_price_percentage',
        #            'radiology_deal_price_percentage', )

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data

    def clean_home_pickup_charges(self):
        data = self.cleaned_data.get('home_pickup_charges')
        if not data:
            data = 0
        return data

    def validate_qc(self):
        qc_required = {'name': 'req', 'location': 'req', 'operational_since': 'req', 'parking': 'req',
                       'license': 'req', 'building': 'req', 'locality': 'req',
                       'matrix_city': 'req', 'matrix_state': 'req',
                       'country': 'req', 'pin_code': 'req', 'network_type': 'req', 'lab_image': 'count'}

        if self.instance.network and self.instance.network.data_status != QCModel.QC_APPROVED:
            raise forms.ValidationError("Lab Network is not QC approved.")

        # if not self.instance.network or not self.instance.network.is_billing_enabled:
        #     qc_required.update({
        #         'lab_documents': 'count'
        #     })
        for key, value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type'] == 2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Lab")

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        if self.data.get('search_distance') and float(self.data.get('search_distance')) > float(50000):
            raise forms.ValidationError("Search Distance should be less than 50 KM.")
        if self.instance and self.instance.id and self.instance.data_status == QCModel.QC_APPROVED:
            is_enabled = data.get('enabled', None)
            if is_enabled is None:
                is_enabled = self.instance.enabled if self.instance else False
            if is_enabled:
                if any([data.get('disabled_after', None), data.get('disable_reason', None),
                        data.get('disable_comments', None)]):
                    raise forms.ValidationError(
                        "Cannot have disabled after/disabled reason/disable comments if lab is enabled.")
            elif not is_enabled:
                if not all([data.get('disabled_after', None), data.get('disable_reason', None)]):
                    raise forms.ValidationError("Must have disabled after/disable reason if lab is not enabled.")
                if data.get('disable_reason', None) and data.get('disable_reason', None) == Lab.OTHERS and not data.get(
                        'disable_comments', None):
                    raise forms.ValidationError("Must have disable comments if disable reason is others.")


class LabCityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'city'

    def lookups(self, request, model_admin):
        cities = Lab.objects.distinct('city').values_list('city','city')

        # cities = set([(c['city'].upper(), c['city'].upper()) if (c.get('city')) else ('', '') for c in
        #               Lab.objects.values('city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(city__iexact=self.value()).distinct()


class LabResource(resources.ModelResource):
    city = fields.Field()
    pan = fields.Field()
    gst = fields.Field()
    registration = fields.Field()
    cheque = fields.Field()
    email_confirmation = fields.Field()
    logo = fields.Field()

    class Meta:
        model = Lab
        fields = ('id', 'name', 'license', 'data_status', 'is_insurance_enabled', 'is_retail_enabled', 'is_ppc_pathology_enabled', 'is_ppc_radiology_enabled',
                  'onboarding_status', 'is_billing_enabled', 'primary_email',  'primary_mobile', 'hospital', 'network',
                  'pin_code', 'city', 'state', 'country', 'pathology_agreed_price_percentage', 'pathology_deal_price_percentage',
                  'radiology_agreed_price_percentage', 'radiology_deal_price_percentage', 'lab_pricing_group', 'assigned_to',
                  'matrix_reference_id', 'matrix_lead_id', 'is_home_collection_enabled', 'home_pickup_charges', 'is_live',
                  'is_test_lab', 'gst', 'pan', 'registration', 'cheque', 'logo', 'email_confirmation')

        export_order = ('id', 'name', 'license', 'data_status', 'is_insurance_enabled', 'is_retail_enabled', 'is_ppc_pathology_enabled', 'is_ppc_radiology_enabled',
                  'onboarding_status', 'is_billing_enabled', 'primary_email',  'primary_mobile', 'hospital', 'network',
                  'pin_code', 'city', 'state', 'country', 'pathology_agreed_price_percentage', 'pathology_deal_price_percentage',
                  'radiology_agreed_price_percentage', 'radiology_deal_price_percentage', 'lab_pricing_group', 'assigned_to',
                  'matrix_reference_id', 'matrix_lead_id', 'is_home_collection_enabled', 'home_pickup_charges', 'is_live',
                  'is_test_lab', 'gst', 'pan', 'registration', 'cheque', 'logo', 'email_confirmation')

    def dehydrate_data_status(self, lab):
        return dict(Lab.DATA_STATUS_CHOICES)[lab.data_status]

    def dehydrate_onboarding_status(self, lab):
        return dict(Lab.ONBOARDING_STATUS)[lab.onboarding_status]

    def dehydrate_hospital(self, lab):
        return (str(lab.hospital.name) if lab.hospital else '')

    def dehydrate_network(self, lab):
        return (str(lab.network.name) if lab.network else '')

    def dehydrate_assigned_to(self, lab):
        return (str(lab.assigned_to.phone_number) if lab.assigned_to else '')

    def dehydrate_gst(self, lab):

         status = 'Pending'
         for l in lab.lab_documents.all():
             if l.document_type == LabDocument.GST:
                status = 'Submitted'
         return status

    def dehydrate_pan(self, lab):
        status = 'Pending'
        for l in lab.lab_documents.all():
            if l.document_type == LabDocument.PAN:
                status = 'Submitted'
        return status

    def dehydrate_registration(self, lab):
        status = 'Pending'
        for l in lab.lab_documents.all():
            if l.document_type == LabDocument.REGISTRATION:
                status = 'Submitted'
        return status

    def dehydrate_cheque(self, lab):
        status = 'Pending'
        for l in lab.lab_documents.all():
            if l.document_type == LabDocument.CHEQUE:
                status = 'Submitted'
        return status

    def dehydrate_logo(self, lab):
        status = 'Pending'
        for l in lab.lab_documents.all():
            if l.document_type == LabDocument.LOGO:
                status = 'Submitted'
        return status

    def dehydrate_email_confirmation(self, lab):
        status = 'Pending'
        for l in lab.lab_documents.all():
            if l.document_type == LabDocument.EMAIL_CONFIRMATION:
                status = 'Submitted'
        return status


class LabTestGroupTimingForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end and start>=end:
            raise forms.ValidationError("Start time should be less than end time")


class LabTestGroupTimingInline(admin.TabularInline):
    model = LabTestGroupTiming
    form = LabTestGroupTimingForm
    extra = 0
    can_delete = True
    show_change_link = False


class LabAdmin(ImportExportMixin, admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):
    change_list_template = 'superuser_import_export.html'
    resource_class = LabResource
    list_display = ('name', 'lab_logo', 'updated_at', 'onboarding_status', 'data_status', 'welcome_calling_done',
                    'list_created_by', 'list_assigned_to', 'get_onboard_link',)
    # readonly_fields=('onboarding_status', )
    list_filter = ('data_status', 'enabled', 'welcome_calling_done', 'onboarding_status', 'is_insurance_enabled',
                   LabCityFilter, CreatedByFilter)
    exclude = ('search_key', 'pathology_agreed_price_percentage', 'pathology_deal_price_percentage',
               'radiology_agreed_price_percentage', 'radiology_deal_price_percentage', 'live_at',
               'onboarded_at', 'qc_approved_at', 'disabled_at', 'welcome_calling_done_at')

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj)

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.model.objects.filter(id=object_id).first()
        lab_appointment = LabAppointment.objects.filter(lab_id=object_id).first()
        content_type = ContentType.objects.get_for_model(obj)
        if lab_appointment:
            messages.set_level(request, messages.ERROR)
            messages.error(request, '{} could not deleted, as {} is present in appointment history'.format(content_type.model, content_type.model))
            return HttpResponseRedirect(reverse('admin:{}_{}_change'.format(content_type.app_label,
                                                                     content_type.model), args=[object_id]))
        if not obj:
            pass
        elif obj.enabled == False:
            pass
        else:
            messages.set_level(request, messages.ERROR)
            messages.error(request, '{} should be disable before delete'.format(content_type.model))
            return HttpResponseRedirect(reverse('admin:{}_{}_change'.format(content_type.app_label,
                                                                            content_type.model), args=[object_id]))
        return super().delete_view(request, object_id, extra_context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    form = LabForm
    search_fields = ['name', 'lab_pricing_group__group_name', ]
    inlines = [LabDoctorInline, LabServiceInline, LabDoctorAvailabilityInline, LabCertificationInline, LabAwardInline,
               LabAccreditationInline,
               LabManagerInline, LabTimingInline, LabImageInline, LabDocumentInline, HomePickupChargesInline,
               GenericLabAdminInline, AssociatedMerchantInline, LabTestGroupTimingInline, RemarkInline]
    # autocomplete_fields = ['lab_pricing_group', ]

    map_width = 200
    map_template = 'admin/gis/gmap.html'

    class Media:
        js = ('js/admin/ondoc.js',)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('lab_documents')

    def get_fields(self, request, obj=None):
        all_fields = super().get_fields(request, obj)
        if not request.user.is_superuser and not request.user.groups.filter(
                name=constants['WELCOME_CALLING_TEAM']).exists():
            if 'welcome_calling_done' in all_fields:
                all_fields.remove('welcome_calling_done')
        return all_fields

    def get_readonly_fields(self, request, obj=None):
        read_only_fields = ['lead_url', 'matrix_lead_id', 'matrix_reference_id', 'is_live', 'city', 'state']
        if (not request.user.is_member_of(constants['QC_GROUP_NAME'])) and (not request.user.is_superuser):
            read_only_fields += ['lab_pricing_group']
        if (not request.user.is_member_of(constants['SUPER_QC_GROUP'])) and (not request.user.is_superuser):
            read_only_fields += ['onboarding_status']
        if not request.user.groups.filter(
                name__in=[constants['WELCOME_CALLING_TEAM'],
                          constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']]) and not request.user.is_superuser:
            read_only_fields += ['is_location_verified']
        return read_only_fields

    def lab_logo(self, instance):
        lab_documents = instance.lab_documents.all()
        for lab_document in lab_documents:
            if lab_document.document_type == LabDocument.LOGO:
                return mark_safe("<a href={} target='_blank'>View</a> ".format(lab_document.name.url))
        return None
    lab_logo.short_description = 'Logo'

    def lead_url(self, instance):
        if instance.id:
            ref_id = instance.matrix_reference_id
            if ref_id is not None:
                html ='''<a href='/admin/lead/doctorlead/%s/change/' target=_blank>Lead Page</a>'''%(ref_id)
                return mark_safe(html)
        else:
            return mark_safe('''<span></span>''')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url('onboardlab_admin/(?P<userid>\d+)/', self.admin_site.admin_view(self.onboardlab_admin), name="onboardlab_admin"),
        ]
        return my_urls + urls

    def onboardlab_admin(self, request, userid):
        host = request.get_host()
        try:
            lab_obj = Lab.objects.get(id=userid)
        except Exception as e:
            return HttpResponse('invalid lab')

        count = 0
        try:
            count = LabOnboardingToken.objects.filter(lab = lab_obj).count()
        except Exception as e:
            pass
            # last_token = None

        #last_url = None
        #created_at = ""
        # if last_token:
        #     last_url = host+'/onboard/lab?token='+str(last_token.token)
        #     created_at = last_token.created_at

        # check for errors
        errors = []
        required = ['name', 'about', 'license', 'primary_email', 'primary_mobile', 'operational_since', 'parking',
                    'network_type', 'location', 'building', 'city', 'state', 'country', 'pin_code', 'agreed_rate_list']
        if lab_obj.is_ppc_pathology_enabled or lab_obj.is_ppc_radiology_enabled:
            required += ['ppc_rate_list']
        for req in required:
            if not getattr(lab_obj, req):
                errors.append(req+' is required')

        if not lab_obj.locality and not lab_obj.sublocality:
            errors.append('locality or sublocality is required')

        length_required = ['labservice', 'labdoctoravailability', 'labmanager', 'labaccreditation']
        if lab_obj.labservice_set.filter(service=LabService.RADIOLOGY).exists():
            length_required.append('labdoctor')
        for req in length_required:
            if not len(getattr(lab_obj, req+'_set').all()):
                errors.append(req + ' is required')
        # if not lab_obj.lab_timings.exists():
        #     errors.append('Lab Timings is required')

        #if not lab_obj.lab_services_set:
            # errors.append('lab services are required')

        # if not lab_obj.license:
        #     errors.append('License is required')
        # if not lab_obj.primary_email:
        #     errors.append('Primary Email is required')
        # if not lab_obj.primary_mobile:
        #     errors.append('Primary Mobile is required')
        # if not lab_obj.agreed_rate_list:
        #     errors.append('Agreed rate list in required')

        return render(request, 'onboardlab.html', {'lab': lab_obj, 'count': count, 'errors': errors})

    def get_onboard_link(self, obj = None):
        if obj.data_status == Lab.IN_PROGRESS and obj.onboarding_status in (Lab.NOT_ONBOARDED, Lab.REQUEST_SENT):
            return mark_safe("<a href='/admin/diagnostic/lab/onboardlab_admin/%s'>generate onboarding url</a>" % obj.id)
        return ""
    get_onboard_link.allow_tags = True

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if not form.cleaned_data.get('enabled', False) and not obj.disabled_by:
            obj.disabled_by = request.user
        elif form.cleaned_data.get('enabled', False) and obj.disabled_by:
            obj.disabled_by = None
        if not obj.assigned_to:
            obj.assigned_to = request.user
        if '_submit_for_qc' in request.POST:
            obj.data_status = QCModel.SUBMITTED_FOR_QC
        if '_qc_approve' in request.POST:
            obj.data_status = QCModel.QC_APPROVED
            obj.qc_approved_at = datetime.datetime.now()
        if '_mark_in_progress' in request.POST:
            obj.data_status = QCModel.REOPENED
        obj.status_changed_by = request.user
        obj.city = obj.matrix_city.name
        obj.state = obj.matrix_state.name
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        for instance in instances:
            if isinstance(instance, GenericLabAdmin):
                if (not instance.created_by):
                    instance.created_by = request.user
                if (not instance.id):
                    instance.source_type = GenericAdmin.CRM
            instance.save()
        formset.save_m2m()

    # def save_related(self, request, form, formsets, change):
    #     super(type(self), self).save_related(request, form, formsets, change)
    #     lab = form.instance
    #     lab_mgr_form_change = False
    #     lab_mgr_new_len = lab_mgr_del_len = 0
    #     for formset in formsets:
    #         if isinstance(formset, LabManagerFormSet):
    #             for form in formset.forms:
    #                 if 'contact_type' in form.changed_data or 'number' in form.changed_data:
    #                     lab_mgr_form_change = True
    #                     break
    #             lab_mgr_new_len = len(formset.new_objects)
    #             lab_mgr_del_len = len(formset.deleted_objects)
    #
    #     if lab is not None:
    #         if (lab_mgr_form_change or lab_mgr_new_len > 0 or lab_mgr_del_len > 0):
    #             GenericLabAdmin.create_admin_permissions(lab)

    def get_form(self, request, obj=None, **kwargs):
        form = super(LabAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['network'].queryset = LabNetwork.objects.filter(Q(data_status = QCModel.SUBMITTED_FOR_QC) | Q(data_status = QCModel.QC_APPROVED) | Q(created_by = request.user))
        form.base_fields['hospital'].queryset = Hospital.objects.filter(Q(data_status = QCModel.SUBMITTED_FOR_QC) | Q(data_status = QCModel.QC_APPROVED) | Q(created_by = request.user))
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if not request.user.is_superuser and not request.user.is_member_of(constants['QC_GROUP_NAME']):
            form.base_fields['assigned_to'].disabled = True
        return form

    # Method is already declared above
    # def get_readonly_fields(self, *args, **kwargs):
    #     read_only = super().get_readonly_fields(*args, **kwargs)
    #     if args:
    #         request = args[0]
    #         if not request.user.groups.filter(
    #                 name__in=[constants['WELCOME_CALLING_TEAM'],
    #                           constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']]) and not request.user.is_superuser:
    #             read_only += ('is_location_verified',)
    #
    #     return read_only



class LabAppointmentForm(RefundableAppointmentForm):
    start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder':'Select a date'}))
    start_time = forms.CharField(widget=TimePickerWidget())
    cancel_type = forms.ChoiceField(label='Cancel Type', choices=((0, 'Cancel and Rebook'),
                                                                  (1, 'Cancel and Refund'),), initial=0, widget=forms.RadioSelect)
    send_email_sms_report = forms.BooleanField(label='Send reports via message and email', initial=False, required=False)
    custom_otp = forms.IntegerField(required=False)
    hospital_reference_id = forms.CharField(widget=forms.Textarea, required=False)
    reports_physically_collected = forms.BooleanField(label='Reports collected physically by customer', initial=False, required=False)

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        # Appointments are now made with CREATED status.
        # if self.request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists() and cleaned_data.get('status') == LabAppointment.BOOKED:
        #     raise forms.ValidationError("Form cant be Saved with Booked Status.")
        if cleaned_data.get('start_date') and cleaned_data.get('start_time'):
            date_time_field = str(cleaned_data.get('start_date')) + " " + str(cleaned_data.get('start_time'))
            dt_field = parse_datetime(date_time_field)
            time_slot_start = make_aware(dt_field)
        else:
            raise forms.ValidationError("Enter valid start date and time.")
        if time_slot_start:
            hour = round(float(time_slot_start.hour) + (float(time_slot_start.minute) * 1 / 60), 2)
        else:
            raise forms.ValidationError("Invalid start date and time.")

        if time_slot_start != self.instance.time_slot_start and time_slot_start < timezone.now():
            raise forms.ValidationError("Time slot can never be in past. Please add time slot in future.")

        if self.instance.id:
            lab_test = self.instance.test_mappings.all()
            lab = self.instance.lab
        else:
            raise forms.ValidationError("Lab and lab test details not entered.")
        if cleaned_data.get('send_email_sms_report', False) and self.instance and self.instance.id and not sum(
                self.instance.reports.annotate(no_of_files=Count('files')).values_list('no_of_files', flat=True)):
                raise forms.ValidationError("Can't send reports as none are available. Please upload.")

        if cleaned_data.get('send_email_sms_report',
                            False) and self.instance and self.instance.id and not self.instance.status == LabAppointment.COMPLETED:
                raise forms.ValidationError("Can't send reports as appointment is not completed")

        if cleaned_data.get('reports_physically_collected', False) and self.instance and \
                self.instance.id and not self.instance.status == LabAppointment.COMPLETED:
                raise forms.ValidationError("Can't collect reports as appointment is not completed")

        # if self.instance.status in [LabAppointment.CANCELLED, LabAppointment.COMPLETED] and len(cleaned_data):
        #     raise forms.ValidationError("Cancelled/Completed appointment cannot be modified.")

        if not cleaned_data.get('status') is LabAppointment.CANCELLED and (cleaned_data.get(
                'cancellation_reason') or cleaned_data.get('cancellation_comments')):
            raise forms.ValidationError(
                "Reason/Comment for cancellation can only be entered on cancelled appointment")

        if cleaned_data.get('status') is LabAppointment.CREATED and cleaned_data.get('status_change_comments'):
            raise forms.ValidationError("Comment for status change can only be entered when changing status from created to other.")

        if cleaned_data.get('status') is LabAppointment.CANCELLED and not cleaned_data.get('cancellation_reason'):
            raise forms.ValidationError("Reason for Cancelled appointment should be set.")

        if cleaned_data.get('status') is LabAppointment.CANCELLED and cleaned_data.get(
                'cancellation_reason', None) and cleaned_data.get('cancellation_reason').is_comment_needed and not cleaned_data.get('cancellation_comments'):
            raise forms.ValidationError(
                "Cancellation comments must be mentioned for selected cancellation reason.")

        if cleaned_data.get('status') and self.instance and self.instance.status == LabAppointment.CREATED:
            if cleaned_data.get('status') not in [LabAppointment.BOOKED, LabAppointment.CANCELLED, LabAppointment.CREATED]:
                raise forms.ValidationError(
                    "Created status can only be changed to Booked or cancelled.")

            if cleaned_data.get('status') != LabAppointment.CREATED and not cleaned_data.get('status_change_comments'):
                raise forms.ValidationError(
                    "Status change comments must be mentioned when changing status from created to other.")

        if not lab.lab_pricing_group:
            raise forms.ValidationError("Lab is not in any lab pricing group.")

        if cleaned_data.get('status') not in [LabAppointment.CANCELLED, LabAppointment.COMPLETED, None]:
            if self.instance.id:
                selected_test_ids = lab_test.values_list('test', flat=True)
                is_lab_timing_available = LabTiming.objects.filter(
                    lab=lab,
                    lab__lab_pricing_group__available_lab_tests__test__in=selected_test_ids,
                    day=time_slot_start.weekday(),
                    start__lte=hour, end__gt=hour).exists()
                # if not is_lab_timing_available:
                #     raise forms.ValidationError("This lab test is not available on selected day and time.")
                if self.instance.is_home_pickup or cleaned_data.get('is_home_pickup'):
                    if not lab.is_home_collection_enabled:
                        raise forms.ValidationError("Home Pickup is disabled for the lab")
                    if hour < 7.0 or hour > 19.0:
                        raise forms.ValidationError("No time slot available")
                else:
                    if not lab.always_open and not is_lab_timing_available:
                        raise forms.ValidationError("No time slot available")

        if cleaned_data.get('status') and cleaned_data.get('status') == LabAppointment.COMPLETED:
            if self.instance and self.instance.id and not self.instance.status == OpdAppointment.ACCEPTED:
                raise forms.ValidationError("Can only complete appointment if it is in accepted state.")
            if not cleaned_data.get('custom_otp') == self.instance.otp:
                raise forms.ValidationError("Entered OTP is incorrect.")


        return cleaned_data


class LabReportFileInline(nested_admin.NestedTabularInline):
    model = LabReportFile
    extra = 0
    can_delete = True
    show_change_link = True


class LabReportInline(nested_admin.NestedTabularInline):
    model = LabReport
    extra = 0
    can_delete = True
    show_change_link = True
    inlines = [LabReportFileInline]

class LabPrescriptionForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            self.fields['prescription_file'].disabled = True

class LabPrescriptionInline(nested_admin.NestedGenericTabularInline):
    model = AppointmentPrescription
    form = LabPrescriptionForm
    #readonly_fields = ['user']
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 3

    def get_readonly_fields(self, request, obj):
        readonly_fields = ['user']
        return readonly_fields


class LabAppointmentAdmin(nested_admin.NestedModelAdmin):
    form = LabAppointmentForm
    search_fields = ['id']
    list_display = (
        'booking_id', 'get_profile', 'get_lab', 'status', 'reports_uploaded', 'time_slot_start', 'effective_price', 'get_profile_email',
        'get_profile_age', 'created_at', 'updated_at', 'get_lab_test_name')
    list_filter = ('status', 'payment_type')
    date_hierarchy = 'created_at'

    inlines = [
        LabReportInline,
        LabPrescriptionInline
    ]

    # def get_autocomplete_fields(self, request):
    #     if request.user.is_superuser:
    #         temp_autocomplete_fields = ('lab', 'profile', 'user')
    #     else:
    #         temp_autocomplete_fields = super().get_autocomplete_fields(request)
    #     return temp_autocomplete_fields

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('profile', 'lab').prefetch_related('lab_test', 'reports','reports__files',
                                                                                      'test_mappings', 'test_mappings__test')
        return qs

    def uploaded_prescriptions(self, obj):
        prescriptions = obj.get_all_uploaded_prescriptions()

        prescription_string = ""
        for p in prescriptions:
            prescription_string+="<div><a target='_blank' href={}>{}</a></div> | {}".format(
                util_absolute_url(p.prescription_file.url), util_absolute_url(p.prescription_file.url), str(p.created_at.date()))
        return mark_safe(prescription_string)

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, None)

        queryset = queryset.filter(Q(integrator_response__integrator_order_id__icontains=search_term) |
         Q(id__contains=search_term) | Q(lab__name__icontains=search_term) | Q(profile__name__icontains=search_term) | Q(profile__phone_number__icontains=search_term)).distinct()

        return queryset, use_distinct

    def integrator_order_status(self, obj):
        return obj.integrator_order_status()

    def thyrocare_booking_id(self, obj):
        return obj.thyrocare_booking_no()

    def accepted_through(self, obj):
        return obj.accepted_through()

    def payout_info(self, obj):
        return MerchantPayout.get_merchant_payout_info(obj)
    payout_info.short_description = 'Merchant Payment Info'

    def through_app(self, obj):
        return obj.created_by_native()

    def get_profile_email(self, obj):
        if not obj.profile:
            return None
        return obj.profile.email

    get_profile_email.admin_order_field = 'profile'
    get_profile_email.short_description = 'Profile Email'

    def get_profile_age(self, obj):
        if not obj.profile:
            return None
        return obj.profile.get_age()

    get_profile_age.admin_order_field = 'profile'
    get_profile_age.short_description = 'Profile Age'

    def get_profile(self, obj):
        if not obj.profile:
            return ''
        return obj.profile.name

    get_profile.admin_order_field = 'profile'
    get_profile.short_description = 'Profile Name'

    def get_lab(self, obj):
        return obj.lab.name

    get_lab.admin_order_field = 'lab'
    get_lab.short_description = 'Lab Name'

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        allowed_status_for_agent = [(LabAppointment.BOOKED, 'Booked'),
                                    (LabAppointment.RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                                    (LabAppointment.RESCHEDULED_LAB, 'Rescheduled by lab'),
                                    (LabAppointment.ACCEPTED, 'Accepted'),
                                    (LabAppointment.CANCELLED, 'Cancelled'),
                                    (LabAppointment.COMPLETED, 'Completed')]
        if db_field.name == "status" and request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            kwargs['choices'] = allowed_status_for_agent
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['cancellation_reason'].queryset = CancellationReason.objects.filter(
            Q(type=Order.LAB_PRODUCT_ID) | Q(type__isnull=True), visible_on_admin=True)
        if obj is not None and obj.time_slot_start:
            time_slot_start = timezone.localtime(obj.time_slot_start, pytz.timezone(settings.TIME_ZONE))
            form.base_fields['start_date'].initial = time_slot_start.strftime('%Y-%m-%d') if time_slot_start else None
            form.base_fields['start_time'].initial = time_slot_start.strftime('%H:%M') if time_slot_start else None
        return form

    def get_fields(self, request, obj=None):
        # if request.user.is_superuser:
        #     return ('booking_id', 'order_id', 'lab', 'lab_id', 'lab_contact_details', 'profile', 'user',
        #             'profile_detail', 'status', 'cancel_type', 'cancellation_reason', 'cancellation_comments',
        #             'get_lab_test', 'price', 'agreed_price',
        #             'deal_price', 'effective_price', 'start_date', 'start_time', 'otp', 'payment_status',
        #             'payment_type', 'insurance', 'is_home_pickup', 'address', 'outstanding',
        #             'send_email_sms_report', 'invoice_urls', 'reports_uploaded', 'email_notification_timestamp', 'payment_type'
        #             )
        # elif request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
        all_fields = ('booking_id', 'through_app', 'integrator_order_status', 'thyrocare_booking_id', 'accepted_through', 'order_id',  'lab_id', 'lab_name', 'get_lab_test', 'lab_contact_details',
                    'used_profile_name', 'used_profile_number',
                    'default_profile_name', 'default_profile_number', 'user_id', 'user_number', 'price', 'agreed_price',
                    'deal_price', 'effective_price', 'payment_status', 'payment_type', 'insurance', 'is_home_pickup',
                    'get_pickup_address', 'get_lab_address', 'outstanding', 'status', 'cancel_type',
                    'cancellation_reason', 'cancellation_comments', 'start_date', 'start_time',
                    'send_email_sms_report', 'reports_physically_collected', 'invoice_urls', 'reports_uploaded', 'email_notification_timestamp', 'payment_type',
                     'payout_info', 'refund_initiated', 'status_change_comments','uploaded_prescriptions', 'hospital_reference_id')
        if request.user.groups.filter(name=constants['APPOINTMENT_OTP_TEAM']).exists() or request.user.is_superuser:
            all_fields = all_fields + ('otp',)

        if obj and obj.can_agent_refund(request.user):
            all_fields = all_fields + ('refund_payment', 'refund_reason')

        if obj and obj.id and obj.status == OpdAppointment.ACCEPTED:
            all_fields = all_fields + ('custom_otp',)
        return all_fields
        # else:
        #     return ()

    def get_readonly_fields(self, request, obj=None):
        # if request.user.is_superuser:
        #     read_only =  ['booking_id', 'order_id', 'lab_id', 'lab_contact_details', 'get_lab_test', 'invoice_urls', 'reports_uploaded', 'email_notification_timestamp', 'payment_type']
        # elif request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
        read_only = ['booking_id' ,'through_app', 'integrator_order_status', 'accepted_through', 'thyrocare_booking_id', 'order_id', 'lab_name', 'lab_id', 'get_lab_test', 'invoice_urls',
                     'lab_contact_details', 'used_profile_name', 'used_profile_number',
                     'default_profile_name', 'default_profile_number', 'user_number', 'user_id', 'price',
                     'agreed_price',
                     'deal_price', 'effective_price', 'payment_status',
                     'payment_type', 'insurance', 'is_home_pickup', 'get_pickup_address', 'get_lab_address',
                     'outstanding', 'reports_uploaded', 'email_notification_timestamp', 'payment_type', 'payout_info', 'refund_initiated',
                     'uploaded_prescriptions']
        # else:
        #     read_only = []
        if obj and (obj.status == LabAppointment.COMPLETED or obj.status == LabAppointment.CANCELLED):
            read_only.extend(['status'])
        if request.user.groups.filter(name=constants['APPOINTMENT_OTP_TEAM']).exists() or request.user.is_superuser:
            read_only = read_only + ['otp']

        if obj and obj.status is not LabAppointment.CREATED:
            read_only = read_only + ['status_change_comments']
        return read_only

    def refund_initiated(self, obj):
        return bool(obj.has_app_consumer_trans())

    # def get_inline_instances(self, request, obj=None):
    #     inline_instance = super().get_inline_instances(request=request, obj=obj)
    #     if request.user.is_superuser:
    #         inline_instance.append(LabTestInline(self.model, self.admin_site))
    #         inline_instance.append(LabReportInline(self.model, self.admin_site))
    #     else:
    #         inline_instance.append(LabReportInline(self.model, self.admin_site))
    #     return inline_instance

    def reports_uploaded(self, instance):
        if instance and instance.id:
            for report in instance.reports.all():
                if report.files.all():
                    return True
        elif instance and instance.id and instance.reports_physically_collected:
            return True

        return False

    def invoice_urls(self, instance):
        invoices_urls = ''
        for invoice in instance.get_invoice_urls():
            invoices_urls += "<a href={} target='_blank'>{}</a><br>".format(util_absolute_url(invoice),
                                                                             util_file_name(invoice))
        return mark_safe(invoices_urls)
    invoice_urls.short_description = 'Invoice(s)'

    def email_notification_timestamp(self, instance):
        l = instance.email_notification.filter(notification_type=NotificationAction.LAB_REPORT_SEND_VIA_CRM).values_list('created_at', flat=True)
        result = []
        for temp_item in l:
            formated_date = datetime_to_formated_string(temp_item)
            result.append(formated_date)
        return ", ".join(result)
    email_notification_timestamp.short_description = 'Report(s) sent at'

    def order_id(self, obj):
        if obj and obj.id:
            order_ids = Order.objects.filter(product_id=Order.LAB_PRODUCT_ID, reference_id=obj.id).values_list('id', flat=True)
            if order_ids:
                return ', '.join([str(order_id) for order_id in order_ids])
        return None
    order_id.short_description = 'Order Id(s)'

    def lab_id(self, obj):
        lab = obj.lab
        if lab is not None:
            return lab.id
        return None

    def booking_id(self, obj):
        return obj.id if obj.id else None

    def lab_name(self, obj):
        profile_link = "lab/{}".format(obj.lab.id)
        return mark_safe('{name} (<a href="{consumer_app_domain}/{profile_link}">Profile</a>)'.format(
            name=obj.lab.name,
            consumer_app_domain=settings.CONSUMER_APP_DOMAIN,
            profile_link=profile_link))

    def lab_contact_details(self, obj):
        employees = obj.lab.labmanager_set.all()
        details = ''
        for employee in employees:
            details += 'Name : {name}<br>Phone number : {number}<br>Email : {email}<br>Type : {type}<br><br>'.format(
                name=employee.name, number=employee.number, email=employee.email,
                type=dict(LabManager.CONTACT_TYPE_CHOICES)[employee.contact_type])
            # ' , '.join([str(employee.name), str(employee.number), str(employee.email), str(employee.details)])
            # details += '\n'
        return mark_safe('<p>{details}</p>'.format(details=details))

    def get_lab_test(self, obj):
        format_string = ""
        for data in obj.test_mappings.all():
            format_string += "<div><span>{}, MRP : {}, Deal Price : {} </span></div>".format(data.test.name, data.mrp,
                                                                                         data.custom_deal_price if data.custom_deal_price else data.computed_deal_price)
        return format_html_join(
            mark_safe('<br/>'),
            format_string,
            ((),),
        )
    get_lab_test.short_description = 'Lab Test'

    def get_lab_test_name(self, obj):
        format_string = ""
        for data in obj.test_mappings.all():
            format_string += "{},".format(data.test.name)
        return format_string
    get_lab_test_name.short_description = 'Lab Test Names'

    def get_lab_address(self, obj):
        address_items = [
            str(getattr(obj.lab, attribute))
            for attribute in ['building', 'sublocality', 'locality', 'city', 'state', 'country',
                              'pin_code'] if getattr(obj.lab, attribute)]
        format_string = "<div>{}</div>".format(",".join(address_items))
        return format_html_join(
            mark_safe('<br/>'),
            format_string,
            ((),),
        )
    get_lab_address.short_description = 'Lab Address'

    def get_pickup_address(self, obj):
        if not obj.is_home_pickup:
            return ""
        address_items = [str(obj.address.get(key)) for key in ['address', 'landmark', 'pincode'] if obj.address.get(key)]
        format_string = "<div>{}</div>".format(",".join(address_items))
        return format_html_join(
            mark_safe('<br/>'),
            format_string,
            ((),),
        )
    get_pickup_address.short_description = 'Home Pickup Address'

    def used_profile_name(self, obj):
        return obj.profile.name

    def used_profile_number(self, obj):
        return obj.profile.phone_number

    def default_profile_name(self, obj):
        # return obj.profile.user.profiles.all()[:1][0].name
        default_profile = obj.profile.user.profiles.filter(is_default_user=True)
        if default_profile.exists():
            return default_profile.first().name
        else:
            return ''

    def default_profile_number(self, obj):
        # return obj.profile.user.profiles.all()[:1][0].phone_number
        default_profile = obj.profile.user.profiles.filter(is_default_user=True)
        if default_profile.exists():
            return default_profile.first().phone_number
        else:
            return ''

    def user_number(self, obj):
        return obj.user.phone_number

    def user_id(self, obj):
        return obj.user.id

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        responsible_user = request.user
        obj._responsible_user = responsible_user if responsible_user and not responsible_user.is_anonymous else None
        if obj:
            lab_app_obj = None
            if obj.id:
                obj._source = AppointmentHistory.CRM
                lab_app_obj = LabAppointment.objects.select_for_update().filter(pk=obj.id).first()
            # date = datetime.datetime.strptime(request.POST['start_date'], '%Y-%m-%d')
            # time = datetime.datetime.strptime(request.POST['start_time'], '%H:%M').time()
            #
            # date_time = datetime.datetime.combine(date, time)
            send_email_sms_report = form.cleaned_data.get('send_email_sms_report', False)
            # reports_physically_collected = form.cleaned_data.get('reports_physically_collected', False)
            if request.POST['start_date'] and request.POST['start_time']:
                date_time_field = request.POST['start_date'] + " " + request.POST['start_time']
                to_zone = tz.gettz(settings.TIME_ZONE)
                dt_field = parse_datetime(date_time_field).replace(tzinfo=to_zone)

                if dt_field:
                    obj.time_slot_start = dt_field
            if request.POST.get('status') and int(request.POST['status']) == LabAppointment.CANCELLED:
                obj.cancellation_type = LabAppointment.AGENT_CANCELLED
                cancel_type = int(request.POST.get('cancel_type'))
                if cancel_type is not None:
                    logger.warning("Lab Admin Cancel started - " + str(obj.id) + " timezone - " + str(timezone.now()))
                    obj.action_cancelled(cancel_type)
                    logger.warning("Lab Admin Cancel completed - " + str(obj.id) + " timezone - " + str(timezone.now()))
            elif request.POST.get('status') and int(request.POST['status']) == LabAppointment.COMPLETED and lab_app_obj and lab_app_obj != LabAppointment.COMPLETED:
                obj.action_completed()
            if form and form.cleaned_data and form.cleaned_data.get('refund_payment', False):
                obj._refund_reason = form.cleaned_data.get('refund_reason', '')
                obj.action_refund()
            else:
                super().save_model(request, obj, form, change)
                if request.POST.get('status') and (int(request.POST['status']) == LabAppointment.ACCEPTED):
                    lab_appointment_content_type = ContentType.objects.get_for_model(obj)
                    history_obj = IntegratorHistory.objects.filter(content_type=lab_appointment_content_type,
                                                                   object_id=obj.id).order_by('id').last()
                    if history_obj:
                        # history_obj.status = IntegratorHistory.PUSHED_AND_ACCEPTED
                        history_obj.accepted_through = "CRM"
                        history_obj.save()

            if send_email_sms_report and sum(
                    obj.reports.annotate(no_of_files=Count('files')).values_list('no_of_files', flat=True)):
                transaction.on_commit(lambda: self.on_commit_tasks(obj.id))

    def on_commit_tasks(self, obj_id):
        from ondoc.notification.tasks import send_lab_reports
        try:
            send_lab_reports.apply_async((obj_id,), countdown=1)
        except Exception as e:
            logger.error(str(e))
        # send_lab_reports(obj_id)

    class Media:
        js = (
            '//ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js',
            'js/admin/ondoc.js',
        )


class ParameterLabTestInline(admin.TabularInline):
    model = LabTest.parameter.through
    fk_name = 'lab_test'
    verbose_name = 'Parameter'
    verbose_name_plural = 'Parameters'
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['parameter']

    def get_queryset(self, request):
        return super().get_queryset(request)


class FAQLabTestInLine(admin.StackedInline):
    model = QuestionAnswer
    verbose_name = 'Frequently Asked Questions'
    can_delete = True
    fields = ['test_question', 'test_answer']
    extra = 0


class FrequentlyBookedTogetherTestInLine(admin.StackedInline):
    model = FrequentlyAddedTogetherTests
    verbose_name = 'Frequently booked together'
    can_delete = True
    fk_name = 'original_test'
    fields = ['original_test', 'booked_together_test']
    extra = 0
    autocomplete_fields = ['booked_together_test',]

class TestPackageFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        for data in self.cleaned_data:
            lab_test = data.get('lab_test')
            if not lab_test:
                continue
            if self.instance.test_type != LabTest.OTHER and self.instance.test_type != lab_test.test_type:
                raise forms.ValidationError('Test-{} is not correct for the Package.'.format(lab_test.name))
            if lab_test.is_package is True:
                raise forms.ValidationError('{} is a test package'.format(lab_test.name))


class TestParameterAdminForm(forms.ModelForm):
    # name = forms.CharField(widget=forms.Textarea, required=False)
    details = forms.CharField(widget=forms.Textarea, required=False)

    class Media:
        extend = False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'test_parameter/js/init.js')
        css = {'all': ('test_parameter/css/style.css',)}


class TestParameterAdmin(VersionAdmin):
    form = TestParameterAdminForm
    search_fields = ['name']
    list_display = ['name']


class LabTestPackageInline(admin.TabularInline):
    model = LabTest.test.through
    fk_name = 'package'
    verbose_name = "Package Test"
    verbose_name_plural = "Package Tests"
    formset = TestPackageFormSet
    autocomplete_fields = ['lab_test']

    def get_queryset(self, request):
        return super(LabTestPackageInline, self).get_queryset(request).filter(
            lab_test__is_package=False, package__is_package=True)


class LabTestToRecommendedCategoryInlineForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        if self.instance and self.instance.id and self.instance.lab_test and self.instance.lab_test.is_package:
            raise forms.ValidationError("Recommended category can only be added on lab test.")
        temp_recommended_category = cleaned_data.get('parent_category')
        if temp_recommended_category and not temp_recommended_category.is_package_category:
            raise forms.ValidationError("Recommended category can only be a lab test package category.")


class LabTestRecommendedCategoryInline(AutoComplete, TabularInline):
    model = LabTestRecommendedCategoryMapping
    form = LabTestToRecommendedCategoryInlineForm
    fk_name = 'lab_test'
    extra = 0
    can_delete = True
    autocomplete_fields = ['parent_category']
    verbose_name = "Recommended Category"
    verbose_name_plural = "Recommended Categories"


class LabTestToParentCategoryInlineFormset(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        all_parent_categories = []
        count_is_primary = 0
        for value in self.cleaned_data:
            if value and not value.get("DELETE"):
                all_parent_categories.append(value.get('parent_category'))
                if value.get('is_primary', False):
                    count_is_primary += 1
        # If lab test is a package its parent can only be package category.
        if self.instance.is_package:
            if any([not parent_category.is_package_category for parent_category in all_parent_categories]):
                raise forms.ValidationError("Parent Categories must be a lab test package category.")
        else:
            if any([parent_category.is_package_category for parent_category in all_parent_categories]):
                raise forms.ValidationError("Parent Categories must be a lab test category.")
        if not count_is_primary == 1:
            raise forms.ValidationError("Must have one and only one primary parent category.")


class LabTestCategoryInline(AutoComplete, TabularInline):
    model = LabTestCategoryMapping
    fk_name = 'lab_test'
    extra = 0
    can_delete = True
    autocomplete_fields = ['parent_category']
    verbose_name = "Parent Category"
    verbose_name_plural = "Parent Categories"
    formset = LabTestToParentCategoryInlineFormset


class LabTestAdminForm(forms.ModelForm):
    why = forms.CharField(widget=forms.Textarea, required=False)
    about_test = forms.CharField(widget=forms.Textarea, required=False)
    preparations = forms.CharField(widget=forms.Textarea, required=False)

    class Media:
        extend = False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'lab_test/js/init.js')
        css = {'all': ('lab_test/css/style.css',)}

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        # is_package toggles handling
        if cleaned_data.get('is_package', False):
            if self.instance.pk:
                if self.instance.parent_lab_test_category_mappings.filter(parent_category__is_package_category=False).count():
                    raise forms.ValidationError("Already has lab test category as parent(s). Remove all of them and try again.")
        else:
            if self.instance.pk:
                if self.instance.parent_lab_test_category_mappings.filter(parent_category__is_package_category=True).count():
                    raise forms.ValidationError("Already has lab test package category as parent(s). Remove all of them and try again.")

        if cleaned_data.get('is_package') == True:
            if not cleaned_data.get('min_age'):
                raise forms.ValidationError('Please enter min_age')
            if not cleaned_data.get('max_age'):
                raise forms.ValidationError('Please enter max_age')
            if not cleaned_data.get('gender_type'):
                raise forms.ValidationError('Please enter gender_type')
            if cleaned_data.get('min_age') > cleaned_data.get('max_age'):
                raise forms.ValidationError('min_age cannot be more than max_age')
        else:
            if cleaned_data.get('min_age'):
                raise forms.ValidationError('Please dont enter min_age')
            if cleaned_data.get('max_age'):
                raise forms.ValidationError('Please dont enter max_age')
            if cleaned_data.get('gender_type'):
                raise forms.ValidationError('Please dont enter gender_type')
            if cleaned_data.get('reference_code'):
                raise forms.ValidationError('Please dont enter reference code for a test')


class LabTestReportThresholdInline(AutoComplete, TabularInline):
    model = LabTestThresholds
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'rows': 6, 'cols': 20})},
    }
    fk_name = 'lab_test'
    extra = 0
    can_delete = True
    autocomplete_fields = ['lab_test']
    # formset = LabTestToParentCategoryInlineFormset


class LabTestAdmin(ImportExportMixin, VersionAdmin):
    form = LabTestAdminForm
    change_list_template = 'superuser_import_export.html'
    formats = (base_formats.XLS, base_formats.XLSX,)
    inlines = [LabTestCategoryInline, LabTestRecommendedCategoryInline, FAQLabTestInLine, FrequentlyBookedTogetherTestInLine, LabTestReportThresholdInline]
    search_fields = ['name']
    list_filter = ('is_package', 'enable_for_ppc', 'enable_for_retail')
    exclude = ['search_key']
    #readonly_fields = ['url',]
    autocomplete_fields = ['author',]

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj and not obj.is_package:
            return [value for value in fields if value != 'number_of_tests']
        return fields

    def get_readonly_fields(self, request, obj=None):
        read_only_fields = ['url']
        if not request.user.is_member_of(constants['SUPER_INSURANCE_GROUP']) and not request.user.is_superuser:
            read_only_fields += ['insurance_cutoff_price']

        return read_only_fields


    def get_inline_instances(self, request, obj=None):
        inline_instance = super().get_inline_instances(request=request, obj=obj)
        if obj and obj.is_package and LabTest.objects.filter(pk=obj.id, is_package=True).exists():
            inline_instance.append(LabTestPackageInline(self.model, self.admin_site))
        if obj and LabTest.objects.filter(pk=obj.id, is_package=False).exists():
            inline_instance.append(ParameterLabTestInline(self.model, self.admin_site))
        return inline_instance

    # def get_active_url(self, obj=None):
    #     if obj:
    #         active_urls = EntityUrls.objects.filter(entity_id=obj.id, is_valid=True).first()
    #         if active_urls:
    #             return active_urls.url

    #     return ''

class LabTestTypeAdmin(VersionAdmin):
    search_fields = ['name']


# class LabSubTestTypeAdmin(VersionAdmin):
#     search_fields = ['name']

class LabTestCategoryForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        # is_live toggles handling
        if cleaned_data.get('is_live', False) and not cleaned_data.get('is_package_category', False) \
                and not cleaned_data.get('preferred_lab_test', None):
            raise forms.ValidationError('This category cannot go live without preferred lab test.')
        if cleaned_data.get('is_live', False) and cleaned_data.get('is_package_category', False) \
                and cleaned_data.get('preferred_lab_test', None):
            raise forms.ValidationError('This category cannot have preferred lab test.')
        # is_package_category toggles handling
        if cleaned_data.get('is_package_category', False):
            if self.instance.pk:
                if self.instance.lab_test_mappings.filter(lab_test__is_package=False).count():
                    raise forms.ValidationError('This category has lab test under it, delete all of them and try again.')
        else:
            if self.instance.pk:
                if self.instance.lab_test_mappings.filter(lab_test__is_package=True).count():
                    raise forms.ValidationError('This category has lab test package(s) under it, delete all of them and try again.')
        preferred_lab_test = cleaned_data.get('preferred_lab_test')
        if preferred_lab_test:
            if self.instance.pk:
                if not preferred_lab_test.parent_lab_test_category_mappings.filter(parent_category=self.instance):
                    raise forms.ValidationError(
                        'This category and preferred lab test are not related.')
            else:
                raise forms.ValidationError('Category and preferred lab_test should be related.')


class LabTestCategoryAdmin(VersionAdmin):
    # list_display = ['test', 'lab_pricing_group', 'get_type', 'mrp', 'computed_agreed_price',
    #                 'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'enabled']
    exclude = ['search_key']
    search_fields = ['name']
    form = LabTestCategoryForm
    autocomplete_fields = ['preferred_lab_test']
    list_filter = ['is_package_category']


class AvailableLabTestAdmin(VersionAdmin):
    list_display = ['test', 'lab_pricing_group', 'get_type', 'mrp', 'computed_agreed_price',
                    'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'enabled']
    search_fields = ['test__name', 'lab_pricing_group__group_name', 'lab_pricing_group__labs__name']
    # autocomplete_fields = ['test']

    class Media:
        js = ('js/admin/ondoc.js',)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        responsible_user = request.user
        transaction.on_commit(lambda: self.on_commit_tasks(obj, responsible_user))

    def on_commit_tasks(self, obj, responsible_user):
        if obj.custom_deal_price:
            deal_price = obj.custom_deal_price
        else:
            deal_price = obj.computed_deal_price if obj.computed_deal_price else 0

        if obj.custom_agreed_price:
            agreed_price = obj.custom_agreed_price
        else:
            agreed_price = obj.computed_agreed_price if obj.computed_agreed_price else 0

        if deal_price < agreed_price:
            obj.send_pricing_alert_email(responsible_user)


class DiagnosticConditionLabTestInline(admin.TabularInline):
    model = DiagnosticConditionLabTest
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['lab_test']


class CommonDiagnosticConditionAdmin(VersionAdmin):
    search_fields = ['name']
    inlines = [DiagnosticConditionLabTestInline]


class CommonTestAdmin(VersionAdmin):
    autocomplete_fields = ['test']


class CommonPackageAdmin(VersionAdmin):

    def get_form(self, request, obj=None, **kwargs):
        form = super(CommonPackageAdmin, self).get_form(request, obj=obj, **kwargs)
        form.base_fields['package'].queryset = LabTest.objects.filter(is_package=True)
        return form


class LabTestGroupAdmin(admin.ModelAdmin):
    search_fields = ['name']
    list_display = ['name']


class LabTestGroupResource(resources.ModelResource):
    test = fields.Field(attribute='test_id', column_name='test')
    lab_test_group = fields.Field(attribute='lab_test_group_id', column_name='group')

    class Meta:
        model = LabTestGroupMapping
        fields = ('id')

    def before_save_instance(self, instance, using_transactions, dry_run):
        super().before_save_instance(instance, using_transactions, dry_run)


class LabTestGroupMappingAdmin(ImportMixin, admin.ModelAdmin):
    resource_class = LabTestGroupResource
    formats = (base_formats.XLS, base_formats.XLSX)
    list_display = ['test', 'lab_test_group']
    search_fields = ['test__name', 'lab_test_group__name']


class TestParameterChatForm(forms.ModelForm):
    test = forms.ModelChoiceField(
        queryset=LabTest.objects.filter(availablelabs__lab_pricing_group__labs__network_id=int(settings.THYROCARE_NETWORK_ID),
                                        enable_for_retail=True, availablelabs__enabled=True).distinct().order_by('name'))


class TestParameterChatAdmin(admin.ModelAdmin):
    form = TestParameterChatForm
    list_display = ['test_name']
    readonly_fields = ('test_name',)
