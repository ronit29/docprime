from django.contrib.gis import forms
from reversion.admin import VersionAdmin
from django.core.exceptions import FieldDoesNotExist
import datetime
from django.forms.models import BaseFormSet
from django.db.models import Q
from django.utils.safestring import mark_safe
from django.conf.urls import url
from django.shortcuts import render

from ondoc.doctor.models import (Doctor, DoctorQualification, DoctorHospital,
    DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
    DoctorMedicalService, DoctorImage, DoctorDocument, DoctorMobile, DoctorOnboardingToken,
    DoctorEmail )

from .common import *
from ondoc.crm.constants import constants

class DoctorQualificationForm(forms.ModelForm):
    passing_year = forms.ChoiceField(choices=college_passing_year_choices, required=False)

    def clean_passing_year(self):
        data = self.cleaned_data['passing_year']
        if data == '':
            return None
        return data


class DoctorQualificationInline(admin.TabularInline):
    model = DoctorQualification
    form = DoctorQualificationForm
    extra = 0
    can_delete = True
    show_change_link = False
    # autocomplete_fields = ['specialization']


class DoctorHospitalInline(admin.TabularInline):
    model = DoctorHospital
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['hospital']


class DoctorLanguageInline(admin.TabularInline):
    model = DoctorLanguage
    extra = 0
    can_delete = True
    show_change_link = False

class DoctorAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices, required=False)
    def clean_year(self):
        data = self.cleaned_data['year']
        if data == '':
            return None
        return data


class DoctorAwardInline(admin.TabularInline):
    form = DoctorAwardForm
    model = DoctorAward
    extra = 0
    can_delete = True
    show_change_link = False

class DoctorAssociationInline(admin.TabularInline):
    model = DoctorAssociation
    extra = 0
    can_delete = True
    show_change_link = False

class DoctorExperienceForm(forms.ModelForm):
    start_year = forms.ChoiceField(required=False, choices=practicing_since_choices)
    end_year = forms.ChoiceField(required=False, choices=practicing_since_choices)

class DoctorExperienceInline(admin.TabularInline):
    model = DoctorExperience
    extra = 0
    can_delete = True
    show_change_link = False
    form = DoctorExperienceForm

class DoctorMedicalServiceInline(admin.TabularInline):
    model = DoctorMedicalService
    extra = 0
    can_delete = True
    show_change_link = False
    # autocomplete_fields = ['service']


class DoctorImageInline(admin.TabularInline):
    model = DoctorImage
    template = 'imageinline.html'
    extra = 0
    can_delete = True
    show_change_link = False

class DoctorDocumentInline(admin.TabularInline):
    model = DoctorDocument
    extra = 0
    can_delete = True
    show_change_link = False


class DoctorMobileForm(forms.ModelForm):
    number = forms.CharField(required=True)
    is_primary = forms.BooleanField(required=False)
    #def is_valid(self):
    #    pass
    # def clean(self):
    #    pass

class DoctorMobileFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        primary = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('is_primary'):
                primary += 1
                
        if count>0:
            if primary==0: 
               raise forms.ValidationError("One primary number is required")
            if primary>=2:
               raise forms.ValidationError("Only one mobile number can be primary")


class DoctorMobileInline(admin.TabularInline):
    model = DoctorMobile
    form = DoctorMobileForm
    formset = DoctorMobileFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['number','is_primary']


class DoctorEmailForm(forms.ModelForm):
    email = forms.CharField(required=True)
    is_primary = forms.BooleanField(required=False)

class DoctorEmailFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        primary = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('is_primary'):
                primary += 1

        if count>0:
            if primary==0: 
               raise forms.ValidationError("One primary email is required")
            if primary>=2:
               raise forms.ValidationError("Only one email can be primary")

class DoctorEmailInline(admin.TabularInline):
    model = DoctorEmail
    form = DoctorEmailForm
    formset = DoctorEmailFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['email','is_primary']


