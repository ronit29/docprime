from reversion.admin import VersionAdmin
from django.core.exceptions import FieldDoesNotExist, MultipleObjectsReturned
from django.conf import settings
from django.contrib.admin import SimpleListFilter
from django.utils.safestring import mark_safe
from django.conf.urls import url
from django.http import HttpResponse
from django.shortcuts import render
from django.db.models import Q
from import_export.admin import ImportExportMixin
from import_export import fields, resources

from ondoc.api.v1.diagnostic.views import TimeSlotExtraction
from ondoc.authentication.models import GenericAdmin
from ondoc.doctor.models import (Doctor, DoctorQualification,
                                 DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
                                 MedicalConditionSpecialization, DoctorMedicalService, DoctorImage,
                                 DoctorDocument, DoctorMobile, DoctorOnboardingToken, Hospital,
                                 DoctorEmail, College, DoctorSpecialization, GeneralSpecialization,
                                 Specialization, Qualification, Language, DoctorClinic, DoctorClinicTiming,
                                 DoctorMapping, HospitalDocument, HospitalNetworkDocument, HospitalNetwork,
                                 OpdAppointment)
from ondoc.authentication.models import User
from .common import *
from .autocomplete import CustomAutoComplete
from ondoc.crm.constants import constants
from django.utils.html import format_html_join
from django.template.loader import render_to_string
import nested_admin
from django.contrib.admin.widgets import AdminSplitDateTime
from ondoc.authentication import models as auth_model


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


# class DoctorHospitalInline(admin.TabularInline):
#     model = DoctorHospital
#     form = DoctorHospitalForm
#     formset = DoctorHospitalFormSet
#     extra = 0
#     # min_num = 1
#     can_delete = True
#     show_change_link = False
#     autocomplete_fields = ['hospital']
#     readonly_fields = ['deal_price']
#
#     def get_queryset(self, request):
#         return super(DoctorHospitalInline, self).get_queryset(request).select_related('doctor', 'hospital')


class DoctorClinicTimingInline(nested_admin.NestedTabularInline):
    model = DoctorClinicTiming
    form = DoctorClinicTimingForm
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
    inlines = [DoctorClinicTimingInline]

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
    formset = DoctorImageFormSet
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
                    if not key == DoctorDocument.GST and value < 1:
                        raise forms.ValidationError(choices[key] + " is required")


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

        if (
                not self.instance.network or not self.instance.network.is_billing_enabled) and self.instance.is_billing_enabled:
            if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
                for key, value in count.items():
                    if not key == HospitalDocument.GST and value < 1:
                        raise forms.ValidationError(choices[key] + " is required")


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

        if count > 0:
            if primary == 0:
                raise forms.ValidationError("One primary number is required")
            if primary >= 2:
                raise forms.ValidationError("Only one mobile number can be primary")


class DoctorMobileInline(nested_admin.NestedTabularInline):
    model = DoctorMobile
    form = DoctorMobileForm
    formset = DoctorMobileFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['number', 'is_primary']


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
    onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Doctor.ONBOARDING_STATUS)

    def validate_qc(self):
        qc_required = {'name': 'req', 'gender': 'req', 'practicing_since': 'req',
                       'raw_about': 'req', 'license': 'req', 'mobiles': 'count', 'emails': 'count',
                       'qualifications': 'count', 'doctor_clinics': 'count', 'languages': 'count',
                       'images': 'count', 'doctorspecializations': 'count'}

        # Q(hospital__is_billing_enabled=False, doctor=self.instance) &&
        # (network is null or network billing is false)

        if DoctorClinic.objects.filter(
                Q(hospital__network__is_billing_enabled=False, hospital__is_billing_enabled=False, doctor=self.instance)|
                Q(hospital__network__isnull=True, hospital__is_billing_enabled=False, doctor=self.instance)).exists():
            qc_required.update({
                'documents': 'count'
            })

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


class DoctorSpecializationInline(nested_admin.NestedTabularInline):
    model = DoctorSpecialization
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
    can_delete = True
    show_change_link = False
    readonly_fields = ['user']
    exclude = ('hospital_network', 'super_user_permission')
    verbose_name_plural = "Admins"

    def get_queryset(self, request):
        return super(GenericAdminInline, self).get_queryset(request).select_related('doctor', 'hospital', 'user')

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        if not request.POST:
            if obj is not None:
                try:
                    formset.form.base_fields['hospital'].queryset = Hospital.objects.filter(
                        assoc_doctors=obj).distinct()
                except MultipleObjectsReturned:
                    pass
        return formset


class DoctorImageAdmin(admin.ModelAdmin):
    model = DoctorImage
    readonly_fields = ('original_image', 'cropped_img', 'crop_image', 'doctor',)
    fields = ('original_image', 'cropped_img', 'crop_image', 'doctor')

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

    class Meta:
        model = Doctor
        fields = ('id', 'name', 'city', 'gender', 'qualification', 'specialization', 'onboarding_status', 'data_status')
        export_order = (
            'id', 'name', 'city', 'gender', 'qualification', 'specialization', 'onboarding_status', 'data_status')

    def dehydrate_data_status(self, doctor):
        return dict(Doctor.DATA_STATUS_CHOICES)[doctor.data_status]

    def dehydrate_onboarding_status(self, doctor):
        return dict(Doctor.ONBOARDING_STATUS)[doctor.onboarding_status]

    def dehydrate_city(self, doctor):
        return ','.join([str(h.city) for h in doctor.hospitals.distinct('city')])

    def dehydrate_specialization(self, doctor):
        return ','.join([str(h.specialization) for h in doctor.qualifications.all()])

    def dehydrate_qualification(self, doctor):
        return ','.join([str(h.qualification) for h in doctor.qualifications.all()])


