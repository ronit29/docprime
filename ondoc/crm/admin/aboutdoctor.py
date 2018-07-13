from ondoc.authentication.models import User, QCModel
from ondoc.doctor import models as doctor_model
from ondoc.crm.admin.doctor import CityFilter
from reversion.admin import admin, VersionAdmin
from django.contrib.admin import SimpleListFilter
from django import forms
from django.db.models import Q


class AboutDoctorForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea, required=False)


class ReadOnlySpecializationInline(admin.TabularInline):
    model = doctor_model.DoctorSpecialization
    can_delete = False
    readonly_fields = ['doctor', 'specialization']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorQualificationInline(admin.TabularInline):
    model = doctor_model.DoctorQualification
    can_delete = False
    readonly_fields = ['doctor', 'qualification', 'specialization', 'college', 'passing_year']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorHospitalInline(admin.TabularInline):
    model = doctor_model.DoctorHospital
    can_delete = False
    readonly_fields = ['doctor', 'hospital', 'day', 'start', 'end', 'fees', 'deal_price', 'mrp',
                       'followup_duration', 'followup_charges']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorLanguageInline(admin.TabularInline):
    model = doctor_model.DoctorLanguage
    can_delete = False
    readonly_fields = ['doctor', 'language']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorAwardInline(admin.TabularInline):
    model = doctor_model.DoctorAward
    can_delete = False
    readonly_fields = ['doctor', 'name', 'year']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorAssociationInline(admin.TabularInline):
    model = doctor_model.DoctorAssociation
    can_delete = False
    readonly_fields = ['doctor', 'name']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorExperienceInline(admin.TabularInline):
    model = doctor_model.DoctorExperience
    can_delete = False
    readonly_fields = ['doctor', 'hospital', 'start_year', 'end_year']

    def has_add_permission(self, request):
        return False


class AboutListFilter(SimpleListFilter):
    title = "blank"

    parameter_name = 'about'

    def lookups(self, request, model_admin):

        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):

        if self.value() == 'yes':
            return queryset.filter(Q(about__isnull=True) | Q(about=''))

        if self.value() == 'no':
            return queryset.filter(~Q(about=''))


class AboutDoctorAdmin(VersionAdmin):
    list_display = ('name', 'updated_at', 'data_status', 'onboarding_status', 'about')
    list_filter = ('data_status', 'onboarding_status', AboutListFilter, CityFilter)
    form = AboutDoctorForm
    exclude = ['user', 'created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code',
               'additional_details', 'is_insurance_enabled', 'is_retail_enabled', 'is_online_consultation_enabled',
               'online_consultation_fees', 'matrix_lead_id', 'matrix_reference_id', 'assigned_to', ]
    search_fields = ['name']
    inlines = [ReadOnlySpecializationInline,
               ReadOnlyDoctorQualificationInline,
               ReadOnlyDoctorHospitalInline,
               ReadOnlyDoctorLanguageInline,
               ReadOnlyDoctorAwardInline,
               ReadOnlyDoctorAssociationInline,
               ReadOnlyDoctorExperienceInline
               ]
    readonly_fields = ('name', 'gender', 'practicing_since', 'raw_about', 'license', 'onboarding_status')

    def get_queryset(self, request):
        qs = super(AboutDoctorAdmin, self).get_queryset(request)
        return qs.filter(Q(data_status=QCModel.SUBMITTED_FOR_QC) | Q(data_status=QCModel.QC_APPROVED) |
                         Q(onboarding_status=doctor_model.Doctor.ONBOARDED) |
                         Q(onboarding_status=doctor_model.Doctor.REQUEST_SENT))

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.groups.filter(name='about_doctor_team').exists():
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False
