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
from django.db.models import Q
from django.db import models, transaction
from django.utils.dateparse import parse_datetime
from dateutil import tz
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.html import format_html_join
import pytz

from ondoc.account.models import Order
from ondoc.doctor.models import Hospital
from ondoc.diagnostic.models import (LabTiming, LabImage,
                                     LabManager, LabAccreditation, LabAward, LabCertification, AvailableLabTest,
                                     LabNetwork, Lab, LabOnboardingToken, LabService, LabDoctorAvailability,
                                     LabDoctor, LabDocument, LabTest, DiagnosticConditionLabTest, LabNetworkDocument,
                                     LabAppointment, HomePickupCharges,
                                     TestParameter, ParameterLabTest, LabReport, LabReportFile, LabTestCategoryMapping)
from .common import *
from ondoc.authentication.models import GenericAdmin, User, QCModel, BillingAccount, GenericLabAdmin
from ondoc.crm.admin.doctor import CustomDateInput, TimePickerWidget, CreatedByFilter, AutoComplete
from ondoc.crm.admin.autocomplete import PackageAutoCompleteView
from django.contrib.contenttypes.admin import GenericTabularInline
from ondoc.authentication import forms as auth_forms
from ondoc.authentication.admin import BillingAccountInline
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet
import logging
import nested_admin

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
    fields = ['user', 'phone_number', 'lab', 'permission_type', 'super_user_permission', 'is_disabled', 'read_permission', 'write_permission']


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
    city = forms.CharField(required=True)
    operational_since = forms.ChoiceField(required=False, choices=hospital_operational_since_choices)
    home_pickup_charges = forms.DecimalField(required=False, initial=0)
    # onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Lab.ONBOARDING_STATUS)
    # agreed_rate_list = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'application/pdf'}))

    class Meta:
        model = Lab
        exclude = ()
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
                       'license': 'req', 'building': 'req', 'locality': 'req', 'city': 'req', 'state': 'req',
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


class LabAdmin(ImportExportMixin, admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):
    change_list_template = 'superuser_import_export.html'
    resource_class = LabResource
    list_display = ('name', 'lab_logo', 'updated_at', 'onboarding_status', 'data_status', 'list_created_by', 'list_assigned_to',
                    'get_onboard_link',)

    # readonly_fields=('onboarding_status', )
    list_filter = ('data_status', 'onboarding_status', 'is_insurance_enabled', LabCityFilter, CreatedByFilter)

    exclude = ('search_key', 'pathology_agreed_price_percentage', 'pathology_deal_price_percentage',
               'radiology_agreed_price_percentage',
               'radiology_deal_price_percentage', 'live_at', 'onboarded_at', 'qc_approved_at')

    form = LabForm
    search_fields = ['name', 'lab_pricing_group__group_name', ]
    inlines = [LabDoctorInline, LabServiceInline, LabDoctorAvailabilityInline, LabCertificationInline, LabAwardInline,
               LabAccreditationInline,
               LabManagerInline, LabTimingInline, LabImageInline, LabDocumentInline, HomePickupChargesInline,
               BillingAccountInline, GenericLabAdminInline]
    autocomplete_fields = ['lab_pricing_group', ]

    map_width = 200
    map_template = 'admin/gis/gmap.html'

    class Media:
        js = ('js/admin/ondoc.js',)

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('lab_documents')

    def get_readonly_fields(self, request, obj=None):
        read_only_fields = ['lead_url', 'matrix_lead_id', 'matrix_reference_id', 'is_live']
        if (not request.user.is_member_of(constants['QC_GROUP_NAME'])) and (not request.user.is_superuser):
            read_only_fields += ['lab_pricing_group']
        if (not request.user.is_member_of(constants['SUPER_QC_GROUP'])) and (not request.user.is_superuser):
            read_only_fields += ['onboarding_status']
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
        if not obj.assigned_to:
            obj.assigned_to = request.user
        if '_submit_for_qc' in request.POST:
            obj.data_status = 2
        if '_qc_approve' in request.POST:
            obj.data_status = 3
            obj.qc_approved_at = datetime.datetime.now()
        if '_mark_in_progress' in request.POST:
            obj.data_status = 1

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
        form.base_fields['network'].queryset = LabNetwork.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        form.base_fields['hospital'].queryset = Hospital.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if not request.user.is_superuser and not request.user.is_member_of(constants['QC_GROUP_NAME']):
            form.base_fields['assigned_to'].disabled = True
        return form


