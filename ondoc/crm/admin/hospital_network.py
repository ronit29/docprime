from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.gis import admin
from django.contrib.gis import forms
from django.db import models
from django.utils.safestring import mark_safe
from reversion.admin import VersionAdmin
from django.db.models import Q
from ondoc.authentication.models import GenericAdmin, User, AssociatedMerchant, QCModel, SPOCDetails
from ondoc.crm.admin.doctor import CreatedByFilter

from ondoc.doctor.models import (HospitalNetworkManager, Hospital,
                                 HospitalNetworkHelpline, HospitalNetworkEmail, HospitalNetworkAccreditation,
                                 HospitalNetworkAward, HospitalNetworkCertification, HospitalNetworkDocument,
                                 HospitalNetworkImage, HospitalNetworkTiming, HospitalNetworkServiceMapping,
                                 HospitalNetworkSpeciality, HospitalCertification)
import datetime
from .common import *
from ondoc.authentication.admin import SPOCDetailsInline
import nested_admin
from .common import AssociatedMerchantInline
import logging
logger = logging.getLogger(__name__)


class HospitalNetworkCertificationInlineFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        for data in self.cleaned_data:
            hospital_obj = Hospital.objects.filter(network_id=data.get('network').id)
            for hosp in hospital_obj:
                HospitalCertification.objects.get_or_create(hospital=hosp, certification=data.get('id').certification)


class HospitalNetworkCertificationInline(admin.TabularInline):
    model = HospitalNetworkCertification
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['certification']
    search_fields = ['certification']
    formset = HospitalNetworkCertificationInlineFormSet

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('network')


class HospitalNetworkAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class HospitalNetworkAwardInline(admin.TabularInline):
    model = HospitalNetworkAward
    form = HospitalNetworkAwardForm
    extra = 0
    can_delete = True
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('network')


class HospitalNetworkAccreditationInline(admin.TabularInline):
    model = HospitalNetworkAccreditation
    extra = 0
    can_delete = True
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('network')


class HospitalNetworkEmailInline(admin.TabularInline):
    model = HospitalNetworkEmail
    extra = 0
    can_delete = True
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('network')


class HospitalNetworkHelplineInline(admin.TabularInline):
    model = HospitalNetworkHelpline
    extra = 0
    can_delete = True
    show_change_link = False
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('network')


class HospitalNetworkTimingInlineFormSet(forms.BaseInlineFormSet):
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


class HospitalNetworkTimingInline(admin.TabularInline):
    model = HospitalNetworkTiming
    formset = HospitalNetworkTimingInlineFormSet
    fk_name = 'network'
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalNetworkServiceInline(admin.TabularInline):
    model = HospitalNetworkServiceMapping
    fk_name = 'network'
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['service']
    verbose_name = "Hospital Network Facility"
    verbose_name_plural = "Hospital Network Facilities"


class HospitalSpecialityInline(admin.TabularInline):
    model = HospitalNetworkSpeciality
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalNetworkImageInline(admin.TabularInline):
    model = HospitalNetworkImage
    readonly_fields = ['cropped_image']
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 10



class HospitalNetworkManagerInline(admin.TabularInline):
    model = HospitalNetworkManager
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    extra = 0
    can_delete = True
    show_change_link = False


    def get_queryset(self, request):
        return super().get_queryset(request).select_related('network')


class GenericAdminInline(admin.TabularInline):
    model = GenericAdmin
    extra = 0
    can_delete = True
    show_change_link = False
    readonly_fields = ['user']
    verbose_name_plural = "Admins"

    def get_queryset(self, request):
        from ondoc.api.v1.utils import GenericAdminEntity
        return super().get_queryset(request).select_related('doctor', 'hospital_network', 'user').filter(entity_type=GenericAdminEntity.HOSPITAL)


