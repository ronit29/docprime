from reversion.admin import VersionAdmin
from django.core.exceptions import FieldDoesNotExist, MultipleObjectsReturned
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.conf.urls import url
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Q
from import_export.fields import Field
from import_export.admin import ImportExportMixin, ImportExportModelAdmin
from import_export import fields, resources
from django.utils.dateparse import parse_datetime
from django.utils.timezone import make_aware
from dateutil import tz
from django.conf import settings
from django.utils import timezone
import pytz
import datetime
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


from ondoc.account.models import Order
from django.contrib.contenttypes.admin import GenericTabularInline
from ondoc.authentication.models import GenericAdmin, BillingAccount
from ondoc.authentication.admin import BillingAccountInline
from ondoc.doctor.models import (Doctor, DoctorQualification,
                                 DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
                                 MedicalConditionSpecialization, DoctorMedicalService, DoctorImage,
                                 DoctorDocument, DoctorMobile, DoctorOnboardingToken, Hospital,
                                 DoctorEmail, College,
                                 Specialization, Qualification, Language, DoctorClinic, DoctorClinicTiming,
                                 DoctorMapping, HospitalDocument, HospitalNetworkDocument, HospitalNetwork,
                                 OpdAppointment, CompetitorInfo, SpecializationDepartment,
                                 SpecializationField, PracticeSpecialization, SpecializationDepartmentMapping,
                                 DoctorPracticeSpecialization, CompetitorMonthlyVisit, DoctorClinicProcedure, Procedure)
from ondoc.authentication.models import User
from .common import *
from .autocomplete import CustomAutoComplete
from ondoc.crm.constants import constants
from django.utils.html import format_html_join
from django.template.loader import render_to_string
import nested_admin
from django.contrib.admin.widgets import AdminSplitDateTime
from ondoc.authentication import models as auth_model
from django import forms

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


class DoctorQualificationInline(nested_admin.NestedTabularInline):
    model = DoctorQualification
    form = DoctorQualificationForm
    formset = DoctorQualificationFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['college']


class DoctorClinicTimingForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        if any(self.errors):
            return
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        fees = cleaned_data.get("fees")
        mrp = cleaned_data.get("mrp")

        if start and end and start >= end:
            raise forms.ValidationError("Availability start time should be less than end time")
        if mrp and mrp < fees:
            raise forms.ValidationError("MRP cannot be less than fees")


class DoctorClinicFormSet(forms.BaseInlineFormSet):
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


class DoctorClinicTimingFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        temp = set()

        for value in self.cleaned_data:
            if not value.get("DELETE"):
                t = tuple([value.get("day"), value.get("start"), value.get("end")])
                if t not in temp:
                    temp.add(t)
                else:
                    raise forms.ValidationError("Duplicate records not allowed.")


class DoctorClinicProcedureInline(nested_admin.NestedTabularInline):
    model = DoctorClinicProcedure
    extra = 0
    can_delete = True
    show_change_link = False
    verbose_name = 'Procedure'
    verbose_name_plural = 'Procedures'
    autocomplete_fields = ['procedure']


class DoctorClinicTimingInline(nested_admin.NestedTabularInline):
    model = DoctorClinicTiming
    form = DoctorClinicTimingForm
    formset = DoctorClinicTimingFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    readonly_fields = ['deal_price']


class DoctorClinicInline(nested_admin.NestedTabularInline):
    model = DoctorClinic
    extra = 0
    can_delete = True
    formset = DoctorClinicFormSet
    show_change_link = False
    autocomplete_fields = ['hospital']
    inlines = [DoctorClinicTimingInline, DoctorClinicProcedureInline]

    def get_queryset(self, request):
        return super(DoctorClinicInline, self).get_queryset(request).select_related('hospital')


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


class DoctorLanguageInline(nested_admin.NestedTabularInline):
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


class DoctorAwardInline(nested_admin.NestedTabularInline):
    form = DoctorAwardForm
    model = DoctorAward
    extra = 0
    can_delete = True
    show_change_link = False


class DoctorAssociationInline(nested_admin.NestedTabularInline):
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


class DoctorExperienceInline(nested_admin.NestedTabularInline):
    model = DoctorExperience
    formset = DoctorExperienceFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    form = DoctorExperienceForm


class DoctorMedicalServiceInline(nested_admin.NestedTabularInline):
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


class DoctorImageInline(nested_admin.NestedTabularInline):
    model = DoctorImage
    # formset = DoctorImageFormSet
    template = 'imageinline.html'
    extra = 0
    can_delete = True
    show_change_link = False
    readonly_fields = ['cropped_image']


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
            if not key == DoctorDocument.ADDRESS and value > 1:
                raise forms.ValidationError("Only one " + choices[key] + " is allowed")

        if DoctorClinic.objects.filter(
                Q(hospital__network__is_billing_enabled=False, hospital__is_billing_enabled=False, doctor=self.instance)|
                Q(hospital__network__isnull=True, hospital__is_billing_enabled=False, doctor=self.instance)).exists():
            if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
                for key, value in count.items():
                    if key == DoctorDocument.REGISTRATION and value < 1:
                        pass
                        #raise forms.ValidationError(choices[key] + " is required")


class HospitalDocumentFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        choices = dict(HospitalDocument.CHOICES)
        count = {}
        for key, value in HospitalDocument.CHOICES:
            count[key] = 0

        for value in self.cleaned_data:
            if value and not value['DELETE']:
                count[value['document_type']] += 1

        for key, value in count.items():
            if not key == HospitalDocument.ADDRESS and value > 1:
                raise forms.ValidationError("Only one " + choices[key] + " is allowed")
        #
        # if (
        #         not self.instance.network or not self.instance.network.is_billing_enabled) and self.instance.is_billing_enabled:
        #     if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
        #         for key, value in count.items():
        #             if not key == HospitalDocument.GST and value < 1:
        #                 raise forms.ValidationError(choices[key] + " is required")


class DoctorDocumentInline(nested_admin.NestedTabularInline):
    formset = DoctorDocumentFormSet

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

    model = DoctorDocument
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalDocumentInline(admin.TabularInline):
    formset = HospitalDocumentFormSet

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

    model = HospitalDocument
    extra = 0
    can_delete = True
    show_change_link = False


class DoctorMobileForm(forms.ModelForm):
    number = forms.CharField(required=True)
    is_primary = forms.BooleanField(required=False)

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        std_code = data.get('std_code')
        number = data.get('number')
        if std_code:
            try:
                std_code=int(std_code)
            except:
                raise forms.ValidationError("Invalid STD code")

        try:
            number=int(number)
        except:
            raise forms.ValidationError("Invalid Number")

        if std_code:
            if data.get('is_primary'):
                raise forms.ValidationError("Primary number should be a mobile number")
        else:
            if number and (number<5000000000 or number>9999999999):
                raise forms.ValidationError("Invalid mobile number")


# class DoctorMobileFormSet(forms.BaseInlineFormSet):
#     def clean(self):
#         super().clean()
#         if any(self.errors):
#             return
#
#         primary = 0
#         count = 0
#         for value in self.cleaned_data:
#             count += 1
#             if value.get('is_primary'):
#                 primary += 1
#
#         if count > 0:
#             if not primary == 1:
#                 raise forms.ValidationError("Doctor must have one primary mobile number.")


class DoctorMobileInline(nested_admin.NestedTabularInline):
    model = DoctorMobile
    form = DoctorMobileForm
    # formset = DoctorMobileFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['std_code','number', 'is_primary']


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

        if count > 0:
            if primary == 0:
                raise forms.ValidationError("One primary email is required")
            if primary >= 2:
                raise forms.ValidationError("Only one email can be primary")


class DoctorEmailInline(nested_admin.NestedTabularInline):
    model = DoctorEmail
    form = DoctorEmailForm
    formset = DoctorEmailFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['email', 'is_primary']


class DoctorForm(FormCleanMixin):
    additional_details = forms.CharField(widget=forms.Textarea, required=False)
    raw_about = forms.CharField(widget=forms.Textarea, required=False)
    # primary_mobile = forms.CharField(required=True)
    # email = forms.EmailField(required=True)
    practicing_since = forms.ChoiceField(required=False, choices=practicing_since_choices)
    # onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Doctor.ONBOARDING_STATUS)

    def validate_qc(self):
        qc_required = {'name': 'req', 'gender': 'req', 'practicing_since': 'req',
                       'license': 'req', 'emails': 'count',
                       'qualifications': 'count', 'doctor_clinics': 'count', 'languages': 'count',
                       'doctorpracticespecializations': 'count'}

        # Q(hospital__is_billing_enabled=False, doctor=self.instance) &&
        # (network is null or network billing is false)

        # if DoctorClinic.objects.filter(
        #         Q(hospital__network__is_billing_enabled=False, hospital__is_billing_enabled=False, doctor=self.instance)|
        #         Q(hospital__network__isnull=True, hospital__is_billing_enabled=False, doctor=self.instance)).exists():
        #     qc_required.update({
        #         'documents': 'count'
        #     })

        for key, value in qc_required.items():
            if value == 'req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key + " is required for Quality Check")
            if value == 'count' and int(self.data[key + '-TOTAL_FORMS']) <= 0:
                raise forms.ValidationError("Atleast one entry of " + key + " is required for Quality Check")

    def clean_practicing_since(self):
        data = self.cleaned_data['practicing_since']
        if data == '':
            return None
        return data


class CityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'hospitals__city'

    def lookups(self, request, model_admin):
        cities = set(
            [(c['hospitals__city'].upper(), c['hospitals__city'].upper()) if (c.get('hospitals__city')) else ('', '')
             for c in Doctor.objects.all().values('hospitals__city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(hospitals__city__iexact=self.value()).distinct()


class CreatedByFilter(SimpleListFilter):
    title = 'creating user'
    parameter_name = 'created_by'

    def lookups(self, request, model_admin):
        return ('0', 'Me',),

    def queryset(self, request, queryset):
        if self.value() is '0':
            queryset = queryset.filter(created_by=request.user)
        return queryset


class DoctorPracticeSpecializationInline(nested_admin.NestedTabularInline):
    model = DoctorPracticeSpecialization
    extra = 0
    can_delete = True
    show_change_link = False
    min_num = 0
    max_num = 4
    autocomplete_fields = ['specialization']


class GenericAdminFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()


class GenericAdminInline(nested_admin.NestedTabularInline):
    model = GenericAdmin
    extra = 0
    formset = GenericAdminFormSet
    # can_delete = True
    show_change_link = False
    exclude = ('hospital_network', 'super_user_permission')
    verbose_name_plural = "Admins"

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        else:
            return False

    def has_add_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        else:
            return False

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return ['phone_number', 'is_disabled', 'write_permission', 'read_permission', 'hospital',  'permission_type',
                    'user', 'is_doc_admin']
        else:
            return ['user']

    def get_queryset(self, request):
        return super(GenericAdminInline, self).get_queryset(request).select_related('doctor', 'hospital', 'user')

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        if request.user.is_superuser:
            if not request.POST:
                if obj is not None:
                    try:
                        formset.form.base_fields['hospital'].queryset = Hospital.objects.filter(
                            assoc_doctors=obj).distinct()
                    except MultipleObjectsReturned:
                        pass
        return formset



class CroppedImageNullFilter(SimpleListFilter):
    title = 'CroppedImage'
    parameter_name = 'cropped_image'

    def lookups(self, request, model_admin):
        return (('1', 'Not NuLL',),
                ('0', 'NuLL',),
               )

    def queryset(self, request, queryset):
        if self.value() in ('0', '1'):
            if self.value() == '1':
                queryset = queryset.exclude(Q(cropped_image='') | Q(cropped_image=None))
            else:
                queryset = queryset.filter(cropped_image__exact='')

        return queryset


class DoctorImageAdmin(admin.ModelAdmin):
    model = DoctorImage
    readonly_fields = ('original_image', 'cropped_img', 'crop_image', 'doctor',)
    fields = ('original_image', 'cropped_img', 'crop_image', 'doctor')
    list_filter = ('doctor__data_status', CroppedImageNullFilter)

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if not obj:
            return True

        if request.user.is_superuser and request.user.is_staff:
            return True

        if request.user.groups.filter(
                name__in=[constants['DOCTOR_IMAGE_CROPPING_TEAM'], constants['DOCTOR_NETWORK_GROUP_NAME']]).exists():
            return True
        return True

    def crop_image(self, instance):
        return render_to_string('doctor/crop_doctor_image.html', context={"instance": instance})


class DoctorResource(resources.ModelResource):
    city = fields.Field()
    specialization = fields.Field()
    qualification = fields.Field()
    pan = fields.Field()
    gst = fields.Field()
    mci = fields.Field()
    cheque = fields.Field()
    aadhar = fields.Field()
    fees = fields.Field()

    # def export(self, queryset=None, *args, **kwargs):
    #     queryset = self.get_queryset()
    #     return super().export(queryset, *args, **kwargs)

    def export(self, queryset=None):
        queryset = self.get_queryset()
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self):
        return Doctor.objects.all().prefetch_related('hospitals', 'doctorpracticespecializations', 'qualifications',
                                                     'doctorpracticespecializations__specialization',
                                                     'qualifications__qualification',
                                                     'doctor_clinics__hospital',
                                                     'doctor_clinics__availability',
                                                     'documents')

    class Meta:
        model = Doctor
        fields = ('id', 'name', 'city', 'gender', 'license', 'fees', 'qualification', 'specialization',
                  'onboarding_status', 'data_status', 'gst', 'pan', 'mci', 'cheque', 'aadhar')
        export_order = ('id', 'name', 'city', 'gender', 'license', 'fees', 'qualification',
                        'specialization', 'onboarding_status', 'data_status', 'gst',
                        'pan', 'mci', 'cheque', 'aadhar')

    def dehydrate_data_status(self, doctor):
        return dict(Doctor.DATA_STATUS_CHOICES)[doctor.data_status]

    def dehydrate_onboarding_status(self, doctor):
        return dict(Doctor.ONBOARDING_STATUS)[doctor.onboarding_status]

    def dehydrate_city(self, doctor):
        return ','.join({str(h.city) for h in doctor.hospitals.all()})

    def dehydrate_specialization(self, doctor):
        return ','.join([str(h.specialization.name) for h in doctor.doctorpracticespecializations.all()])

    def dehydrate_qualification(self, doctor):
        return ','.join([str(h.qualification) for h in doctor.qualifications.all()])

    def dehydrate_fees(self, doctor):
        return ', '.join(
            [str(h.hospital.name + '-Rs.' + (str(h.availability.all()[0].fees) if h.availability.all() else '')) for h
             in doctor.doctor_clinics.all()])

    def dehydrate_gst(self, doctor):

         status = 'Pending'
         for doc in doctor.documents.all():
             if doc.document_type == DoctorDocument.GST:
                status = 'Submitted'
         return status

    def dehydrate_pan(self, doctor):
        status = 'Pending'
        for doc in doctor.documents.all():
            if doc.document_type == DoctorDocument.PAN:
                status = 'Submitted'
        return status

    def dehydrate_mci(self, doctor):
        status = 'Pending'
        for doc in doctor.documents.all():
            if doc.document_type == DoctorDocument.REGISTRATION:
                status = 'Submitted'
        return status

    def dehydrate_cheque(self, doctor):
        status = 'Pending'
        for doc in doctor.documents.all():
            if doc.document_type == DoctorDocument.CHEQUE:
                status = 'Submitted'
        return status

    def dehydrate_aadhar(self, doctor):
        status = 'Pending'
        for doc in doctor.documents.all():
            if doc.document_type == DoctorDocument.AADHAR:
                status = 'Submitted'
        return status


class CompetitorInfoFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
            
        # prev_compe_infos = {}
        # for item in self.cleaned_data:
        #     req_set = (item.get('name'), item.get('hospital_name'), item.get('doctor'))
        #     if req_set in prev_compe_infos:
        #         raise forms.ValidationError('Cannot have duplicate competitor info.')
        #     else:
        #         prev_compe_infos[req_set] = True





class CompetitorInfoForm(forms.ModelForm):
    hospital_name = forms.CharField(required=True)
    fee = forms.CharField(required=True)
    url = forms.URLField(required=True)
    # processed_url = forms.URLField(required=True)


class CompetitorInfoInline(nested_admin.NestedTabularInline):
    model = CompetitorInfo
    autocomplete_fields = ['hospital']
    form = CompetitorInfoForm
    formset = CompetitorInfoFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['name', 'hospital', 'hospital_name', 'fee', 'url']


class CompetitorInfoResource(resources.ModelResource):
    class Meta:
        model = CompetitorInfo
        fields = ('id', 'doctor', 'hospital_name', 'fee', 'url')

    def init_instance(self, row=None):
        ins = super().init_instance(row)
        ins.name = CompetitorInfo.PRACTO
        return ins


class CompetitorInfoImportAdmin(ImportExportModelAdmin):
    resource_class = CompetitorInfoResource
    list_display = ('id', 'doctor', 'hospital_name', 'fee', 'url')


class CompetitorMonthlyVisitsInline(nested_admin.NestedTabularInline):
    model = CompetitorMonthlyVisit
    extra = 0
    can_delete = True
    show_change_link = False
    verbose_name = 'Monthly Visit through Competitor Info'
    verbose_name_plural = 'Monthly Visits through Competitor Info'


class DoctorAdmin(ImportExportMixin, VersionAdmin, ActionAdmin, QCPemAdmin, nested_admin.NestedModelAdmin):
    # class DoctorAdmin(nested_admin.NestedModelAdmin):
    resource_class = DoctorResource
    change_list_template = 'superuser_import_export.html'

    list_display = (
        'name', 'updated_at', 'data_status', 'onboarding_status', 'list_created_by', 'list_assigned_to', 'registered',
        'get_onboard_link')
    date_hierarchy = 'created_at'
    list_filter = (
        'data_status', 'onboarding_status', 'is_live', 'enabled', 'is_insurance_enabled', 'doctorpracticespecializations__specialization',
        CityFilter, CreatedByFilter)
    form = DoctorForm
    inlines = [
        CompetitorInfoInline,
        CompetitorMonthlyVisitsInline,
        DoctorMobileInline,
        DoctorEmailInline,
        #ProcedureInline,
        DoctorPracticeSpecializationInline,
        DoctorQualificationInline,
        # DoctorHospitalInline,
        DoctorClinicInline,
        DoctorLanguageInline,
        DoctorAwardInline,
        DoctorAssociationInline,
        DoctorExperienceInline,
        DoctorMedicalServiceInline,
        DoctorImageInline,
        DoctorDocumentInline,
        GenericAdminInline,
        BillingAccountInline
    ]
    exclude = ['user', 'created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code', 'search_key', 'live_at',
               'onboarded_at', 'qc_approved_at']
    search_fields = ['name']

    # def get_export_queryset(self, request):
    #     return super(DoctorAdmin, self).get_export_queryset(request).prefetch_related('hospitals',
    #                                                                                   'doctorpracticespecializations',
    #                                                                                   'qualifications',
    #                                                                                   'doctorpracticespecializations__specialization',
    #                                                                                   'qualifications__qualification',
    #                                                                                   'doctor_clinics__hospital',
    #                                                                                   'doctor_clinics__availability',
    #                                                                                   'documents')

    def get_readonly_fields(self, request, obj=None):
        read_only_fields = ['source', 'batch', 'lead_url', 'registered', 'matrix_lead_id', 'matrix_reference_id', 'about', 'is_live', 'enable_for_online_booking', 'onboarding_url']
        if (not request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists()) and (not request.user.is_superuser):
            read_only_fields += ['onboarding_status']
        return read_only_fields

    def lead_url(self, instance):
        if instance.id:
            ref_id = instance.matrix_reference_id
            if ref_id is not None:
                html = '''<a href='/admin/lead/doctorlead/%s/change/' target=_blank>Lead Page</a>''' % (ref_id)
                return mark_safe(html)
        else:
            return mark_safe('''<span></span>''')

    def onboarding_url(self, instance):
        if instance.id:
            token = DoctorOnboardingToken.objects.filter(doctor=instance.id, status=DoctorOnboardingToken.GENERATED).first()
            if token:
                return mark_safe('<a href="{0}">{0}</a>'.format(settings.BASE_URL + '/onboard/doctor?token=' + str(token.token)))
        return None

    def registered(self, instance):
        registered = None
        if instance and instance.id:
            registered = 'NO'
            if instance.user is not None:
                registered = 'YES'
        return mark_safe('''<span>%s</span>'''%(registered))
    registered.short_description = "Registered"

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url('onboard_admin/(?P<userid>\d+)/', self.admin_site.admin_view(self.onboarddoctor_admin),
                name="onboarddoctor_admin"),
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
            count = DoctorOnboardingToken.objects.filter(doctor=doctor).count()
        except Exception as e:
            pass
            # last_token = None

        # last_url = None
        # created_at = ""
        # if last_token:
        #     last_url = host+'/onboard/lab?token='+str(last_token.token)
        #     created_at = last_token.created_at

        # check for errors
        errors = []
        required = ['name', 'gender', 'license', 'practicing_since']
        for req in required:
            if not getattr(doctor, req):
                errors.append(req + ' is required')

        length_required = ['mobiles', 'emails', 'qualifications', 'hospitals',
                           'languages', 'experiences']

        for req in length_required:
            if not len(getattr(doctor, req).all()):
                errors.append(req + ' is required')
            if req =='mobiles' and not len(getattr(doctor, req).filter(is_primary=True)) == 1:
                errors.append("Doctor must have atleast and atmost one primary mobile number.")

        return render(request, 'onboarddoctor.html', {'doctor': doctor, 'count': count, 'errors': errors})

    def get_onboard_link(self, obj=None):
        if obj.data_status == Doctor.IN_PROGRESS and obj.onboarding_status in (
                Doctor.NOT_ONBOARDED, Doctor.REQUEST_SENT):
            return mark_safe("<a href='/admin/doctor/doctor/onboard_admin/%s'>generate onboarding url</a>" % obj.id)
        return ""

    def get_form(self, request, obj=None, **kwargs):
        form = super(DoctorAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if (not request.user.is_superuser) and (
                (not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() and not request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists())):
            form.base_fields['assigned_to'].disabled = True
        return form

    # def save_formset(self, request, form, formset, change):
    #     for form in formset.forms:
    #         if hasattr(form.instance, 'created_by'):
    #             form.instance.created_by = request.user
    #     try:
    #         formset.save()
    #     except Exception as e:
    #         logger.error(e)

    def save_related(self, request, form, formsets, change):
        super(type(self), self).save_related(request, form, formsets, change)
        # now you have all objects in the database
        doctor = form.instance
        doc_hosp_form_change = False
        gen_admin_form_change = False
        doc_hosp_new_len = doc_hosp_del_len = gen_admin_new_len = gen_admin_del_len = 0
        for formset in formsets:
            if isinstance(formset, DoctorClinicFormSet):
                for form in formset.forms:
                    if 'hospital' in form.changed_data:
                        doc_hosp_form_change = True
                        break
                doc_hosp_new_len = len(formset.new_objects)
                doc_hosp_del_len = len(formset.deleted_objects)
            if isinstance(formset, GenericAdminFormSet):
                for form in formset.forms:
                    if form.has_changed():
                        gen_admin_form_change = True
                        break
                gen_admin_new_len = len(formset.new_objects)
                gen_admin_del_len = len(formset.deleted_objects)

        if doctor is not None:
            if ((doc_hosp_form_change or doc_hosp_new_len > 0 or doc_hosp_del_len > 0) or
                    (gen_admin_form_change or gen_admin_new_len > 0 or gen_admin_del_len > 0)):
                GenericAdmin.create_admin_permissions(doctor)
                GenericAdmin.create_admin_billing_permissions(doctor)

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

    def has_change_permission(self, request, obj=None):
        if not super().has_change_permission(request, obj):
            return False
        if not obj:
            return True

        if request.user.is_superuser and request.user.is_staff:
            return True
        if (request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() or request.user.groups.filter(
                name=constants['SUPER_QC_GROUP']).exists() or request.user.groups.filter(
                name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists()) and obj.data_status in (1, 2, 3):
            return True
        return obj.created_by == request.user

    class Media:
        js = ('js/admin/ondoc.js',)


class CustomDateInput(forms.DateInput):
    input_type = 'date'


class TimePickerWidget(forms.TextInput):

    def render(self, name, value, attrs=None):
        htmlString = u''
        htmlString += u'<div><select name="%s">' % (name)
        default_min = default_hour = 0

        if value:
            values_list = value.split(':')
            default_hour = values_list[0].lstrip("0")
            default_min = values_list[1].lstrip("0")
        default_hour = default_hour if default_hour else 0
        default_min = default_min if default_min else 0
        for i in range(0, 24):
            for d in range(0, 60, 15):
                if i==int(default_hour) and d==int(default_min):
                    htmlString += ('<option selected value="%02d:%02d">%02d:%02d</option>' % (i, d, i, d))
                else:
                    htmlString += ('<option value="%02d:%02d">%02d:%02d</option>' % (i, d, i, d))

        htmlString +='</select></div>'
        return mark_safe(u''.join(htmlString))


class DoctorOpdAppointmentForm(forms.ModelForm):

    start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder':'Select a date'}))
    start_time = forms.CharField(widget=TimePickerWidget())
    cancel_type = forms.ChoiceField(label='Cancel Type', choices=((0, 'Cancel and Rebook'),
                                                                  (1, 'Cancel and Refund'),), initial=0, widget=forms.RadioSelect)

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        if self.request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists() and cleaned_data.get('status') == OpdAppointment.BOOKED:
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

        if cleaned_data.get('doctor') and cleaned_data.get('hospital'):
            doctor = cleaned_data.get('doctor')
            hospital = cleaned_data.get('hospital')
        elif self.instance.id:
            doctor = self.instance.doctor
            hospital = self.instance.hospital
        else:
            raise forms.ValidationError("Doctor and hospital details not entered.")

        if self.instance.status in [OpdAppointment.CANCELLED, OpdAppointment.COMPLETED] and len(cleaned_data):
            raise forms.ValidationError("Cancelled/Completed appointment cannot be modified.")

        if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=doctor,
                                                 doctor_clinic__hospital=hospital,
                                                 day=time_slot_start.weekday(),
                                                 start__lte=hour, end__gt=hour).exists():
            raise forms.ValidationError("Doctor do not sit at the given hospital in this time slot.")

        if self.instance.id:
            deal_price = cleaned_data.get('deal_price') if cleaned_data.get('deal_price') else self.instance.deal_price
            if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=doctor,
                                                     doctor_clinic__hospital=hospital,
                                                     day=time_slot_start.weekday(),
                                                     start__lte=hour, end__gt=hour,
                                                     deal_price=deal_price).exists():
                raise forms.ValidationError("Deal price is different for this time slot.")

        return cleaned_data


class DoctorOpdAppointmentAdmin(admin.ModelAdmin):
    form = DoctorOpdAppointmentForm
    list_display = ('booking_id', 'get_doctor', 'get_profile', 'status', 'time_slot_start', 'created_at',)
    list_filter = ('status', )
    date_hierarchy = 'created_at'

    @transaction.non_atomic_requests
    def change_view(self, request, object_id, form_url='', extra_context=None):        
        resp = super().change_view(request, object_id, form_url, extra_context=None)
        return resp

    def get_profile(self, obj):
        if not obj.profile_detail:
            return ''
        return obj.profile_detail.get('name', '')

    get_profile.admin_order_field = 'profile'
    get_profile.short_description = 'Profile Name'

    def get_doctor(self, obj):
        return obj.doctor.name

    get_doctor.admin_order_field = 'doctor'
    get_doctor.short_description = 'Doctor Name'

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        allowed_status_for_agent = [(OpdAppointment.BOOKED, 'Booked'),
                                    (OpdAppointment.RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                                    (OpdAppointment.RESCHEDULED_DOCTOR, 'Rescheduled by doctor'),
                                    (OpdAppointment.ACCEPTED, 'Accepted'),
                                    (OpdAppointment.CANCELLED, 'Cancelled')]
        if db_field.name == "status" and request.user.groups.filter(
                name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            kwargs['choices'] = allowed_status_for_agent
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        if obj is not None and obj.time_slot_start:
            time_slot_start = timezone.localtime(obj.time_slot_start, pytz.timezone(settings.TIME_ZONE))
            form.base_fields['start_date'].initial = time_slot_start.strftime('%Y-%m-%d')
            form.base_fields['start_time'].initial = time_slot_start.strftime('%H:%M')
        return form

    def get_fields(self, request, obj=None):
        if request.user.is_superuser and request.user.is_staff:
            return ('booking_id', 'doctor', 'doctor_id', 'doctor_details', 'hospital', 'profile',
                    'profile_detail', 'user', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status', 'status', 'cancel_type','start_date',
                    'start_time', 'payment_type', 'otp', 'insurance', 'outstanding')
        elif request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('booking_id', 'doctor_name', 'doctor_id', 'doctor_details', 'hospital_name',
                    'contact_details', 'used_profile_name',
                    'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_id', 'user_number', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status',
                    'payment_type', 'admin_information', 'otp', 'insurance', 'outstanding',
                    'status', 'cancel_type', 'start_date', 'start_time')
        else:
            return ()

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser and request.user.is_staff:
            return ('booking_id', 'doctor_id', 'doctor_details')
        elif request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('booking_id', 'doctor_name', 'doctor_id', 'doctor_details', 'hospital_name', 'contact_details',
                    'used_profile_name', 'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_id', 'user_number', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status', 'payment_type',
                    'admin_information', 'otp', 'insurance', 'outstanding')
        else:
            return ()


    def doctor_id(self, obj):
        doctor = obj.doctor if obj and obj.doctor else None
        if doctor is not None:
            return doctor.id
        return None

    def doctor_details(self, obj):
        doctor = obj.doctor if obj and obj.doctor else None
        if doctor is not None:
            result = ''
            result += 'Name : ' + doctor.name
            mobile_numbers = doctor.mobiles.all()
            if mobile_numbers.exists():
                result += '<br>Number(s) :<br>'
                for number in mobile_numbers:
                    result += '{0} (primary = {1}, verified = {2})'.format(number.number, number.is_primary, number.is_phone_number_verified)

            mobile_emails = doctor.emails.all()
            if mobile_emails.exists():
                result += '<br>Email(s) :<br>'
                for email in mobile_emails:
                    result += '{0} (primary = {1}, verified = {2})'.format(email.email, email.is_primary,
                                                                           email.is_email_verified)

            return mark_safe('<p>' + result + '</p>')

        return None

    def contact_details(self, obj):
        details = ''
        if obj and obj.doctor:
            doctor_admins = GenericAdmin.get_appointment_admins(obj)
            if doctor_admins:
                for doctor_admin in doctor_admins:
                    details += 'Phone number : {number}<br>Email : {email}<br><br>'.format(
                        number=doctor_admin.phone_number,
                        email=doctor_admin.email if doctor_admin.email else 'Not provided')
            else:
                details += "-"
        return mark_safe('<p>{details}</p>'.format(details=details))
    contact_details.short_description = "Concerned Admin Details"

    def booking_id(self, obj):
        return obj.id if  obj and obj.id else None

    def doctor_name(self, obj):
        profile_link = "opd/doctor/{}".format(obj.doctor.id)
        return mark_safe('{name} (<a href="{consumer_app_domain}/{profile_link}">Profile</a>)'.format(
            name=obj.doctor.name, consumer_app_domain=settings.CONSUMER_APP_DOMAIN, profile_link=profile_link))

    def hospital_name(self, obj):
        if obj.hospital.location:
            location_link = 'https://www.google.com/maps/search/?api=1&query={lat},{long}'.format(
                lat=obj.hospital.location.y, long=obj.hospital.location.x)
            return mark_safe('{name} (<a href="{location_link}">View on map</a>)'.format(name=obj.hospital.name,
                                                                                         location_link=location_link))
        else:
            return obj.hospital.name

    def used_profile_name(self, obj):
        return obj.profile.name

    def used_profile_number(self, obj):
        return obj.profile.phone_number if obj and obj.profile and obj.profile.phone_number else None

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
        return obj.user.phone_number if obj and obj.user and obj.user.phone_number else None

    def user_id(self, obj):
        return obj.user.id if obj and obj.user and obj.user.id else None

    def admin_information(self, obj):
        doctor_admins = auth_model.GenericAdmin.get_appointment_admins(obj)
        doctor_admins_phone_numbers = list()
        for doctor_admin in doctor_admins:
            doctor_admins_phone_numbers.append(doctor_admin.phone_number)
        return mark_safe(','.join(doctor_admins_phone_numbers))

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if obj:
            if obj.id:
                opd_obj = OpdAppointment.objects.select_for_update().get(pk=obj.id)
            if request.POST.get('start_date') and request.POST.get('start_time'):
                date_time_field = request.POST['start_date'] + " " + request.POST['start_time']
                to_zone = tz.gettz(settings.TIME_ZONE)
                dt_field = parse_datetime(date_time_field).replace(tzinfo=to_zone)

                if dt_field:
                    obj.time_slot_start = dt_field
            if request.POST.get('status') and int(request.POST['status']) == OpdAppointment.CANCELLED:
                obj.cancellation_type = OpdAppointment.AGENT_CANCELLED
                cancel_type = int(request.POST.get('cancel_type'))
                if cancel_type is not None:
                    logger.warning("Admin Cancel started - " + str(obj.id) + " timezone - " + str(timezone.now()))
                    obj.action_cancelled(cancel_type)
                    logger.warning("Admin Cancel completed - " + str(obj.id) + " timezone - " + str(timezone.now()))

            else:        
                super().save_model(request, obj, form, change)

    class Media:
        js = (
            '//ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js',
            'js/admin/ondoc.js',
        )


class SpecializationResource(resources.ModelResource):
    class Meta:
        model = Specialization
        fields = ('id', 'name', 'human_readable_name')


class CollegeResource(resources.ModelResource):
    class Meta:
        model = College
        fields = ('id', 'name')


class LanguageResource(resources.ModelResource):
    class Meta:
        model = Language
        fields = ('id', 'name')


class QualificationResource(resources.ModelResource):
    class Meta:
        model = Qualification
        fields = ('id', 'name')


class SpecializationAdmin(AutoComplete, ImportExportMixin, VersionAdmin):
    search_fields = ['name']
    resource_class = SpecializationResource
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


class HealthTipForm(forms.ModelForm):
    text = forms.CharField(widget=forms.Textarea)


class HealthTipAdmin(VersionAdmin):
    list_display = ('name', 'updated_at',)
    date_hierarchy = 'created_at'
    form = HealthTipForm
    search_fields = ['name']


class DoctorClinicAdmin(VersionAdmin):
    list_display = ('doctor', 'hospital', 'updated_at')
    date_hierarchy = 'created_at'
    search_fields = ['doctor__name', 'hospital__name']
    autocomplete_fields = ['doctor', 'hospital']
    inlines = [DoctorClinicTimingInline]

    def get_queryset(self, request):
        return super(DoctorClinicAdmin, self).get_queryset(request).select_related('doctor', 'hospital')


class DoctorMappingAdmin(VersionAdmin):
    list_display = ('doctor', 'profile_to_be_shown', 'updated_at',)
    date_hierarchy = 'created_at'
    search_fields = ['doctor']

    # autocomplete_fields = ['doctor', 'profile_to_be_shown']

    def get_form(self, request, obj=None, **kwargs):
        form = super(DoctorMappingAdmin, self).get_form(request, obj=obj, **kwargs)
        form.base_fields['doctor'].queryset = Doctor.objects.filter(is_internal=True)
        form.base_fields['profile_to_be_shown'].queryset = Doctor.objects.filter(is_internal=True)
        return form


class CommonSpecializationAdmin(VersionAdmin):
    autocomplete_fields = ['specialization']


class SpecializationDepartmentResource(resources.ModelResource):

    def skip_row(self, instance, original):
        if SpecializationDepartment.objects.filter(name=instance.name).exists():
            return True
        super().skip_row(instance, original)

    class Meta:
        model = SpecializationDepartment
        fields = ('id', 'name')


class SpecializationFieldResource(resources.ModelResource):

    def skip_row(self, instance, original):
        if SpecializationField.objects.filter(name=instance.name).exists():
            return True
        super().skip_row(instance, original)

    class Meta:
        model = SpecializationField
        fields = ('id', 'name')


class PracticeSpecializationResource(resources.ModelResource):
    name = Field(attribute='name', column_name='modified_name')
    field_medicine = Field(column_name='field_medicine')
    department = Field(column_name='department')
    general_specialization_id = Field(column_name='general_specialization_id')

    class Meta:
        model = PracticeSpecialization
        fields = ('id', 'name')

    def skip_row(self, instance, original):
        database_instance = PracticeSpecialization.objects.filter(name=instance.name).first()
        if database_instance:
            if not PracticeSpecialization.objects.filter(
                    general_specialization_ids__contains=[instance._general_specialization_id]).exists():
                if database_instance.general_specialization_ids:
                    database_instance.general_specialization_ids.append(instance._general_specialization_id)
                else:
                    database_instance.general_specialization_ids = [instance._general_specialization_id]
            if not database_instance.specialization_field:
                database_instance.specialization_field = instance.specialization_field
            database_instance.save()
            if not instance._department:
                return True
            SpecializationDepartmentMapping.objects.get_or_create(specialization=database_instance,
                                                                  department=instance._department)
            return True
        return False

    def get_or_init_instance(self, instance_loader, row):
        instance, created = super().get_or_init_instance(instance_loader, row)
        specialization_field, is_field_created = SpecializationField.objects.get_or_create(
            name=row.get('field_medicine')) if row.get('field_medicine') else (None, False)
        _department, is_dept_created = SpecializationDepartment.objects.get_or_create(
            name=row.get('department')) if row.get('department') else (None, False)
        _general_specialization_id = int(row.get('general_specialization_id'))
        instance._department = _department
        instance._general_specialization_id = _general_specialization_id
        instance.specialization_field = specialization_field
        return instance, created

    def after_save_instance(self, instance, using_transactions, dry_run):
        if instance.general_specialization_ids:
            instance.general_specialization_ids.append(instance._general_specialization_id)
        else:
            instance.general_specialization_ids = [instance._general_specialization_id]
        instance.save()
        if instance._department:
            SpecializationDepartmentMapping.objects.get_or_create(specialization=instance,
                                                                  department=instance._department)
        super().after_save_instance(instance, using_transactions, dry_run)


class SpecializationDepartmentAdmin(ImportExportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name', )
    date_hierarchy = 'created_at'
    resource_class = SpecializationDepartmentResource


class SpecializationFieldAdmin(ImportExportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name', )
    date_hierarchy = 'created_at'
    resource_class = SpecializationFieldResource


class PracticeSpecializationDepartmentMappingInline(admin.TabularInline):
    model = SpecializationDepartmentMapping
    extra = 0
    can_delete = True
    show_change_link = False


class PracticeSpecializationAdmin(AutoComplete, ImportExportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name', )
    date_hierarchy = 'created_at'
    inlines = [PracticeSpecializationDepartmentMappingInline, ]
    resource_class = PracticeSpecializationResource
    search_fields = ['name', ]


class ProcedureAdmin(AutoComplete, VersionAdmin):
    model = Procedure
    search_fields = ['name']
