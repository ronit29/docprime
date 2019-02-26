from django.forms.utils import ErrorList
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
from dal import autocomplete
from ondoc.api.v1.utils import GenericAdminEntity, util_absolute_url, util_file_name
from ondoc.common.models import AppointmentHistory
from ondoc.procedure.models import DoctorClinicProcedure, Procedure

logger = logging.getLogger(__name__)


from ondoc.account.models import Order, Invoice
from django.contrib.contenttypes.admin import GenericTabularInline
from ondoc.authentication.models import GenericAdmin, SPOCDetails, AssociatedMerchant, Merchant
from ondoc.doctor.models import (Doctor, DoctorQualification,
                                 DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
                                 MedicalConditionSpecialization, DoctorMedicalService, DoctorImage,
                                 DoctorDocument, DoctorMobile, DoctorOnboardingToken, Hospital,
                                 DoctorEmail, College,
                                 Specialization, Qualification, Language, DoctorClinic, DoctorClinicTiming,
                                 DoctorMapping, HospitalDocument, HospitalNetworkDocument, HospitalNetwork,
                                 OpdAppointment, CompetitorInfo, SpecializationDepartment,
                                 SpecializationField, PracticeSpecialization, SpecializationDepartmentMapping,
                                 DoctorPracticeSpecialization, CompetitorMonthlyVisit,
                                 GoogleDetailing, VisitReason, VisitReasonMapping, PracticeSpecializationContent,
                                 PatientMobile, DoctorMobileOtp,
                                 UploadDoctorData, CancellationReason)

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
from decimal import Decimal
from .common import AssociatedMerchantInline
from ondoc.sms import api
from ondoc.ratings_review import models as rating_models

class AutoComplete:
    def autocomplete_view(self, request):
        return CustomAutoComplete.as_view(model_admin=self)(request)


class ReadOnlyInline(nested_admin.NestedTabularInline):
    def get_readonly_fields(self, request, obj=None):
        if request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):
            all_fields = [f for f in self.model._meta.get_fields()
                          if f.concrete and (
                                  not f.is_relation
                                  or f.one_to_one
                                  or (f.many_to_one and f.related_model)
                          ) and not f.auto_created and not (f.auto_now if hasattr(f, 'auto_now') else False) and not (
                    f.auto_now_add if hasattr(f, 'auto_now_add') else False)
                          ]
            return [x.name for x in all_fields]
        return []


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


class DoctorQualificationInline(ReadOnlyInline):
    model = DoctorQualification
    form = DoctorQualificationForm
    formset = DoctorQualificationFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['college']


class DoctorClinicTimingForm(forms.ModelForm):

    def __init__(self, data=None, files=None, auto_id='id_%s', prefix=None, initial=None, error_class=ErrorList,
                 label_suffix=None, empty_permitted=False, instance=None, use_required_attribute=None):
        super().__init__(data, files, auto_id, prefix, initial, error_class, label_suffix, empty_permitted, instance,
                         use_required_attribute)

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
        # hospital = 0
        # count = 0
        # for value in self.cleaned_data:
        #     count += 1
        #     if value.get('hospital'):
        #         hospital += 1
        #
        # if count > 0:
        #     if not hospital:
        #         raise forms.ValidationError("Atleast one Hospital is required")


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


class DoctorClinicInlineForm(forms.ModelForm):
    hospital = forms.ModelChoiceField(
        queryset=Hospital.objects.all(),
        widget=autocomplete.ModelSelect2(url='hospital-autocomplete')
    )

    class Meta:
        model = DoctorClinic
        fields = ('__all__')


class DoctorClinicInline(nested_admin.NestedTabularInline):
    model = DoctorClinic
    form = DoctorClinicInlineForm
    extra = 0
    can_delete = True
    formset = DoctorClinicFormSet
    show_change_link = False
    # autocomplete_fields = ['hospital']
    inlines = [DoctorClinicTimingInline, DoctorClinicProcedureInline, AssociatedMerchantInline]

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


class DoctorLanguageInline(ReadOnlyInline):
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
    # formset = DoctorExperienceFormSet
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


