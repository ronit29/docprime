from django.shortcuts import render, HttpResponse, HttpResponseRedirect, redirect
from django.conf.urls import url
from django.urls import include, path, reverse
from django.utils.safestring import mark_safe
from django.contrib.gis import forms
from django.contrib.gis import admin
from reversion.admin import VersionAdmin
from django.db.models import Q
from django.db import models

from ondoc.doctor.models import Hospital
from ondoc.diagnostic.models import (LabTiming, LabImage,
    LabManager,LabAccreditation, LabAward, LabCertification,
    LabNetwork, Lab, LabOnboardingToken, LabService,LabDoctorAvailability,
    LabDoctor, LabDocument)
from .common import *


class LabTimingInline(admin.TabularInline):
    model = LabTiming
    extra = 0
    can_delete = True
    show_change_link = False


class LabImageInline(admin.TabularInline):
    model = LabImage   
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

class LabDocumentInline(admin.TabularInline):
    model = LabDocument
    #form = LabAwardForm
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


class LabForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea, required=False)
    primary_mobile = forms.CharField(required=True)
    primary_email = forms.EmailField(required=True)
    city = forms.CharField(required=True)
    operational_since = forms.ChoiceField(required=False, choices=hospital_operational_since_choices)
    onboarding_status = forms.ChoiceField(disabled=True,required=False, choices=Lab.ONBOARDING_STATUS)

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data


    def validate_qc(self):
        qc_required = {'name':'req','location':'req','operational_since':'req','parking':'req',
            'license':'req','building':'req','locality':'req','city':'req','state':'req',
            'country':'req','pin_code':'req','network_type':'req','labimage':'count'}
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'_set-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type']==2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Lab")


    def clean(self):
        if not self.request.user.is_superuser:
            if self.instance.data_status == 3:
                raise forms.ValidationError("Cannot update QC approved Lab")

            if self.instance.data_status == 2 and not self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
                raise forms.ValidationError("Cannot update Lab submitted for QC approval")

            if self.instance.data_status == 1 and self.instance.created_by and self.instance.created_by != self.request.user:
                raise forms.ValidationError("Cannot modify Lab added by other users")


            if '_submit_for_qc' in self.data:
                self.validate_qc()
                if self.instance.network and self.instance.network.data_status <2:
                    raise forms.ValidationError("Cannot submit for QC without submitting associated Lab Network: " + self.instance.network.name)

            if '_qc_approve' in self.data:
                self.validate_qc()
                if self.instance.network and  self.instance.network.data_status < 3:
                    raise forms.ValidationError("Cannot approve QC check without approving associated Lab Network: " + self.instance.network.name)

            if '_mark_in_progress' in self.data:
                if self.instance.data_status == 3:
                    raise forms.ValidationError("Cannot reject QC approved data")

        return super(LabForm, self).clean()


class LabAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin):
    change_form_template = 'custom_change_form.html'
    list_display = ('name', 'updated_at','onboarding_status','data_status', 'created_by', 'get_onboard_link',)
    # readonly_fields=('onboarding_status', )


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

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            return qs.filter(Q(data_status=2) | Q(data_status=3))
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return qs.filter(created_by=request.user )

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

class PathologyTestAdmin(VersionAdmin):
    search_fields = ['name']

class RadiologyTestAdmin(VersionAdmin):
    search_fields = ['name']

class RadiologyTestTypeAdmin(VersionAdmin):
    search_fields = ['name']

class PathologyTestTypeAdmin(VersionAdmin):
    search_fields = ['name']
