from django.contrib.gis import admin
from django.contrib.gis import forms
from django.contrib.gis.db import models
from ondoc.doctor.models import Doctor, Qualification, Specialization, DoctorQualification, Hospital, DoctorHospital, DoctorLanguage, Language, DoctorAward, DoctorAssociation, DoctorExperience, DoctorMedicalService, MedicalService, DoctorImage, DoctorDocument, HospitalImage, HospitalDocument, OpdAppointment
from ondoc.authentication.models import StaffProfile, UserProfile
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from reversion.admin import VersionAdmin
from django.core.exceptions import FieldDoesNotExist
from django.db.models import Q

import datetime
from ondoc.crm.constants import constants

# from django.dispatch import receiver
# from django.db.models.signals import post_save

from django.contrib.auth import get_user_model
User = get_user_model()


class ActionAdmin(admin.ModelAdmin):

    actions = ['submit_for_qc','qc_approve', 'mark_in_progress']

    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_superuser and request.user.is_staff:
            return actions

        if 'delete_selected' in actions:
            del actions['delete_selected']

        # check if member of QC Team
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            if 'submit_for_qc' in actions:
                del actions['submit_for_qc']
            return actions

        # if field team member
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            if 'qc_approve' in actions:
                del actions['qc_approve']
            if 'mark_in_progress' in actions:
                del actions['mark_in_progress']
            return actions

        return {}

    def mark_in_progress(self, request, queryset):
        rows_updated = queryset.filter(data_status=2).update(data_status=1)
        if rows_updated == 1:
            message_bit = "1 record was "
        else:
            message_bit = "%s records were" % rows_updated
        self.message_user(request, "%s sent back for information collection." % message_bit)

    mark_in_progress.short_description = "Send back for information collection";


    def submit_for_qc(self, request, queryset):
        rows_updated = queryset.filter(data_status=1).update(data_status=2)
        if rows_updated == 1:
            message_bit = "1 record was "
        else:
            message_bit = "%s records were" % rows_updated
        self.message_user(request, "%s submitted for Quality Check." % message_bit)

    submit_for_qc.short_description = "Submit for Quality Check";


    def qc_approve(self, request, queryset):
        rows_updated = queryset.filter(data_status=2).update(data_status=3)
        if rows_updated == 1:
            message_bit = "1 record was "
        else:
            message_bit = "%s records were" % rows_updated
        self.message_user(request, "%s approved Quality Check." % message_bit)

    qc_approve.short_description = "Approve Quality Check";

    class Meta:
        abstract = True


class DoctorQualificationInline(admin.TabularInline):
    model = DoctorQualification
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

class DoctorAwardInline(admin.TabularInline):
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
    start_year = forms.IntegerField(min_value=1950,max_value=datetime.datetime.now().year)
    end_year = forms.IntegerField(min_value=1950,max_value=datetime.datetime.now().year)

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

class DoctorForm(forms.ModelForm):
    additional_details = forms.CharField(widget=forms.Textarea, required=False)
    about = forms.CharField(widget=forms.Textarea, required=False)
    registration_details = forms.CharField(widget=forms.Textarea, required=False)
    practice_duration = forms.IntegerField(required=False, min_value=1, max_value=100)
    phone_number = forms.IntegerField(widget=forms.TextInput, required=False, min_value=1000000000, max_value=9999999999)
    
    def clean(self):
        if not self.request.user.is_superuser and self.instance.data_status==3:
            raise forms.ValidationError("Cannot modify QC approved Data")
        return super(DoctorForm, self).clean()


