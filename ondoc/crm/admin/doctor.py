from django.contrib.gis.db import models
from django.contrib.gis import forms
from reversion.admin import VersionAdmin
from django.core.exceptions import FieldDoesNotExist
import datetime
from django.forms.models import BaseFormSet
from django.db.models import Q
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.conf.urls import url
from django.shortcuts import render
from import_export.admin import ImportExportMixin
from import_export import fields, resources

from ondoc.doctor.models import (Doctor, DoctorQualification, DoctorHospital,
    DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience, MedicalConditionSpecialization,
    DoctorMedicalService, DoctorImage, DoctorDocument, DoctorMobile, DoctorOnboardingToken,
    DoctorEmail, College, DoctorSpecialization, GeneralSpecialization, Specialization, Qualification, Language)
from .filters import RelatedDropdownFilter
from ondoc.authentication.models import User
from .common import *
from .autocomplete import CustomAutoComplete
from ondoc.crm.constants import constants

class AutoComplete:
    def autocomplete_view(self, request):
        return CustomAutoComplete.as_view(model_admin=self)(request)


class DoctorQualificationForm(forms.ModelForm):
    passing_year = forms.ChoiceField(choices=college_passing_year_choices, required=False)

    def clean_passing_year(self):
        data = self.cleaned_data['passing_year']
        if data == '':
            return None
        return data


class DoctorQualificationFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        doctor = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('doctor'):
                doctor += 1

        if count > 0:
            if not doctor:
                raise forms.ValidationError("Atleast one Qualification is required")


class DoctorQualificationInline(admin.TabularInline):
    model = DoctorQualification
    form = DoctorQualificationForm
    formset = DoctorQualificationFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['college']


class DoctorHospitalForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        fees = cleaned_data.get("fees")
        mrp = cleaned_data.get("mrp")

        if start and end and start>=end:
            raise forms.ValidationError("Availability start time should be less than end time")
        if mrp and mrp < fees:
            raise forms.ValidationError("MRP cannot be less than fees")

class DoctorHospitalFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        hospital = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('hospital'):
                hospital += 1

        if count > 0:
            if not hospital:
                raise forms.ValidationError("Atleast one Hospital is required")


class DoctorHospitalInline(admin.TabularInline):
    model = DoctorHospital
    form = DoctorHospitalForm
    formset = DoctorHospitalFormSet
    extra = 0
    # min_num = 1
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['hospital']
    readonly_fields = ['deal_price']


class DoctorLanguageFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        language = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('language'):
                language += 1

        if count > 0:
            if not language:
                raise forms.ValidationError("Atleast one language is required")


class DoctorLanguageInline(admin.TabularInline):
    model = DoctorLanguage
    formset = DoctorLanguageFormSet
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

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_year")
        end = cleaned_data.get("end_year")
        if start and end and start >= end:
            raise forms.ValidationError("Start Year should be less than end Year")



class DoctorExperienceFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        hospital = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('hospital'):
                hospital += 1

        if count > 0:
            if not hospital:
                raise forms.ValidationError("Atleast one Experience is required")


class DoctorExperienceInline(admin.TabularInline):
    model = DoctorExperience
    formset = DoctorExperienceFormSet
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

# class DoctorImageForm(forms.ModelForm):
#     name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))


class DoctorImageFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        name = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('name'):
                name += 1

        if count > 0:
            if not name:
                raise forms.ValidationError("Atleast one Image is required")


class DoctorImageInline(admin.TabularInline):
    model = DoctorImage
    formset = DoctorImageFormSet
    template = 'imageinline.html'
    extra = 0
    can_delete = True
    show_change_link = False

# class DoctorDocumentForm(forms.ModelForm):
#     pass
    # name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))
    # class Meta:
    #     Model = DoctorDocument

class DoctorDocumentFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        choices = dict(DoctorDocument.CHOICES)
        count = {}
        for key, value in DoctorDocument.CHOICES:
            count[key] = 0

        for value in self.cleaned_data:
            if value and not value['DELETE']:
                count[value['document_type']] += 1

        for key, value in count.items():
            if not key==DoctorDocument.ADDRESS and value>1:
                raise forms.ValidationError("Only one "+choices[key]+" is allowed")

        if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
            for key, value in count.items():
                if not key==DoctorDocument.GST and value<1:
                    raise forms.ValidationError(choices[key]+" is required")


class DoctorDocumentInline(admin.TabularInline):
    formset = DoctorDocumentFormSet

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

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
        if any(self.errors):
            return

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
        if any(self.errors):
            return
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


class DoctorForm(FormCleanMixin):
    additional_details = forms.CharField(widget=forms.Textarea, required=False)
    about = forms.CharField(widget=forms.Textarea, required=False)
    # primary_mobile = forms.CharField(required=True)
    # email = forms.EmailField(required=True)
    practicing_since = forms.ChoiceField(required=False, choices=practicing_since_choices)
    onboarding_status = forms.ChoiceField(disabled=True,required=False, choices=Doctor.ONBOARDING_STATUS)
    def validate_qc(self):
        qc_required = {'name':'req', 'gender':'req','practicing_since':'req',
        'about':'req','license':'req','mobiles':'count','emails':'count',
        'qualifications':'count', 'availability': 'count', 'languages':'count',
        'images':'count','documents':'count','doctorspecializations':'count'}
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value == 'count' and int(self.data[key+'-TOTAL_FORMS']) <= 0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")

    def clean_practicing_since(self):
        data = self.cleaned_data['practicing_since']
        if data == '':
            return None
        return data

class CityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'hospitals__city'
    def lookups(self, request, model_admin):
        cities = set([(c['hospitals__city'].upper(), c['hospitals__city'].upper()) if(c.get('hospitals__city')) else ('','') for c in Doctor.objects.all().values('hospitals__city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(hospitals__city__iexact=self.value()).distinct()


class DoctorSpecializationInline(admin.TabularInline):
    model = DoctorSpecialization
    extra = 0
    can_delete = True
    show_change_link = False
    min_num = 0
    max_num = 4
    autocomplete_fields = ['specialization']


class DoctorResource(resources.ModelResource):
    city = fields.Field()
    class Meta:
        model = Doctor
        fields = ('id', 'name', 'city','gender', 'onboarding_status', 'data_status')
        export_order = ('id', 'name', 'city', 'gender', 'onboarding_status', 'data_status')

    def dehydrate_data_status(self, doctor):
        return dict(Doctor.DATA_STATUS_CHOICES)[doctor.data_status]
    def dehydrate_onboarding_status(self, doctor):
        return dict(Doctor.ONBOARDING_STATUS)[doctor.onboarding_status]
    def dehydrate_city(self, doctor):
        return ','.join([str(h.city) for h in doctor.hospitals.distinct('city')])


class DoctorAdmin(ImportExportMixin, VersionAdmin, ActionAdmin, QCPemAdmin):
    resource_class = DoctorResource
    change_list_template = 'superuser_import_export.html'

    list_display = ('name', 'updated_at', 'data_status', 'onboarding_status', 'list_created_by', 'list_assigned_to', 'get_onboard_link')
    date_hierarchy = 'created_at'
    list_filter = ('data_status','onboarding_status', CityFilter,)
    form = DoctorForm
    inlines = [
        DoctorMobileInline,
        DoctorEmailInline,
        DoctorSpecializationInline,
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
    exclude = ['user', 'created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code']
    search_fields = ['name']

    readonly_fields = ('lead_url','matrix_lead_id','matrix_reference_id')

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
            url('onboard_admin/(?P<userid>\d+)/', self.admin_site.admin_view(self.onboarddoctor_admin), name="onboarddoctor_admin"),
        ]
        return my_urls + urls

    def onboarddoctor_admin(self, request, userid):
        host = request.get_host()
        try:
            doctor = Doctor.objects.get(id=userid)
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
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if (not request.user.is_superuser) and (not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists()):
            form.base_fields['assigned_to'].disabled = True
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

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if not obj.assigned_to:
            obj.assigned_to = request.user
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
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() and obj.data_status in (1, 2, 3):
            return True
        return obj.created_by == request.user

    class Media:
        js = ('js/admin/ondoc.js',)

class SpecializationResource(resources.ModelResource):

    class Meta:
        model = Specialization
        fields = ('id','name','human_readable_name')


class CollegeResource(resources.ModelResource):

    class Meta:
        model = College
        fields = ('id','name')


class LanguageResource(resources.ModelResource):

    class Meta:
        model = Language
        fields = ('id','name')


class QualificationResource(resources.ModelResource):

    class Meta:
        model = Qualification
        fields = ('id','name')


class GeneralSpecializationResource(resources.ModelResource):

    class Meta:
        model = GeneralSpecialization
        fields = ('id','name')


class SpecializationAdmin(AutoComplete, ImportExportMixin, VersionAdmin):
    search_fields = ['name']
    resource_class = SpecializationResource
    change_list_template = 'superuser_import_export.html'


class GeneralSpecializationAdmin(AutoComplete, ImportExportMixin, VersionAdmin):
    search_fields = ['name']
    resource_class = GeneralSpecializationResource
    change_list_template = 'superuser_import_export.html'


class QualificationAdmin(AutoComplete, ImportExportMixin, VersionAdmin):
    search_fields = ['name']
    resource_class = QualificationResource
    change_list_template = 'superuser_import_export.html'


class MedicalServiceAdmin(VersionAdmin):
    search_fields = ['name']


class LanguageAdmin(ImportExportMixin, VersionAdmin):
    search_fields = ['name']
    resource_class = LanguageResource
    change_list_template = 'superuser_import_export.html'


class CollegeAdmin(AutoComplete, ImportExportMixin, VersionAdmin):
    search_fields = ['name']
    resource_class = CollegeResource
    change_list_template = 'superuser_import_export.html'


class MedicalConditionSpecializationInline(admin.TabularInline):
    model = MedicalConditionSpecialization
    extra = 0
    can_delete = True
    min_num = 0
    autocomplete_fields = ['specialization']


class MedicalConditionAdmin(VersionAdmin):
    list_display = ('name', 'updated_at',)
    date_hierarchy = 'created_at'
    inlines = [
        MedicalConditionSpecializationInline
    ]
    search_fields = ['name']