class DoctorDocumentInline(ReadOnlyInline):
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
    mark_primary = forms.BooleanField(required=False)
    otp = forms.IntegerField(required=False)

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
    
        #Marking doctor mobile primary work.
        # if std_code and data.get('mark_primary'):
        #     raise forms.ValidationError('Primary number should be a mobile number')
        
        # if not std_code and data.get('mark_primary'):
        #     if number and (number<5000000000 or number>9999999999):
        #         raise forms.ValidationError("Invalid mobile number")

    class Meta:
        fields = '__all__'


# class DoctorMobileFormSet(forms.BaseInlineFormSet):
#     def clean(self):
#         super().clean()
#         if any(self.errors):
#             return

#         primary = 0
#         mark_primary = 0
#         count = 0

#         for value in self.cleaned_data:
#             std_code = value.get('std_code')
#             number = value.get('number')
#             if std_code:
#                 try:
#                     std_code=int(std_code)
#                 except:
#                     raise forms.ValidationError("Invalid STD code")

#             try:
#                 number=int(number)
#             except:
#                 raise forms.ValidationError("Invalid Number")

#             if std_code:
#                 if value.get('is_primary'):
#                     raise forms.ValidationError("Primary number should be a mobile number")

#                 if value.get('mark_primary'):
#                     raise forms.ValidationError("Mark primary is only applicable for mobile numbers.")

#             else:
#                 if number and (number<5000000000 or number>9999999999):
#                     raise forms.ValidationError("Invalid mobile number")

#             count += 1


#             if value.get('is_primary'):
#                 if self.forms[0].instance.doctor.onboarding_status == 3:
#                     if value.get('DELETE'):
#                         raise forms.ValidationError('Primary number cannot be deleted.')

#                     if not value.get('id'):
#                         raise forms.ValidationError('Primary number can be marked only by checking mark_primary, '
#                                                     'obtaining otp and entering otp again.')
#                     id = value.get('id').id
#                     if id and not DoctorMobile.objects.filter(id=id, is_primary=True).exists():
#                         raise forms.ValidationError('Primary number can be marked only by checking mark_primary, '
#                                                     'obtaining otp and entering otp again.')

#                     if id and not DoctorMobile.objects.filter(id=id, number=value.get('number')).exists():
#                         raise forms.ValidationError('Primary number cannot be changed. Add another number , mark it as primary'
#                                                     ' and validate it with otp')

#                     if value.get('mark_primary'):
#                         raise forms.ValidationError('Number is already primary number.')

#                 primary += 1

#             if value.get('mark_primary'):
#                 mark_primary += 1

#         if count > 0:

#             if primary > 1:
#                 raise forms.ValidationError("Doctor can have only one primary number.")

#             if DoctorMobile.objects.filter(doctor=self.forms[0].instance.doctor).exists() \
#                     and self.forms[0].instance.doctor.onboarding_status == 3:
#                 if primary != 1 :
#                     raise forms.ValidationError("Doctor must have one primary mobile number.")
#             if mark_primary > 1:
#                 raise forms.ValidationError("Doctor can change only one primary mobile number.")

#         record = None
#         todo_make_primary = None
#         for form in self.forms:
#             if form.instance.mark_primary and not form.instance.otp:
#                 # if not DoctorMobileOtp.objects.filter(doctor_mobile=form.instance).exists():
#                 form.instance.save()
#                 dmo = DoctorMobileOtp.create_otp(form.instance)
#                 message = "The OTP for onboard process is %d" % dmo.otp

#                 try:
#                     api.send_sms(message, str(form.instance.number))
#                 except Exception as e:
#                     logger.error(str(e))

#             elif form.instance.mark_primary and form.instance.otp:
#                 doctor_mobile_otp = form.instance.mobiles_otp.all().last()
#                 resonse = doctor_mobile_otp.consume()
#                 if resonse:
#                     # DoctorMobile.objects.filter(doctor=form.instance.doctor).update(is_primary=False)
#                     # form.instance.is_primary = True
#                     todo_make_primary = form.instance.id
#                     form.instance.otp = None
#                     form.instance.mark_primary = False
#                 else:
#                     raise forms.ValidationError("OTP is incorrect")