class DoctorAdmin(VersionAdmin, ActionAdmin):

    list_display = ('name', 'updated_at','data_status', 'created_by')
    date_hierarchy = 'created_at'
    list_filter = ('data_status',)
    form = DoctorForm
    inlines = [
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
            return qs.filter(data_status=1,created_by=request.user )

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user

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


class HospitalImageInline(admin.TabularInline):
    model = HospitalImage
    template = 'imageinline.html'
    extra = 0
    can_delete = True
    show_change_link = False

class HospitalDocumentInline(admin.TabularInline):
    model = HospitalDocument
    extra = 0
    can_delete = True
    show_change_link = False

class HospitalForm(forms.ModelForm):
    address = forms.CharField(widget=forms.Textarea)

    def clean(self):
        if self.request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            if self.instance.data_status in (2,3):
                raise forms.ValidationError("Cannot update Hospital submitted for QC approval")
            if self.instance.created_by != self.request.user:
                raise forms.ValidationError("Cannot modify Hospital added by other users")

        if self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            if self.instance.data_status == 3:
                raise forms.ValidationError("Cannot update QC approved hospital")

        return super(HospitalForm, self).clean()



class HospitalAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin):

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)

        if request.user.is_superuser:
            return qs
        if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            return qs.filter(Q(data_status=2) | Q(data_status=3))
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return qs.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user))

    def get_form(self, request, obj=None, **kwargs):
        form = super(HospitalAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        return form

    list_display = ('name', 'updated_at', 'data_status', 'created_by')
    form = HospitalForm
    search_fields = ['name', 'address']
    inlines = [
        HospitalImageInline,
        HospitalDocumentInline]

    map_width = 200
    map_template = 'admin/gis/gmap.html'
    extra_js = ['js/admin/GoogleMap.js','https://maps.googleapis.com/maps/api/js?key=AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA&callback=initGoogleMap']

class StaffProfileInline(admin.TabularInline):
    model = StaffProfile
    extra = 0
    can_delete = False
    show_change_link = False


class CustomUserChangeForm(UserChangeForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.email is None:
            self.instance.email = ''
            kwargs['instance'] = self.instance
            super(CustomUserChangeForm, self).__init__(*args, **kwargs)

    def clean_email(self):
        if self.initial["email"] is None:
            return ''
        return self.initial["email"]


class CustomUserAdmin(UserAdmin,VersionAdmin):
    list_display = ('email',)
    list_filter = ('is_staff', 'is_superuser')
    ordering = []
    inlines = [
        StaffProfileInline
    ]
    list_display = ('email','phone_number', 'is_active')
    list_select_related = ('staffprofile',)
    # form = CustomUserChangeForm
    def save_model(self, request, obj, form, change):
        if not obj.email:
            obj.email = None
        super().save_model(request, obj, form, change)

    def get_fieldsets(self, request, obj=None):
        if not obj:
            return ((None, {'fields': ('email', 'phone_number','groups','user_type','is_staff','is_active','password1','password2')}),)
        return ((None, {'fields': ('email', 'phone_number','groups', 'is_active','is_staff','password')}),)

    # readonly_fields = ['user_type']
    # exclude = ['last_login','is_superuser','user_type','is_phone_number_verified','is_staff']

    # def user_name(self, object):
       # return object.staffprofile

    def get_queryset(self, request):
        # use our manager, rather than the default one
        qs = self.model.objects.get_queryset()

        # we need this from the superclass method
        ordering = self.ordering or () # otherwise we might try to *None, which is bad ;)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs
    def get_changeform_initial_data(self, request):
        return {'user_type': 1}


class SpecializationAdmin(VersionAdmin):
    search_fields = ['name']

class MedicalServiceAdmin(VersionAdmin):
    search_fields = ['name']


# Admin Site config
admin.site.site_header = 'Ondoc CRM'
admin.site.site_title = 'Ondoc CRM'
admin.site.site_url = None
admin.site.index_title = 'CRM Administration'



admin.site.register(Doctor, DoctorAdmin)
admin.site.register(Qualification)
# admin.site.register(Specialization)
admin.site.register(Hospital, HospitalAdmin)
admin.site.register(User, CustomUserAdmin)
admin.site.register(UserProfile)
admin.site.register(Language)
admin.site.register(OpdAppointment)
admin.site.register(MedicalService, MedicalServiceAdmin)
# admin.site.register(DoctorMedicalService)
admin.site.register(Specialization, SpecializationAdmin)
# admin.site.register(DoctorImage)
# admin.site.register(Image)