class HospitalNetworkForm(FormCleanMixin):
    operational_since = forms.ChoiceField(choices=hospital_operational_since_choices, required=False)
    about = forms.CharField(widget=forms.Textarea, required=False)

    class Media:
        extend = True
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'hospital_network/js/init.js')
        css = {'all': ('hospital_network/css/style.css',)}

    class Meta:
        widgets = {
            'matrix_state': autocomplete.ModelSelect2(url='matrix-state-autocomplete'),
            'matrix_city': autocomplete.ModelSelect2(url='matrix-city-autocomplete', forward=['matrix_state'])
        }

    def validate_qc(self):
        qc_required = {'name': 'req', 'operational_since': 'req', 'about': 'req', 'network_size': 'req',
                       'building': 'req', 'locality': 'req',
                       'country': 'req', 'pin_code': 'req', 'hospitalnetworkmanager': 'count',
                       'hospitalnetworkhelpline': 'count', 'hospitalnetworkemail': 'count',
                       'matrix_city': 'req', 'matrix_state': 'req', 'hospitalnetworkmanager_set': 'count',
                       'matrix_lead_id': 'value_req'}

        # if self.instance.is_billing_enabled:
        #     qc_required.update({
        #         'hospital_network_documents': 'count'
        #     })

        for key, value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if self.data.get(key+'_set-TOTAL_FORMS') and value=='count' and int(self.data[key+'_set-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
            if self.data.get(key+'-TOTAL_FORMS') and value == 'count' and int(self.data.get(key+'-TOTAL_FORMS')) <= 0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
            if value == 'value_req':
                if hasattr(self.instance, key) and not getattr(self.instance, key):
                    raise forms.ValidationError(key + " is required for Quality Check")

        # number_of_spocs = self.data.get('hospitalnetworkmanager_set-TOTAL_FORMS', '0')
        # try:
        #     number_of_spocs = int(number_of_spocs)
        # except Exception as e:
        #     logger.error("Something went wrong while counting SPOCs for hospital - " + str(e))
        #     raise forms.ValidationError("Something went wrong while counting SPOCs.")
        # if number_of_spocs > 0:
        #     if not any([self.data.get('hospitalnetworkmanager_set-{}-contact_type'.format(i),
        #                               0) == str(2) and self.data.get(
        #         'hospitalnetworkmanager_set-{}-number'.format(i)) for i in
        #                 range(number_of_spocs)]):
        #         raise forms.ValidationError("Must have Single Point Of Contact number.")

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data


class HospitalNetworkDocumentFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        choices = dict(HospitalNetworkDocument.CHOICES)
        count = {}
        for key, value in HospitalNetworkDocument.CHOICES:
            count[key] = 0

        for value in self.cleaned_data:
            if value and not value['DELETE']:
                count[value['document_type']] += 1

        for key, value in count.items():
            if not key == HospitalNetworkDocument.ADDRESS and value > 1:
                raise forms.ValidationError("Only one " + choices[key] + " is allowed")

        if self.instance.is_billing_enabled:
            if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
               for key, value in count.items():
                   if not key == HospitalNetworkDocument.GST and value < 1:
                       raise forms.ValidationError(choices[key] + " is required")


class HospitalNetworkDocumentInline(admin.TabularInline):
    # formset = HospitalNetworkDocumentFormSet

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

    model = HospitalNetworkDocument
    extra = 0
    can_delete = True
    show_change_link = False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('hospital_network')


class HospitalNetworkAdmin(VersionAdmin, ActionAdmin, QCPemAdmin):
    form = HospitalNetworkForm

    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }
    list_display = ('name', 'welcome_calling_done', 'updated_at', 'data_status', 'list_created_by', 'list_assigned_to')
    list_filter = ('data_status', 'welcome_calling_done', CreatedByFilter)
    search_fields = ['name']
    exclude = ('qc_approved_at', 'welcome_calling_done_at', 'physical_agreement_signed_at')
    # autocomplete_fields = ['matrix_city', 'matrix_state']
    inlines = [
        HospitalNetworkImageInline,
        HospitalNetworkTimingInline,
        HospitalNetworkServiceInline,
        HospitalSpecialityInline,
        HospitalNetworkManagerInline,
        HospitalNetworkHelplineInline,
        HospitalNetworkEmailInline,
        HospitalNetworkAccreditationInline,
        HospitalNetworkAwardInline,
        HospitalNetworkCertificationInline,
        HospitalNetworkDocumentInline,
        #GenericAdminInline,
        SPOCDetailsInline,
        AssociatedMerchantInline,
        RemarkInline
    ]

    def associated_hospitals(self, instance):
        if instance.id:
            html = "<ul style='margin-left:0px !important'>"
            for hosp in Hospital.objects.filter(network=instance.id).distinct():
                html += "<li><a target='_blank' href='/admin/doctor/hospital/%s/change'>%s</a></li>"% (hosp.id, hosp.name)
            html += "</ul>"
            return mark_safe(html)
        else:
            return ''

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ('associated_hospitals', 'city', 'state', 'matrix_lead_id',)
        list_readonly = list(readonly_fields)
        if request.user.is_member_of(constants['SUPER_QC_GROUP']) or request.user.is_superuser:
            list_readonly.remove('matrix_lead_id')
        return tuple(list_readonly)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # parent_qs = super(QCPemAdmin, self).get_queryset(request)
        # if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
        #     return parent_qs.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user))
        # else:
        #     return qs
        return qs

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if not obj.assigned_to:
            obj.assigned_to = request.user
        if '_submit_for_qc' in request.POST:
            obj.data_status = QCModel.SUBMITTED_FOR_QC
        if '_qc_approve' in request.POST:
            obj.data_status = QCModel.QC_APPROVED
            obj.qc_approved_at = datetime.datetime.now()
        if '_mark_in_progress' in request.POST:
            obj.data_status = QCModel.REOPENED
        obj.status_changed_by = request.user
        obj.city = obj.matrix_city.name
        obj.state = obj.matrix_state.name

        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super(HospitalNetworkAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if (not request.user.is_superuser) and (not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists()):
            form.base_fields['assigned_to'].disabled = True
        return form

    def get_fields(self, request, obj=None):
        all_fields = super().get_fields(request, obj)
        if not request.user.is_superuser and not request.user.groups.filter(name=constants['WELCOME_CALLING_TEAM']).exists():
            if 'welcome_calling_done' in all_fields:
                all_fields.remove('welcome_calling_done')
        return all_fields