#             elif not form.instance.mark_primary and form.instance.otp:
#                 form.instance.otp = None

#         if todo_make_primary:
#             for form in self.forms:
#                 if form.instance.id == todo_make_primary:
#                     form.instance.is_primary = True
#                 else:
#                     form.instance.is_primary = False


class DoctorMobileInline(nested_admin.NestedTabularInline):
    model = DoctorMobile
    form = DoctorMobileForm
    #formset = DoctorMobileFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['std_code','number', 'is_primary', 'mark_primary', 'otp']


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
    disable_comments = forms.CharField(widget=forms.Textarea, required=False)
    raw_about = forms.CharField(widget=forms.Textarea, required=False)
    # primary_mobile = forms.CharField(required=True)
    # email = forms.EmailField(required=True)
    practicing_since = forms.ChoiceField(required=False, choices=practicing_since_choices)
    # onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Doctor.ONBOARDING_STATUS)

    def validate_qc(self):
        qc_required = {'name': 'req', 'gender': 'req',
                       # 'practicing_since': 'req',
                       'emails': 'count',
                       'doctor_clinics': 'count', 'languages': 'count',
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
            if key == 'doctor_clinics':
                    all_hospital_ids = []
                    for indx in range(int(self.data[key + '-TOTAL_FORMS'])):
                        all_hospital_ids.append(int(self.data[key + '-{}-hospital'.format(indx)]))
                    if not Hospital.objects.filter(pk__in=all_hospital_ids, is_live=True).count():
                        raise forms.ValidationError("Atleast one entry of " + key + " should be live for Quality Check")


    def clean_practicing_since(self):
        data = self.cleaned_data['practicing_since']
        if data == '':
            return None
        return data

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        is_enabled = data.get('enabled', None)
        enabled_for_online_booking = data.get('enabled_for_online_booking', None)
        if is_enabled is None:
            is_enabled = self.instance.enabled if self.instance else False
        if enabled_for_online_booking is None:
            enabled_for_online_booking = self.instance.enabled_for_online_booking if self.instance else False
        if is_enabled and enabled_for_online_booking:
            if any([data.get('disabled_after', None), data.get('disable_reason', None),
                    data.get('disable_comments', None)]):
                raise forms.ValidationError(
                    "Cannot have disabled after/disabled reason/disable comments if doctor is enabled or not enabled for online booking.")
        elif not is_enabled or not enabled_for_online_booking:
            if not all([data.get('disabled_after', None), data.get('disable_reason', None)]):
                raise forms.ValidationError(
                    "Must have disabled after/disable reason if doctor is not enabled or not enabled for online booking.")
            if data.get('disable_reason', None) and data.get('disable_reason', None) == Doctor.OTHERS and not data.get(
                    'disable_comments', None):
                raise forms.ValidationError("Must have disable comments if disable reason is others.")


class CityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'hospitals__city'

    def lookups(self, request, model_admin):
        cities = Hospital.objects.distinct('city').values_list('city','city')
        # cities = set(
        #     [(c['hospitals__city'].upper(), c['hospitals__city'].upper()) if (c.get('hospitals__city')) else ('', '')
        #      for c in Doctor.objects.all().values('hospitals__city')])
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


class DoctorPracticeSpecializationInline(ReadOnlyInline):
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
        if any(self.errors):
            return
        if self.cleaned_data:
            validate_unique = []
            for data in self.cleaned_data:
                if not data.get('DELETE'):
                    row = (data.get('phone_number'), data.get('hospital'), data.get('permission_type'))
                    if row in validate_unique:
                        raise forms.ValidationError("Duplicate Permission with this phone number exists.")
                    else:
                        validate_unique.append(row)
            if validate_unique:
                numbers = list(zip(*validate_unique))[0]
                for row in validate_unique:
                    if row[1] is None and numbers.count(row[0]) > 2:
                        raise forms.ValidationError(
                            "Permissions for all Hospitals already allocated for %s." % (row[0]))


class GenericAdminInline(nested_admin.NestedTabularInline):
    model = GenericAdmin
    extra = 0
    formset = GenericAdminFormSet
    form = GenericAdminForm
    show_change_link = False
    # exclude = ('hospital_network', 'source_type', 'is_doc_admin', 'read_permission')
    fields = ('phone_number', 'hospital', 'name', 'permission_type', 'super_user_permission', 'write_permission', 'user', 'updated_at')
    verbose_name_plural = "Admins"

    # def has_delete_permission(self, request, obj=None):
    #     if request.user.is_superuser:
    #         return True
    #     else:
    #         return False
    #
    # def has_add_permission(self, request, obj=None):
    #     if request.user.is_superuser:
    #         return True
    #     else:
    #         return False

    def get_readonly_fields(self, request, obj=None):
        # if not request.user.is_superuser:
        #     return ['phone_number', 'is_disabled', 'write_permission', 'read_permission', 'hospital',  'permission_type',
        #             'user', 'is_doc_admin']
        # else:
        return ['user', 'updated_at']

    def get_queryset(self, request):
        return super(GenericAdminInline, self).get_queryset(request).select_related('doctor', 'hospital', 'user')\
            .filter(entity_type=GenericAdminEntity.DOCTOR)


    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "hospital":
            doctor_id = request.resolver_match.kwargs.get('object_id')
            kwargs["queryset"] = Hospital.objects.filter(assoc_doctors=doctor_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # def get_formset(self, request, obj=None, **kwargs):
    #     formset = super().get_formset(request, obj=obj, **kwargs)
    #     if not request.POST:
    #         if obj is not None:
    #             try:
    #                 formset.form.base_fields['hospital'].queryset = Hospital.objects.filter(
    #                     assoc_doctors=obj).distinct()
    #             except MultipleObjectsReturned:
    #                 pass
    #     return formset



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
    search_fields = ['doctor__id', 'doctor__name']

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


class CompetitorInfoInline(ReadOnlyInline):
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
        fields = ('id', 'doctor', 'hospital_name', 'fee', 'hospital', 'url')

    def init_instance(self, row=None):
        ins = super().init_instance(row)
        ins.name = CompetitorInfo.PRACTO
        return ins


class CompetitorInfoImportAdmin(ImportExportModelAdmin):
    resource_class = CompetitorInfoResource
    list_display = ('id', 'doctor', 'hospital_name', 'fee', 'url')


class CompetitorMonthlyVisitsInline(ReadOnlyInline):
    model = CompetitorMonthlyVisit
    extra = 0
    can_delete = True
    show_change_link = False
    verbose_name = 'Monthly Visit through Competitor Info'
    verbose_name_plural = 'Monthly Visits through Competitor Info'


class DoctorAdmin(AutoComplete, ImportExportMixin, VersionAdmin, ActionAdmin, QCPemAdmin, nested_admin.NestedModelAdmin):
    # class DoctorAdmin(nested_admin.NestedModelAdmin):
    resource_class = DoctorResource
    change_list_template = 'superuser_import_export.html'

    # fieldsets = ((None,{'fields':('name','gender','practicing_since','license','is_license_verified','signature','raw_about' \
    #               ,'about',  'onboarding_url', 'get_onboard_link', 'additional_details')}),
    #              (None,{'fields':('assigned_to',)}),
    #               (None,{'fields':('enabled_for_online_booking','is_internal','is_test_doctor','is_insurance_enabled','is_retail_enabled', \
    #                 'is_online_consultation_enabled','online_consultation_fees')}),
    #                 (None,{'fields':('enabled','disabled_after','disable_reason','disable_comments','onboarding_status','assigned_to', \
    #                  'matrix_lead_id','batch', 'is_gold', 'lead_url', 'registered','is_live')}))
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
        DoctorPracticeSpecializationInline,
        DoctorQualificationInline,
        DoctorClinicInline,
        DoctorLanguageInline,
        DoctorAwardInline,
        DoctorAssociationInline,
        DoctorExperienceInline,
        DoctorMedicalServiceInline,
        DoctorImageInline,
        DoctorDocumentInline,
        GenericAdminInline,
        AssociatedMerchantInline
    ]

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
    #exclude = ('source','batch','lead_url','registered')
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):
            qs = qs.filter(source='pr')
            if request.path.endswith('doctor/'):
                qs = Doctor.objects.none()
            #pass
        return qs

    def get_exclude(self, request, obj=None):
        exclude = ['source', 'user', 'created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code', 'search_key', 'live_at',
               'onboarded_at', 'qc_approved_at','enabled_for_online_booking_at', 'disabled_at']

        if request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):
            exclude += ['source', 'batch', 'lead_url', 'registered', 'created_by', 'about', 'raw_about',
            'additional_details', 'is_insurance_enabled', 'is_insurance_enabled', 'is_online_consultation_enabled',
            'online_consultation_fees', 'is_retail_enabled', 'is_internal', 'is_test_doctor', 'doctor_signature',
            'is_enabled', 'matrix_reference_id', 'doctor_signature','enabled_for_online_booking','raw_about']

        return exclude

    def get_readonly_fields(self, request, obj=None):
        read_only_fields = ['is_gold','source', 'lead_url', 'registered', 'matrix_lead_id', 'matrix_reference_id', 'about', 'is_live', 'onboarding_url', 'get_onboard_link']
        if not request.user.is_member_of(constants['SUPER_QC_GROUP']) and not request.user.is_superuser:
            read_only_fields += ['onboarding_status']
        if request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):
            read_only_fields += ['name', 'gender', 'license', 'additional_details',
                                 'is_insurance_enabled', 'is_retail_enabled', 'is_online_consultation_enabled',
                                 'online_consultation_fees', 'live_at', 'is_internal',
                                 'is_test_doctor', 'is_license_verified', 'signature', 'enabled', 'raw_about']
        excluded = self.get_exclude(request, obj)
        final = [x for x in read_only_fields if x not in excluded]
        #make matrix_lead_id ediable if not present or user is superqc or superuser
        is_matrix_id_editable = False
        if obj:
            if not obj.matrix_lead_id:
                is_matrix_id_editable = True
            if request.user.is_member_of(constants['SUPER_QC_GROUP']) or request.user.is_superuser:
                is_matrix_id_editable = True
        else:
            is_matrix_id_editable = True

        if is_matrix_id_editable:
            final.remove('matrix_lead_id')

        return final

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
        required = ['name', 'gender', 'practicing_since']
        for req in required:
            if not getattr(doctor, req):
                errors.append(req + ' is required')

        length_required = ['mobiles', 'emails', 'hospitals']

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
        # if not request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):
        #     kwargs['form'] = DoctorForm
        kwargs['form'] = DoctorForm
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if not request.user.is_superuser and\
            (not request.user.is_member_of(constants['QC_GROUP_NAME']) and not request.user.is_member_of(constants['SUPER_QC_GROUP']) ):
            form.base_fields['assigned_to'].disabled = True
        # if request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):
        #     form.base_fields['raw_about'].disabled = True
        #     form.base_fields['additional_details'].disabled = True
        return form

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        for instance in instances:
            if isinstance(instance, GenericAdmin):
                if instance.hospital and instance.hospital.is_appointment_manager:
                    instance.is_disabled = True
                if (not instance.created_by):
                    instance.created_by = request.user
                if (not instance.id):
                    instance.source_type = GenericAdmin.CRM
                    instance.entity_type = GenericAdmin.DOCTOR
            instance.save()
        formset.save_m2m()


    # def save_related(self, request, form, formsets, change):
    #     super(type(self), self).save_related(request, form, formsets, change)
    #     # now you have all objects in the database
    #     doctor = form.instance
    #     doc_hosp_form_change = False
    #     gen_admin_form_change = False
    #     doc_hosp_new_len = doc_hosp_del_len = gen_admin_new_len = gen_admin_del_len = 0
    #     for formset in formsets:
    #         if isinstance(formset, DoctorClinicFormSet):
    #             for form in formset.forms:
    #                 if 'hospital' in form.changed_data:
    #                     doc_hosp_form_change = True
    #                     break
    #             doc_hosp_new_len = len(formset.new_objects)
    #             doc_hosp_del_len = len(formset.deleted_objects)
    #         if isinstance(formset, GenericAdminFormSet):
    #             for form in formset.forms:
    #                 if form.has_changed():
    #                     gen_admin_form_change = True
    #                     break
    #             gen_admin_new_len = len(formset.new_objects)
    #             gen_admin_del_len = len(formset.deleted_objects)
    #
    #     if doctor is not None:
    #         if ((doc_hosp_form_change or doc_hosp_new_len > 0 or doc_hosp_del_len > 0) or
    #                 (gen_admin_form_change or gen_admin_new_len > 0 or gen_admin_del_len > 0)):
    #             GenericAdmin.create_admin_permissions(doctor)
    #             GenericAdmin.create_admin_billing_permissions(doctor)

    def save_model(self, request, obj, form, change):
        if not request.user.is_member_of(constants['DOCTOR_SALES_GROUP']):        
            if not obj.created_by:
                obj.created_by = request.user
            if not obj.assigned_to:
                obj.assigned_to = request.user
        if not form.cleaned_data.get('enabled', False) and not obj.disabled_by:
            obj.disabled_by = request.user
        elif form.cleaned_data.get('enabled', False) and obj.disabled_by:
            obj.disabled_by = None
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
                name=constants['DOCTOR_SALES_GROUP']).exists() or request.user.groups.filter(
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

        if not cleaned_data.get('status') is OpdAppointment.CANCELLED and (cleaned_data.get(
                'cancellation_reason') or cleaned_data.get('cancellation_comments')):
            raise forms.ValidationError(
                "Reason/Comment for cancellation can only be entered on cancelled appointment")

        if cleaned_data.get('status') is OpdAppointment.CANCELLED and not cleaned_data.get('cancellation_reason'):
            raise forms.ValidationError("Reason for Cancelled appointment should be set.")

        if cleaned_data.get('status') is OpdAppointment.CANCELLED and cleaned_data.get(
                'cancellation_reason') and cleaned_data.get('cancellation_reason').is_comment_needed and not cleaned_data.get('cancellation_comments'):
            raise forms.ValidationError(
                "Cancellation comments must be mentioned for selected cancellation reason.")

        if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=doctor,
                                                 doctor_clinic__hospital=hospital,
                                                 day=time_slot_start.weekday(),
                                                 start__lte=hour, end__gt=hour).exists():
            raise forms.ValidationError("Doctor do not sit at the given hospital in this time slot.")

        # if self.instance.id:
        #     if cleaned_data.get('status') == OpdAppointment.RESCHEDULED_PATIENT or cleaned_data.get(
        #             'status') == OpdAppointment.RESCHEDULED_DOCTOR:
        #         if self.instance.procedure_mappings.count():
        #             doctor_details = self.instance.get_procedures()[0]
        #             deal_price = Decimal(doctor_details["deal_price"])
        #         else:
        #             deal_price = cleaned_data.get('deal_price') if cleaned_data.get('deal_price') else self.instance.deal_price
        #         if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=doctor,
        #                                                  doctor_clinic__hospital=hospital,
        #                                                  day=time_slot_start.weekday(),
        #                                                  start__lte=hour, end__gt=hour,
        #                                                  deal_price=deal_price).exists():
        #             raise forms.ValidationError("Deal price is different for this time slot.")

        return cleaned_data