class LabAppointmentForm(forms.ModelForm):

    start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder':'Select a date'}))
    start_time = forms.CharField(widget=TimePickerWidget())
    cancel_type = forms.ChoiceField(label='Cancel Type', choices=((0, 'Cancel and Rebook'),
                                                                  (1, 'Cancel and Refund'),), initial=0, widget=forms.RadioSelect)

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        if self.request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists() and cleaned_data.get('status') == LabAppointment.BOOKED:
            raise forms.ValidationError("Form cant be Saved with Booked Status.")
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

        if cleaned_data.get('lab') and cleaned_data.get('lab_test'):
            lab_test = cleaned_data.get('lab_test').all()
            lab = cleaned_data.get('lab')
        elif self.instance.id:
            lab_test = self.instance.lab_test.all()
            lab = self.instance.lab
        else:
            raise forms.ValidationError("Lab and lab test details not entered.")


        # if self.instance.status in [LabAppointment.CANCELLED, LabAppointment.COMPLETED] and len(cleaned_data):
        #     raise forms.ValidationError("Cancelled/Completed appointment cannot be modified.")


        if not cleaned_data.get('status') is LabAppointment.CANCELLED and (cleaned_data.get(
                'cancellation_reason') or cleaned_data.get('cancellation_comments')):
            raise forms.ValidationError(
                "Reason/Comment for cancellation can only be entered on cancelled appointment")

        if cleaned_data.get('status') is LabAppointment.CANCELLED and not cleaned_data.get('cancellation_reason'):
            raise forms.ValidationError("Reason for Cancelled appointment should be set.")

        if cleaned_data.get('status') is LabAppointment.CANCELLED and cleaned_data.get(
                'cancellation_reason') and 'others' in cleaned_data.get(
                'cancellation_reason').name.lower() and not cleaned_data.get('cancellation_comments'):
            raise forms.ValidationError(
                "If Reason for Cancelled appointment is others it should be mentioned in cancellation comment.")


        if not lab.lab_pricing_group:
            raise forms.ValidationError("Lab is not in any lab pricing group.")

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


