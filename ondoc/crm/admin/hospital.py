from django.contrib.gis import admin
from reversion.admin import VersionAdmin
from django.db.models import Q
from ondoc.doctor.models import (HospitalImage, HospitalDocument, HospitalAward,
    HospitalAccreditation, HospitalCertification, HospitalSpeciality, HospitalNetwork, Doctor)
from .common import *
from ondoc.crm.constants import constants

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
        qc_required = {'name':'req','location':'req','operational_since':'req','parking':'req',
            'registration_number':'req','building':'req','locality':'req','city':'req','state':'req',
            'country':'req','pin_code':'req','hospital_type':'req','network_type':'req','hospitalimage':'count'}
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'_set-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type']==2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Hospital")


class HospitalAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):
    list_filter = ('data_status',)
    readonly_fields = ('associated_doctors',)

    def associated_doctors(self, instance):
        if instance.id:
            html = "<ul style='margin-left:0px !important'>"
            for doc in Doctor.objects.filter(hospitals=instance.id):
                html += "<li><a target='_blank' href='/admin/doctor/doctor/%s/change'>%s</a></li>"% (doc.id, doc.name)
            html += "</ul>"
            return mark_safe(html)
        else:
            return ''

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
    #
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        parent_qs = super(QCPemAdmin, self).get_queryset(request)
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return parent_qs.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user))
        else:
            return qs

    def get_form(self, request, obj=None, **kwargs):
        form = super(HospitalAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['network'].queryset = HospitalNetwork.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        return form

    list_display = ('name', 'updated_at', 'data_status', 'list_created_by')
    form = HospitalForm
    search_fields = ['name']
    inlines = [
        # HospitalNetworkMappingInline,
        HospitalSpecialityInline,
        HospitalAwardInline,
        HospitalAccreditationInline,
        HospitalImageInline,
        HospitalDocumentInline,
        HospitalCertificationInline]

    map_width = 200
    map_template = 'admin/gis/gmap.html'
    extra_js = ['js/admin/GoogleMap.js','https://maps.googleapis.com/maps/api/js?key=AIzaSyAfoicJaTk8xQOoAOQn9vtHJzgTeZDJRtA&callback=initGoogleMap']
