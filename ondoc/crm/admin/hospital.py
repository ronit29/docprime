from django.contrib.gis import admin
from reversion.admin import VersionAdmin
from django.db.models import Q
import datetime
from ondoc.crm.admin.doctor import CreatedByFilter
from ondoc.doctor.models import (HospitalImage, HospitalDocument, HospitalAward,Doctor,
    HospitalAccreditation, HospitalCertification, HospitalSpeciality, HospitalNetwork, Hospital)
from .common import *
from ondoc.crm.constants import constants
from django.utils.safestring import mark_safe
from django.contrib.admin import SimpleListFilter
from ondoc.authentication.models import GenericAdmin, User, QCModel
from ondoc.authentication.admin import BillingAccountInline


class HospitalImageInline(admin.TabularInline):
    model = HospitalImage
    # template = 'imageinline.html'
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 5


# class DcotorInline(admin.TabularInline):
#     model = DoctorHospital
#     # template = 'imageinline.html'
#     extra = 0
#     can_delete = False
#     show_change_link = False

class HospitalDocumentInline(admin.TabularInline):
    model = HospitalDocument
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class HospitalAwardInline(admin.TabularInline):
    model = HospitalAward
    form = HospitalAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalAccreditationInline(admin.TabularInline):
    model = HospitalAccreditation
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalCertificationInline(admin.TabularInline):
    model = HospitalCertification
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalSpecialityInline(admin.TabularInline):
    model = HospitalSpeciality
    extra = 0
    can_delete = True
    show_change_link = False


# class HospitalNetworkMappingInline(admin.TabularInline):
#     model = HospitalNetworkMapping
#     extra = 0
#     can_delete = True
#     show_change_link = False
class GenericAdminFormSet(forms.BaseInlineFormSet):
    def clean(self):
        appnt_manager_flag = self.instance.is_appointment_manager
        if self.cleaned_data:
            phone_number = False
            for data in self.cleaned_data:
                if data.get('phone_number') and data.get('permission_type') == GenericAdmin.APPOINTMENT:
                    phone_number = True
                    break
            if phone_number:
                if not appnt_manager_flag:
                    if not(len(self.deleted_forms) == len(self.cleaned_data)):
                        raise forms.ValidationError(
                            "'Enabled for Managing Appointment' should be set if a Admin is Entered.")
            else:
                if appnt_manager_flag:
                    raise forms.ValidationError(
                        "An Admin phone number is required if 'Enabled for Managing Appointment' Field is Set.")
        else:
            if appnt_manager_flag:
                raise forms.ValidationError("An Admin phone number is required if 'Enabled for Managing Appointment' Field is Set.")
        if len(self.deleted_forms) == len(self.cleaned_data):
            if appnt_manager_flag:
                raise forms.ValidationError(
                    "An Admin phone number is required if 'Enabled for Managing Appointment' Field is Set.")


class GenericAdminInline(admin.TabularInline):
    model = GenericAdmin
    extra = 0
    can_delete = True
    show_change_link = False
    formset = GenericAdminFormSet
    readonly_fields = ['user']
    verbose_name_plural = "Admins"
    fields = ['phone_number', 'permission_type', 'read_permission', 'write_permission', 'user']

    def get_queryset(self, request):
        return super(GenericAdminInline, self).get_queryset(request).select_related('doctor', 'hospital').filter(doctor=None)


class HospitalForm(FormCleanMixin):
    operational_since = forms.ChoiceField(required=False, choices=hospital_operational_since_choices)

    def clean_location(self):
        data = self.cleaned_data['location']
        # if data == '':
        #    return None
        return data

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data

    def validate_qc(self):
        qc_required = {'name': 'req', 'location': 'req', 'operational_since': 'req', 'parking': 'req',
                       'registration_number': 'req', 'building': 'req', 'locality': 'req', 'city': 'req',
                       'state': 'req',
                       'country': 'req', 'pin_code': 'req', 'hospital_type': 'req', 'network_type': 'req'}

        # if (not self.instance.network or not self.instance.network.is_billing_enabled) and self.instance.is_billing_enabled:
        #     qc_required.update({
        #         'hospital_documents': 'count'
        #     })

        if self.instance.network and self.instance.network.data_status != QCModel.QC_APPROVED:
            raise forms.ValidationError("Hospital Network is not QC approved.")

        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if self.data.get(key+'_set-TOTAL_FORMS') and value=='count' and int(self.data[key+'_set-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
            if self.data.get(key+'-TOTAL_FORMS') and value == 'count' and int(self.data.get(key+'-TOTAL_FORMS')) <= 0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type']==2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Hospital")


class HospCityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'city'

    def lookups(self, request, model_admin):
        cities = set([(c['city'].upper(),c['city'].upper()) if(c.get('city')) else ('','') for c in Hospital.objects.all().values('city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(city__iexact=self.value()).distinct()

class HospitalAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):
    list_filter = ('data_status', HospCityFilter, CreatedByFilter)
    readonly_fields = ('associated_doctors', 'is_live', )
    exclude = ('search_key', 'live_at', 'qc_approved_at' )

    def associated_doctors(self, instance):
        if instance.id:
            html = "<ul style='margin-left:0px !important'>"
            for doc in Doctor.objects.filter(hospitals=instance.id).distinct():
                html += "<li><a target='_blank' href='/admin/doctor/doctor/%s/change'>%s</a></li>"% (doc.id, doc.name)
            html += "</ul>"
            return mark_safe(html)
        else:
            return ''

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if not obj.assigned_to:
            obj.assigned_to = request.user
        if '_submit_for_qc' in request.POST:
            obj.data_status = 2
        if '_qc_approve' in request.POST:
            obj.data_status = 3
            #obj.is_live = True
            #obj.live_at = datetime.datetime.now()
            obj.qc_approved_at = datetime.datetime.now()
        if '_mark_in_progress' in request.POST:
            obj.data_status = 1
        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # parent_qs = super(QCPemAdmin, self).get_queryset(request)
        # if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
        #     return parent_qs.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user)).prefetch_related('assoc_doctors')
        # else:
        #     return qs.prefetch_related('assoc_doctors')
        return qs.prefetch_related('assoc_doctors')

    def get_form(self, request, obj=None, **kwargs):
        form = super(HospitalAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['network'].queryset = HospitalNetwork.objects.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user))
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if (not request.user.is_superuser) and (not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists()):
            form.base_fields['assigned_to'].disabled = True
        return form

    def doctor_count(self, instance):
        if instance.id:
            count  = len(set(instance.assoc_doctors.values_list('id', flat=True)))
            #count = DoctorHospital.objects.filter(hospital_id=instance.id).count()
            return count

        else:
            return ''


    list_display = ('name', 'updated_at', 'data_status', 'doctor_count', 'list_created_by', 'list_assigned_to')
    form = HospitalForm
    search_fields = ['name']
    inlines = [
        # HospitalNetworkMappingInline,
        HospitalSpecialityInline,
        HospitalAwardInline,
        HospitalAccreditationInline,
        HospitalImageInline,
        HospitalDocumentInline,
        HospitalCertificationInline,
        GenericAdminInline,
        BillingAccountInline
    ]

    map_width = 200
    map_template = 'admin/gis/gmap.html'
    extra_js = ['js/admin/GoogleMap.js','https://maps.googleapis.com/maps/api/js?key=AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA&callback=initGoogleMap']