class DoctorForm(forms.ModelForm):
    additional_details = forms.CharField(widget=forms.Textarea, required=False)
    about = forms.CharField(widget=forms.Textarea, required=False)
    # primary_mobile = forms.CharField(required=True)
    # email = forms.EmailField(required=True)
    practicing_since = forms.ChoiceField(required=False, choices=practicing_since_choices)
    onboarding_status = forms.ChoiceField(disabled=True,required=False, choices=Doctor.ONBOARDING_STATUS)
    def validate_qc(self):
        qc_required = {'name':'req','gender':'req','practicing_since':'req',
        'about':'req','license':'req','mobiles':'count','emails':'count',
        'qualifications':'count','availability':'count','languages':'count',
        'images':'count'}
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")

    def clean_practicing_since(self):
        data = self.cleaned_data['practicing_since']
        if data == '':
            return None
        return data

    def clean(self):
        if not self.request.user.is_superuser:
            if self.instance.data_status == 3:
                raise forms.ValidationError("Cannot modify QC approved Data")
            if self.instance.data_status == 2 and not self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() :
                raise forms.ValidationError("Cannot modify QC submitted Data")

            if '_submit_for_qc' in self.data:
                self.validate_qc()
                for h in self.instance.hospitals.all():
                    if(h.data_status < 2):
                        raise forms.ValidationError("Cannot submit for QC without submitting associated Hospitals: " + h.name)

            if '_qc_approve' in self.data:
                self.validate_qc()
                for h in self.instance.hospitals.all():
                    if(h.data_status < 3):
                        raise forms.ValidationError("Cannot approve QC check without approving associated Hospitals: " + h.name)

            if '_mark_in_progress' in self.data:
                if self.instance.data_status == 3:
                    raise forms.ValidationError("Cannot reject QC approved data")

        return super(DoctorForm, self).clean()


class DoctorAdmin(VersionAdmin, ActionAdmin):

    change_form_template = 'custom_change_form.html'

    list_display = ('name', 'updated_at','data_status', 'created_by','get_onboard_link')
    date_hierarchy = 'created_at'
    list_filter = ('data_status',)
    form = DoctorForm
    inlines = [
        DoctorMobileInline,
        DoctorEmailInline,
        DoctorQualificationInline,
        DoctorHospitalInline,
        DoctorLanguageInline,
        DoctorAwardInline,
        DoctorAssociationInline,
        DoctorExperienceInline,
        DoctorMedicalServiceInline,
        DoctorImageInline,
        DoctorDocumentInline
    ]
    exclude = ['created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code']
    search_fields = ['name']

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url('onboard_admin/(?P<userid>\d+)/', self.admin_site.admin_view(self.onboarddoctor_admin), name="onboarddoctor_admin"),
        ]
        return my_urls + urls

    def onboarddoctor_admin(self, request, userid):
        host = request.get_host()
        try:
            doctor = Doctor.objects.get(id = userid)
        except Exception as e:
            return HttpResponse('invalid doctor')

        count = 0
        try:
            count = DoctorOnboardingToken.objects.filter(doctor = doctor).count()
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
        required = ['name','about','gender','license','practicing_since']
        for req in required:
            if not getattr(doctor, req):
                errors.append(req+' is required')

        
        length_required = ['mobiles','emails','qualifications','hospitals',
             'languages','experiences','images']

        for req in length_required:
            if not len(getattr(doctor, req).all()):
                errors.append(req + ' is required')

        return render(request, 'onboarddoctor.html', {'doctor': doctor, 'count': count, 'errors': errors})

    def get_onboard_link(self, obj = None):
        if obj.data_status == Doctor.IN_PROGRESS and obj.onboarding_status in (Doctor.NOT_ONBOARDED, Doctor.REQUEST_SENT):
            return mark_safe("<a href='/admin/doctor/doctor/onboard_admin/%s'>generate onboarding url</a>" % obj.id)
        return ""

    def get_form(self, request, obj=None, **kwargs):
        form = super(DoctorAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        return form

    def save_formset(self, request, form, formset, change):
        for form in formset.forms:
            try:
                form.instance._meta.get_field('created_by')
                if not form.instance.created_by:
                    form.instance.created_by = request.user
            except FieldDoesNotExist:
                pass

        formset.save()

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            return qs.filter(Q(data_status=2) | Q(data_status=3))
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return qs.filter(created_by=request.user )

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

    def has_change_permission(self, request, obj=None):
        if not obj:
            # the changelist itself
            return True

        if request.user.is_superuser and request.user.is_staff:
            return True
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() and obj.data_status in (2, 3):
            return True

        return obj.created_by == request.user

    class Media:
        js = ('js/admin/ondoc.js',)


class SpecializationAdmin(VersionAdmin):
    search_fields = ['name']


class QualificationAdmin(VersionAdmin):
    search_fields = ['name']


class MedicalServiceAdmin(VersionAdmin):
    search_fields = ['name']

class LanguageAdmin(VersionAdmin):
    search_fields = ['name']


class CollegeAdmin(VersionAdmin):
    search_fields = ['name']
