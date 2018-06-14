from django.shortcuts import render, HttpResponse, HttpResponseRedirect, redirect
from django.conf.urls import url
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats
from django.urls import include, path, reverse
from django.utils.safestring import mark_safe
from django.contrib.gis import forms
from django.contrib.gis import admin
from django.contrib.admin import SimpleListFilter
from reversion.admin import VersionAdmin
from django.db.models import Q
from django.db import models

from ondoc.doctor.models import Hospital
from ondoc.diagnostic.models import (LabTiming, LabImage,
    LabManager,LabAccreditation, LabAward, LabCertification,
    LabNetwork, Lab, LabOnboardingToken, LabService,LabDoctorAvailability,
    LabDoctor, LabDocument, LabTest, LabTestSubType, LabTestSubTypeMapping)
from .common import *


class LabTestResource(resources.ModelResource):
    excel_id = fields.Field(attribute='excel_id', column_name='Test ID')
    test_type = fields.Field(attribute='test_type', column_name='Test Type')
    sub_type = fields.Field(attribute='sub_type', column_name='Test SubType')
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

    class Meta:
        model = LabTest

    def before_save_instance(self, instance, using_transactions, dry_run):
        instance.test_type = (LabTest.RADIOLOGY if instance.test_type.strip() == 'Radiology'
                              else LabTest.PATHOLOGY) if instance.test_type else None
        instance.is_package = (True if instance.is_package.strip() == "Yes" else False) if instance.is_package else False
        instance.excel_id = instance.excel_id.strip() if instance.excel_id else ""
        instance.sub_type = instance.sub_type.strip().lower() if instance.sub_type else ""
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
        super().before_save_instance(instance, using_transactions, dry_run)

    def after_save_instance(self, instance, using_transactions, dry_run):
        sub_type = instance.sub_type.strip().split(",")
        for sub_type_name in sub_type:
            obj, created = LabTestSubType.objects.get_or_create(name=sub_type_name.strip())
            LabTestSubTypeMapping.objects.get_or_create(lab_test=instance,
                                                        test_sub_type=obj)


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


class LabManagerInline(admin.TabularInline):
    model = LabManager
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
    #form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False

# class LabDocumentForm(forms.ModelForm):
#     name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))


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

        if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
            for key, value in count.items():
                if not key==LabDocument.GST and value<1:
                    raise forms.ValidationError(choices[key]+" is required")



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
    onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Lab.ONBOARDING_STATUS)
    # agreed_rate_list = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'application/pdf'}))

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data


    def validate_qc(self):
        qc_required = {'name':'req','location':'req','operational_since':'req','parking':'req',
            'license':'req','building':'req','locality':'req','city':'req','state':'req',
            'country':'req','pin_code':'req','network_type':'req','lab_image':'count'}
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type']==2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Lab")


class LabCityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'city'
    def lookups(self, request, model_admin):
        cities = set([(c['city'].upper(),c['city'].upper()) if(c.get('city')) else ('','') for c in Lab.objects.values('city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(city__iexact=self.value()).distinct()

class LabAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):
    list_display = ('name', 'updated_at','onboarding_status','data_status', 'list_created_by', 'get_onboard_link',)
    # readonly_fields=('onboarding_status', )
    list_filter = ('data_status','onboarding_status',LabCityFilter)

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url('onboardlab_admin/(?P<userid>\d+)/', self.admin_site.admin_view(self.onboardlab_admin), name="onboardlab_admin"),
        ]
        return my_urls + urls

    def onboardlab_admin(self, request, userid):
        host = request.get_host()
        try:
            lab_obj = Lab.objects.get(id = userid)
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
        required = ['name','about','license','primary_email','primary_mobile','operational_since', 'parking', 'network_type', 'location','building','city','state','country','pin_code','agreed_rate_list']
        for req in required:
            if not getattr(lab_obj, req):
                errors.append(req+' is required')

        if not lab_obj.locality and not lab_obj.sublocality:
            errors.append('locality or sublocality is required')

        length_required = ['labservice', 'labdoctoravailability', 'labmanager', 'labtiming', 'labaccreditation']
        if lab_obj.labservice_set.filter(service = LabService.RADIOLOGY).exists():
            length_required.append('labdoctor')
        for req in length_required:
            if not len(getattr(lab_obj, req+'_set').all()):
                errors.append(req + ' is required')

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
        if '_submit_for_qc' in request.POST:
            obj.data_status = 2
        if '_qc_approve' in request.POST:
            obj.data_status = 3
        if '_mark_in_progress' in request.POST:
            obj.data_status = 1

        super().save_model(request, obj, form, change)



    def get_form(self, request, obj=None, **kwargs):
        form = super(LabAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['network'].queryset = LabNetwork.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        form.base_fields['hospital'].queryset = Hospital.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        return form

    form = LabForm
    search_fields = ['name']
    inlines = [LabDoctorInline, LabServiceInline, LabDoctorAvailabilityInline, LabCertificationInline, LabAwardInline, LabAccreditationInline,
        LabManagerInline, LabTimingInline, LabImageInline, LabDocumentInline]

    map_width = 200
    map_template = 'admin/gis/gmap.html'

    class Media:
        js = ('js/admin/ondoc.js',)

    # extra_js = ['js/admin/GoogleMap.js','https://maps.googleapis.com/maps/api/js?key=AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA&callback=initGoogleMap']
    # extra_js = ['https://maps.googleapis.com/maps/api/js?key=AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA&libraries=places&callback=initMap']


class LabTestAdmin(ImportMixin, VersionAdmin):
    change_list_template = 'change_list_import.html'
    formats = (base_formats.XLS, base_formats.XLSX,)
    search_fields = ['name']
    resource_class = LabTestResource


class LabTestTypeAdmin(VersionAdmin):
    search_fields = ['name']


class LabSubTestTypeAdmin(VersionAdmin):
    search_fields = ['name']


class AvailableLabTestAdmin(VersionAdmin):
    search_fields = ['name']