class LabAppointmentAdmin(nested_admin.NestedModelAdmin):
    form = LabAppointmentForm
    list_display = ('booking_id', 'get_profile', 'get_lab', 'status', 'time_slot_start', 'created_at', 'updated_at')
    list_filter = ('status', )
    date_hierarchy = 'created_at'

    inlines = [
        LabReportInline
    ]

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
                                    (LabAppointment.CANCELLED, 'Cancelled')]
        if db_field.name == "status" and request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            kwargs['choices'] = allowed_status_for_agent
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        if obj is not None and obj.time_slot_start:
            time_slot_start = timezone.localtime(obj.time_slot_start, pytz.timezone(settings.TIME_ZONE))
            form.base_fields['start_date'].initial = time_slot_start.strftime('%Y-%m-%d') if time_slot_start else None
            form.base_fields['start_time'].initial = time_slot_start.strftime('%H:%M') if time_slot_start else None
        return form

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ('booking_id', 'order_id', 'lab', 'lab_id', 'lab_test', 'lab_contact_details', 'profile', 'user',
                    'profile_detail', 'status', 'cancel_type', 'cancellation_reason', 'cancellation_comments',
                    'price', 'agreed_price',
                    'deal_price', 'effective_price', 'start_date', 'start_time', 'otp', 'payment_status',
                    'payment_type', 'insurance', 'is_home_pickup', 'address', 'outstanding')
        elif request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('booking_id', 'order_id',  'lab_id', 'lab_name', 'get_lab_test', 'lab_contact_details',
                    'used_profile_name', 'used_profile_number',
                    'default_profile_name', 'default_profile_number', 'user_id', 'user_number', 'price', 'agreed_price',
                    'deal_price', 'effective_price', 'payment_status', 'payment_type', 'insurance', 'is_home_pickup',
                    'get_pickup_address', 'get_lab_address', 'outstanding', 'status', 'cancel_type',
                    'cancellation_reason', 'cancellation_comments', 'start_date', 'start_time')
        else:
            return ()

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ('booking_id', 'order_id', 'lab_id', 'lab_contact_details')
        elif request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('booking_id', 'order_id', 'lab_name', 'lab_id', 'get_lab_test',
                    'lab_contact_details', 'used_profile_name', 'used_profile_number',
                    'default_profile_name', 'default_profile_number', 'user_number', 'user_id', 'price', 'agreed_price',
                    'deal_price', 'effective_price', 'payment_status',
                    'payment_type', 'insurance', 'is_home_pickup', 'get_pickup_address', 'get_lab_address', 'outstanding')
        else:
            return ()

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
        for data in obj.lab_test.all():
            format_string += "<div><span>{}</span></div>".format(data.test.name)
        return format_html_join(
            mark_safe('<br/>'),
            format_string,
            ((),),
        )
    get_lab_test.short_description = 'Lab Test'

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
        if obj:
            if obj.id:
                lab_app_obj = LabAppointment.objects.select_for_update().get(pk=obj.id)
            # date = datetime.datetime.strptime(request.POST['start_date'], '%Y-%m-%d')
            # time = datetime.datetime.strptime(request.POST['start_time'], '%H:%M').time()
            #
            # date_time = datetime.datetime.combine(date, time)
            if request.POST['start_date'] and request.POST['start_time']:
                date_time_field = request.POST['start_date'] + " " + request.POST['start_time']
                to_zone = tz.gettz(settings.TIME_ZONE)
                dt_field = parse_datetime(date_time_field).replace(tzinfo=to_zone)

                if dt_field:
                    obj.time_slot_start = dt_field
            if request.POST.get('status') and (int(request.POST['status']) == LabAppointment.CANCELLED or \
                int(request.POST['status']) == LabAppointment.COMPLETED):
                obj.cancellation_type = LabAppointment.AGENT_CANCELLED
                cancel_type = int(request.POST.get('cancel_type'))
                if cancel_type is not None:
                    logger.warning("Lab Admin Cancel started - " + str(obj.id) + " timezone - " + str(timezone.now()))
                    obj.action_cancelled(cancel_type)
                    logger.warning("Lab Admin Cancel completed - " + str(obj.id) + " timezone - " + str(timezone.now()))
            else:
                super().save_model(request, obj, form, change)

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


class TestParameterAdmin(VersionAdmin):
    search_fields = ['name']


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


