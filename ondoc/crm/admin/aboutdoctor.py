from ondoc.authentication.models import User, QCModel
from ondoc.doctor import models as doctor_model
from ondoc.crm.admin.doctor import CityFilter
from django.contrib.admin import SimpleListFilter
from django import forms
from django.db.models import Q
import nested_admin


class AboutDoctorForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea, required=False)


class ReadOnlySpecializationInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorSpecialization
    can_delete = False
    readonly_fields = ['doctor', 'specialization']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorQualificationInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorQualification
    can_delete = False
    readonly_fields = ['doctor', 'qualification', 'specialization', 'college', 'passing_year']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorClinicTimingInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorClinicTiming
    # form = DoctorClinicTimingForm
    extra = 0
    can_delete = False
    show_change_link = False
    readonly_fields = ['doctor_clinic', 'day', 'start', 'end', 'fees', 'deal_price', 'mrp',
                       'followup_duration', 'followup_charges']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorClinicInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorClinic
    extra = 0
    can_delete = False
    show_change_link = False
    autocomplete_fields = ['hospital']
    readonly_fields = ['doctor', 'hospital']
    inlines = [ReadOnlyDoctorClinicTimingInline]

    def has_add_permission(self, request):
        return False

    def get_queryset(self, request):
        return super(ReadOnlyDoctorClinicInline, self).get_queryset(request).select_related('hospital')


class ReadOnlyDoctorLanguageInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorLanguage
    can_delete = False
    readonly_fields = ['doctor', 'language']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorAwardInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorAward
    can_delete = False
    readonly_fields = ['doctor', 'name', 'year']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorAssociationInline(nested_admin.NestedTabularInline):
    model = doctor_model.DoctorAssociation
    can_delete = False
    readonly_fields = ['doctor', 'name']

    def has_add_permission(self, request):
        return False


class ReadOnlyDoctorExperienceInline(nested_admin.NestedTabularInline):
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


class AboutDoctorAdmin(nested_admin.NestedModelAdmin):
    list_display = ('name', 'updated_at', 'data_status', 'onboarding_status', 'about')
    list_filter = ('data_status', 'onboarding_status', AboutListFilter, CityFilter)
    form = AboutDoctorForm
    exclude = ['user', 'created_by', 'is_phone_number_verified', 'is_email_verified', 'country_code',
               'additional_details', 'is_insurance_enabled', 'is_retail_enabled', 'is_online_consultation_enabled',
               'online_consultation_fees', 'matrix_lead_id', 'matrix_reference_id', 'assigned_to', 'search_key',
               'is_live', 'is_internal']
    search_fields = ['name']
    inlines = [ReadOnlySpecializationInline,
               ReadOnlyDoctorQualificationInline,
               ReadOnlyDoctorLanguageInline,
               ReadOnlyDoctorAwardInline,
               ReadOnlyDoctorAssociationInline,
               ReadOnlyDoctorExperienceInline,
               ReadOnlyDoctorClinicInline
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