class DoctorOpdAppointmentAdmin(admin.ModelAdmin):
    form = DoctorOpdAppointmentForm
    list_display = ('booking_id', 'get_doctor', 'get_profile', 'status', 'time_slot_start', 'effective_price', 'created_at', 'updated_at')
    list_filter = ('status', )
    date_hierarchy = 'created_at'

    def get_queryset(self, request):
        return super(DoctorOpdAppointmentAdmin, self).get_queryset(request).select_related('doctor', 'hospital', 'hospital__network')

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
        if obj.doctor:
            return obj.doctor.name
        return ''
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
        form.base_fields['cancellation_reason'].queryset = CancellationReason.objects.filter(
            Q(type=Order.DOCTOR_PRODUCT_ID) | Q(type__isnull=True), visible_on_admin=True)
        if obj is not None and obj.time_slot_start:
            time_slot_start = timezone.localtime(obj.time_slot_start, pytz.timezone(settings.TIME_ZONE))
            form.base_fields['start_date'].initial = time_slot_start.strftime('%Y-%m-%d')
            form.base_fields['start_time'].initial = time_slot_start.strftime('%H:%M')
        return form

    def get_fields(self, request, obj=None):
        if request.user.is_superuser and request.user.is_staff:
            return ('booking_id', 'doctor', 'doctor_id', 'doctor_details', 'hospital', 'hospital_details', 'kyc',
                    'contact_details', 'profile', 'profile_detail', 'user', 'booked_by', 'procedures_details',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status', 'status', 'cancel_type',
                    'cancellation_reason', 'cancellation_comments', 'ratings',
                    'start_date', 'start_time', 'payment_type', 'otp', 'insurance', 'outstanding', 'invoice_urls', 'payment_type')
        elif request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('booking_id', 'doctor_name', 'doctor_id', 'doctor_details', 'hospital_name', 'hospital_details',
                    'kyc', 'contact_details', 'used_profile_name',
                    'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_id', 'user_number', 'booked_by', 'procedures_details',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status',
                    'payment_type', 'admin_information', 'otp', 'insurance', 'outstanding',
                    'status', 'cancel_type', 'cancellation_reason', 'cancellation_comments',
                    'start_date', 'start_time', 'invoice_urls', 'payment_type')
        else:
            return ()

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser and request.user.is_staff:
            return ('booking_id', 'doctor_id', 'doctor_details', 'contact_details', 'hospital_details', 'kyc',
                    'procedures_details', 'invoice_urls', 'ratings', 'payment_type')
        elif request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('booking_id', 'doctor_name', 'doctor_id', 'doctor_details', 'hospital_name',
                    'hospital_details', 'kyc', 'contact_details',
                    'used_profile_name', 'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_id', 'user_number', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status', 'payment_type',
                    'admin_information', 'otp', 'insurance', 'outstanding', 'procedures_details','invoice_urls', 'payment_type')
        else:
            return ('invoice_urls')

    def ratings(self, obj):
        rating_queryset = rating_models.RatingsReview.objects.filter(appointment_id=obj.id).first()
        if rating_queryset:
            review = rating_queryset.review if rating_queryset.review else ''
            url = '/admin/ratings_review/ratingsreview/%s/change' % (rating_queryset.id)
            response = mark_safe('''<p>Ratings: %s</p><p>Review: %s</p><p>Status: <b>%s</b></p><p><a href="%s" target="_blank">Link</a></p>'''
                                 % (rating_queryset.ratings, review,
                                    dict(rating_models.RatingsReview.MODERATION_TYPE_CHOICES)[rating_queryset.moderation_status],
                                    url))
            return response
        return ''


    def invoice_urls(self, instance):
        invoices_urls = ''
        for invoice in instance.get_invoice_urls():
            invoices_urls += "<a href={} target='_blank'>{}</a><br>".format(util_absolute_url(invoice),
                                                                             util_file_name(invoice))
        return mark_safe(invoices_urls)
    invoice_urls.short_description = 'Invoice(s)'

    def procedures_details(self, obj):
        procedure_mappings = obj.procedure_mappings.all()
        if procedure_mappings:
            result = []
            for mapping in procedure_mappings:
                result.append('{}, mrp was {}, booking price was {}'.format(mapping.procedure, mapping.mrp, mapping.deal_price))
            return ",\n".join(result)
        return None

    def kyc(self, obj):
        count = 0
        if obj.hospital.network_type == Hospital.NETWORK_HOSPITAL and obj.hospital.network and obj.hospital.network.is_billing_enabled:
            all_docs = obj.hospital.network.hospital_network_documents.all()
            for doc in all_docs:
                if doc.document_type == HospitalNetworkDocument.PAN or doc.document_type == HospitalNetworkDocument.CHEQUE:
                    count += 1
        elif not obj.hospital.network_type == Hospital.NETWORK_HOSPITAL and obj.hospital.is_billing_enabled:
            all_docs = obj.hospital.hospital_documents.all()
            for doc in all_docs:
                if doc.document_type == HospitalDocument.PAN or doc.document_type == HospitalDocument.CHEQUE:
                    count += 1
        elif obj.doctor:
            all_docs = obj.doctor.documents.all()
            for doc in all_docs:
                if doc.document_type == DoctorDocument.PAN or doc.document_type == DoctorDocument.CHEQUE:
                    count += 1

        if count == 2:
                return True

        return False

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

    def hospital_details(self, obj):
        if obj.hospital:
            result = ''
            c_t_d = dict(SPOCDetails.CONTACT_TYPE_CHOICES)
            for spoc in obj.hospital.spoc_details.all():
                result += 'Name : {name}\nSTD Code : {std_code}\nNumber : {number}\nEmail : {email}\nDetails : {details}\nContact Type : {c_t}\n\n'.format(**(spoc.__dict__), c_t=c_t_d.get(spoc.contact_type, ''))
            return result
        return ''

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
        responsible_user = request.user
        obj._responsible_user = responsible_user if responsible_user and not responsible_user.is_anonymous else None
        if obj:
            if obj.id:
                obj._source = AppointmentHistory.CRM
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