class LabTestToParentCategoryInlineFormset(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        all_parent_categories = []
        count_is_primary = 0
        for value in self.cleaned_data:
            if not value.get("DELETE"):
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

        # if not count_is_primary == 1:
        #     raise forms.ValidationError("Must have one and only one primary parent category.")
        # if all_parent_categories and ProcedureCategoryMapping.objects.filter(parent_category__in=all_parent_categories,
        #                                                                      child_category__in=all_parent_categories).count():
        #     raise forms.ValidationError("Some Categories are already related, so can't be added together.")
        # if any([category.related_parent_category.count() for category in
        #         all_parent_categories]):  # PROCEDURE_category_SAME_level
        #     raise forms.ValidationError("Procedure and Category can't be on same level.")


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
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        # TODO : SHASHANK_SINGH is_package toggles handling
        if cleaned_data.get('is_package', False):
            if self.instance:
                if self.instance.parent_lab_test_category_mappings.filter(parent_category__is_package_category=False).count():
                    raise forms.ValidationError("Already has lab test category as parent(s). Remove all of them and try again.")
        else:
            if self.instance:
                if self.instance.parent_lab_test_category_mappings.filter(parent_category__is_package_category=True).count():
                    raise forms.ValidationError("Already has lab test package category as parent(s). Remove all of them and try again.")


class LabTestAdmin(PackageAutoCompleteView, ImportExportMixin, VersionAdmin):
    change_list_template = 'superuser_import_export.html'
    formats = (base_formats.XLS, base_formats.XLSX,)
    inlines = [LabTestCategoryInline]
    search_fields = ['name']
    list_filter = ('is_package', 'enable_for_ppc', 'enable_for_retail')
    exclude = ['search_key']
    form = LabTestAdminForm

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj and not obj.is_package:
            return [value for value in fields if value != 'number_of_tests']
        return fields

    def get_inline_instances(self, request, obj=None):
        inline_instance = super().get_inline_instances(request=request, obj=obj)
        if obj and obj.is_package and LabTest.objects.filter(pk=obj.id, is_package=True).exists():
            inline_instance.append(LabTestPackageInline(self.model, self.admin_site))
        if obj and LabTest.objects.filter(pk=obj.id, is_package=False).exists():
            inline_instance.append(ParameterLabTestInline(self.model, self.admin_site))
        return inline_instance


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
        # TODO : SHASHANK_SINGH is_live toggles handling
        if cleaned_data.get('is_live', False) and not cleaned_data.get('is_package_category', False) \
                and not cleaned_data.get('preferred_lab_test', None):
            raise forms.ValidationError('This category cannot go live without preferred lab test.')
        if cleaned_data.get('is_live', False) and cleaned_data.get('is_package_category', False) \
                and cleaned_data.get('preferred_lab_test', None):
            raise forms.ValidationError('This category cannot have preferred lab test.')
        # TODO : SHASHANK_SINGH is_package_category toggles handling
        if cleaned_data.get('is_package_category', False):
            if self.instance:
                if self.instance.lab_test_mappings.filter(lab_test__is_package=False).count():
                    raise forms.ValidationError('This category has lab test under it, delete all of them and try again.')
        else:
            if self.instance:
                if self.instance.lab_test_mappings.filter(lab_test__is_package=True).count():
                    raise forms.ValidationError('This category has lab test package(s) under it, delete all of them and try again.')

        # procedure = cleaned_data.get('preferred_procedure', None)
        # is_live = cleaned_data.get('is_live', False)
        # if is_live and not procedure:
        #     raise forms.ValidationError('Category can\'t go live without a preferred procedure.')
        # if procedure:
        #     if self.instance.pk:
        #         all_organic_parents = procedure.categories.all().values_list('pk', flat=True)
        #         all_parents = ProcedureCategoryMapping.objects.filter(
        #             child_category__in=all_organic_parents).values_list('parent_category', flat=True)
        #         all_parents = set(all_organic_parents).union(set(all_parents))
        #         if self.instance.pk not in all_parents:
        #                 raise forms.ValidationError('Category and preferred procedure should be related.')
        #         if not procedure.categories.filter(pk=self.instance.pk).exists():  # PROCEDURE_category_SAME_level
        #             raise forms.ValidationError(
        #                 'Category should be direct parent of the preferred procedure.')
        #     else:
        #         raise forms.ValidationError('Category and preferred procedure should be related.')



class LabTestCategoryAdmin(VersionAdmin):
    # list_display = ['test', 'lab_pricing_group', 'get_type', 'mrp', 'computed_agreed_price',
    #                 'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'enabled']
    exclude = ['search_key']
    search_fields = ['name']
    form = LabTestCategoryForm


class AvailableLabTestAdmin(VersionAdmin):
    list_display = ['test', 'lab_pricing_group', 'get_type', 'mrp', 'computed_agreed_price',
                    'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'enabled']
    search_fields = ['test__name', 'lab_pricing_group__group_name', 'lab_pricing_group__labs__name']


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