class DoctorAdmin(ImportExportMixin, VersionAdmin, ActionAdmin, QCPemAdmin, nested_admin.NestedModelAdmin):
    # class DoctorAdmin(nested_admin.NestedModelAdmin):
    resource_class = DoctorResource
    change_list_template = 'superuser_import_export.html'

    list_display = (
        'name', 'updated_at', 'data_status', 'onboarding_status', 'list_created_by', 'list_assigned_to',
        'get_onboard_link')
    date_hierarchy = 'created_at'
    list_filter = (
        'data_status', 'onboarding_status', 'is_insurance_enabled', 'doctorspecializations__specialization',
        CityFilter,)
    form = DoctorForm
    inlines = [
        DoctorMobileInline,
        DoctorEmailInline,
        DoctorSpecializationInline,
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
        GenericAdminInline
    ]
    exclude = ['user', 'created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code', 'search_key']
    search_fields = ['name']

    readonly_fields = ('lead_url', 'matrix_lead_id', 'matrix_reference_id', 'about', 'is_live')

    def lead_url(self, instance):
        if instance.id:
            ref_id = instance.matrix_reference_id
            if ref_id is not None:
                html = '''<a href='/admin/lead/doctorlead/%s/change/' target=_blank>Lead Page</a>''' % (ref_id)
                return mark_safe(html)
        else:
            return mark_safe('''<span></span>''')

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
        required = ['name', 'raw_about', 'gender', 'license', 'practicing_since']
        for req in required:
            if not getattr(doctor, req):
                errors.append(req + ' is required')

        length_required = ['mobiles', 'emails', 'qualifications', 'hospitals',
                           'languages', 'experiences', 'images']

        for req in length_required:
            if not len(getattr(doctor, req).all()):
                errors.append(req + ' is required')

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
                not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists()):
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
            # obj.is_live = True
            obj.update_live_status()
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
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() and obj.data_status in (1, 2, 3):
            return True
        return obj.created_by == request.user

    class Media:
        js = ('js/admin/ondoc.js',)


class DoctorOpdAppointmentForm(forms.ModelForm):

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        time_slot_start = cleaned_data['time_slot_start']
        hour = round(float(time_slot_start.hour) + (float(time_slot_start.minute) * 1 / 60), 2)
        minutes = time_slot_start.minute
        valid_minutes_slot = TimeSlotExtraction.TIME_SPAN
        if minutes % valid_minutes_slot != 0:
            self._errors['time_slot_start'] = self.error_class(['Invalid time slot.'])
            self.cleaned_data.pop('time_slot_start', None)
        if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=self.instance.doctor,
                                                 doctor_clinic__hospital=self.instance.hospital,
                                                 day=time_slot_start.weekday(),
                                                 start__lte=hour, end__gt=hour).exists():
            raise forms.ValidationError("Doctor do not sit at the given hospital in this time slot.")
        if not DoctorClinicTiming.objects.filter(doctor_clinic__doctor=self.instance.doctor,
                                                 doctor_clinic__hospital=self.instance.hospital,
                                                 day=time_slot_start.weekday(),
                                                 start__lte=hour, end__gt=hour,
                                                 deal_price=self.instance.deal_price).exists():
            raise forms.ValidationError("Deal price is different for this time slot.")
        return cleaned_data


class DoctorOpdAppointmentAdmin(admin.ModelAdmin):
    form = DoctorOpdAppointmentForm
    list_display = ('id', 'get_profile', 'get_doctor', 'status', 'time_slot_start', 'created_at',)
    list_filter = ('status', )
    date_hierarchy = 'created_at'

    def get_profile(self, obj):
        return obj.profile.name

    get_profile.admin_order_field = 'profile'
    get_profile.short_description = 'Profile Name'

    def get_doctor(self, obj):
        return obj.doctor.name

    get_doctor.admin_order_field = 'doctor'
    get_doctor.short_description = 'Doctor Name'


    def formfield_for_choice_field(self, db_field, request, **kwargs):
        allowed_status_for_agent = [(OpdAppointment.RESCHEDULED_PATIENT, 'Rescheduled by patient'),
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
        return form

    def get_fields(self, request, obj=None):
        if request.user.is_superuser and request.user.is_staff:
            return ('doctor', 'hospital', 'profile', 'profile_detail', 'user', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status', 'status', 'time_slot_start',
                    'time_slot_end', 'payment_type', 'otp', 'insurance', 'outstanding')
        elif request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('doctor_name', 'hospital_name', 'used_profile_name', 'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_number', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status',
                    'payment_type', 'admin_information', 'otp', 'insurance', 'outstanding',
                    'status', 'time_slot_start')
        else:
            return ()

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser and request.user.is_staff:
            return ()
        elif request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('doctor_name', 'hospital_name', 'used_profile_name', 'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_number', 'booked_by',
                    'fees', 'effective_price', 'mrp', 'deal_price', 'payment_status', 'payment_type',
                    'admin_information', 'otp', 'insurance', 'outstanding')
        else:
            return ()

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

    def admin_information(self, obj):
        doctor_admins = auth_model.GenericAdmin.get_appointment_admins(obj)
        doctor_admins_phone_numbers = list()
        for doctor_admin in doctor_admins:
            doctor_admins_phone_numbers.append(doctor_admin.phone_number)
        return mark_safe(','.join(doctor_admins_phone_numbers))


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


class GeneralSpecializationResource(resources.ModelResource):
    class Meta:
        model = GeneralSpecialization
        fields = ('id', 'name')


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