class PracticeSpecializationSynonymResource(resources.ModelResource):
    class Meta:
        model = PracticeSpecialization
        fields = ('id', 'synonyms')


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
    resource_class = PracticeSpecializationSynonymResource
    search_fields = ['name', ]


class GoogleDetailingResource(resources.ModelResource):
    identifier = fields.Field(attribute='identifier', column_name='Unique identifier')
    name = fields.Field(attribute='name', column_name='Doc Name')
    clinic_hospital_name = fields.Field(attribute='clinic_hospital_name', column_name='Clinic/ Hospital Name')
    address = fields.Field(attribute='address', column_name='Address')
    doctor_clinic_address = fields.Field(attribute='doctor_clinic_address', column_name='Doctor Name + Clinic Name +  Address ')
    clinic_address = fields.Field(attribute='clinic_address', column_name='Clinic Name +  Address ')

    class Meta:
        model = GoogleDetailing
        import_id_fields = ('id',)
        exclude = ('created_at', 'updated_at', 'doctor_place_search', 'clinic_place_search', 'doctor_detail',
                   'clinic_detail', 'doctor_number', 'clinic_number', 'doctor_international_number',
                   'clinic_international_number', 'doctor_formatted_address', 'clinic_formatted_address', 'doctor_name',
                   'clinic_name')


class GoogleDetailingAdmin(ImportMixin, admin.ModelAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name', 'clinic_hospital_name')
    resource_class = GoogleDetailingResource


class VisitReasonPracticeSpecializationInline(admin.TabularInline):
    model = VisitReasonMapping
    fk_name = 'visit_reason'
    extra = 0
    can_delete = True
    show_change_link = False
    verbose_name = 'Related practice specialization'
    verbose_name_plural = 'Related practice specializations'


class VisitReasonAdmin(admin.ModelAdmin):
    fields = ['name']
    inlines = [VisitReasonPracticeSpecializationInline]

    class Meta:
        model = VisitReason


class PracticeSpecializationContentAdmin(admin.ModelAdmin):
    model = PracticeSpecializationContent
    list_display = ('specialization',)
    display = ('specialization', 'content', )
    autocomplete_fields = ('specialization', )


class PatientMobileInline(admin.TabularInline):
    model = PatientMobile
    extra = 0
    can_delete = True
    show_change_link = True


class OfflinePatientAdmin(VersionAdmin):
    list_display = ('name', 'gender', 'referred_by')
    date_hierarchy = 'created_at'
    inlines = [PatientMobileInline]


class UploadDoctorDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'batch', 'status', 'file')
    readonly_fields = ('status', 'error_message', 'user', 'lines')

    def save_model(self, request, obj, form, change):
        if obj:
            if not obj.user:
                obj.user = request.user
        super().save_model(request, obj, form, change)

    def error_message(self, instance):
        final_message = ''
        if instance.error_msg:
            for message in instance.error_msg:
                if isinstance(message, dict):
                    final_message += '{}  ::  {}\n\n'.format(message.get('line number', ''), message.get('message', ''))
                else:
                    final_message += str(message)
        return final_message
