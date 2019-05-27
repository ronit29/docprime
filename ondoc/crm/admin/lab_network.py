from django.contrib.gis import forms
from django.contrib.gis import admin
from django.utils.safestring import mark_safe
from reversion.admin import VersionAdmin
from django.db.models import Q
from django.db import models
import datetime
from ondoc.crm.admin.doctor import CreatedByFilter
from ondoc.crm.admin.lab import HomePickupChargesInline
from ondoc.diagnostic.models import (Lab, LabNetworkCertification,
                                     LabNetworkAward, LabNetworkAccreditation, LabNetworkEmail,
                                     LabNetworkHelpline, LabNetworkManager, LabNetworkDocument, LabNetwork)
from .common import *
from ondoc.authentication.models import GenericAdmin, User, GenericLabAdmin, AssociatedMerchant
from django.contrib.contenttypes.admin import GenericTabularInline

from ondoc.authentication.admin import SPOCDetailsInline
import nested_admin
from .common import AssociatedMerchantInline, RemarkInline

class LabNetworkCertificationInline(admin.TabularInline):
    model = LabNetworkCertification
    extra = 0
    can_delete = True
    show_change_link = False


class LabNetworkAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class LabNetworkAwardInline(admin.TabularInline):
    model = LabNetworkAward
    form = LabNetworkAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class LabNetworkAccreditationInline(admin.TabularInline):
    model = LabNetworkAccreditation
    extra = 0
    can_delete = True
    show_change_link = False


class LabNetworkEmailInline(admin.TabularInline):
    model = LabNetworkEmail
    extra = 0
    can_delete = True
    show_change_link = False


class LabNetworkHelplineInline(admin.TabularInline):
    model = LabNetworkHelpline
    extra = 0
    can_delete = True
    show_change_link = False
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }


# class GenericAdminInline(admin.TabularInline):
#     model = GenericAdmin
#     extra = 0
#     can_delete = True
#     show_change_link = False
#     readonly_fields = ['user']
#     verbose_name_plural = "Admins"


class LabNetworkManagerInline(admin.TabularInline):
    model = LabNetworkManager
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    extra = 0
    can_delete = True
    show_change_link = False


class LabNetworkForm(FormCleanMixin):
    operational_since = forms.ChoiceField(choices=hospital_operational_since_choices, required=False)
    about = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = LabNetwork
        exclude = ()
        widgets = {
            'matrix_state': autocomplete.ModelSelect2(url='matrix-state-autocomplete'),
            'matrix_city': autocomplete.ModelSelect2(url='matrix-city-autocomplete', forward=['matrix_state'])
        }

    def validate_qc(self):
        qc_required = {'name': 'req', 'operational_since': 'req', 'about': 'req', 'network_size': 'req',
                       'building': 'req', 'locality': 'req',
                       'matrix_city': 'req', 'matrix_state': 'req',
                       'country': 'req', 'pin_code': 'req', 'labnetworkmanager': 'count',
                       'labnetworkhelpline': 'count', 'labnetworkemail': 'count'}

        # if self.instance.is_billing_enabled:
        #     qc_required.update({
        #         'lab_documents': 'count'
        #     })

        for key, value in qc_required.items():
            if value == 'req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key + " is required for Quality Check")
            if self.data.get(key + '_set-TOTAL_FORMS') and value == 'count' and int(
                    self.data[key + '_set-TOTAL_FORMS']) <= 0:
                raise forms.ValidationError("Atleast one entry of " + key + " is required for Quality Check")
            if self.data.get(key + '-TOTAL_FORMS') and value == 'count' and int(
                    self.data.get(key + '-TOTAL_FORMS')) <= 0:
                raise forms.ValidationError("Atleast one entry of " + key + " is required for Quality Check")

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data


class LabNetworkDocumentFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        choices = dict(LabNetworkDocument.CHOICES)
        count = {}
        for key, value in LabNetworkDocument.CHOICES:
            count[key] = 0

        for value in self.cleaned_data:
            if value and not value['DELETE']:
                count[value['document_type']] += 1

        for key, value in count.items():
            if not key == LabNetworkDocument.ADDRESS and value > 1:
                raise forms.ValidationError("Only one " + choices[key] + " is allowed")

        # if self.instance.is_billing_enabled:
        #     if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
        #         for key, value in count.items():
        #             if not key==LabNetworkDocument.GST and value<1:
        #                 raise forms.ValidationError(choices[key]+" is required")


class LabNetworkDocumentInline(admin.TabularInline):
    model = LabNetworkDocument
    formset = LabNetworkDocumentFormSet
    # form = LabDocumentForm
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

    extra = 0
    can_delete = True
    show_change_link = False


class GenericLabNetworkAdminFormSet(forms.BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        # current_lab_network_id = self.instance.id
        # if current_lab_network_id:
        #     associated_labs = Lab.objects.filter(network=current_lab_network_id).prefetch_related('manageable_lab_admins')
        #     if associated_labs.exists():
        #         is_lab_network_admin = False
        #         for value in self.cleaned_data:
        #             if value and not value['DELETE']:
        #                 is_lab_network_admin = True
        #                 break
        #         if is_lab_network_admin:
        #             is_disabled_value = True
        #         else:
        #             is_disabled_value = False
        #         for lab in associated_labs:
        #             lab.manageable_lab_admins.update(is_disabled=is_disabled_value)


class GenericLabNetworkAdminInline(admin.TabularInline):
    model = GenericLabAdmin
    formset = GenericLabNetworkAdminFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    readonly_fields = ['user']
    verbose_name_plural = "Admins"
    fields = ['user', 'phone_number', 'lab_network', 'super_user_permission', 'permission_type', 'read_permission', 'write_permission']


class LabNetworkAdmin(VersionAdmin, ActionAdmin, QCPemAdmin):
    form = LabNetworkForm
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }
    list_display = ('name', 'updated_at', 'data_status', 'list_created_by', 'list_assigned_to')
    list_filter = ('data_status', CreatedByFilter)
    search_fields = ['name']
    readonly_fields = ('no_of_associated_labs', 'associated_labs', 'city', 'state')
    exclude = ('qc_approved_at', )

    def no_of_associated_labs(self, instance):
        if instance.id:
            return instance.all_associated_labs().count()
    no_of_associated_labs.short_description = 'No. of associated lab(s)'

    def associated_labs(self, instance):
        if instance.id:
            html = "<ul style='margin-left:0px !important'>"
            for lab in instance.all_associated_labs():
                html += "<li><a target='_blank' href='/admin/diagnostic/lab/%s/change'>%s</a></li>" % (lab.id, lab.name)
            html += "</ul>"
            return mark_safe(html)
        else:
            return ''

    inlines = [LabNetworkManagerInline,
               LabNetworkHelplineInline,
               LabNetworkEmailInline,
               LabNetworkAccreditationInline,
               LabNetworkAwardInline,
               LabNetworkCertificationInline,
               HomePickupChargesInline,
               LabNetworkDocumentInline,
               GenericLabNetworkAdminInline,
               SPOCDetailsInline,
               AssociatedMerchantInline,
               RemarkInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # parent_qs = super(QCPemAdmin, self).get_queryset(request)
        # if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
        #         return parent_qs.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user))
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
        form = super(LabNetworkAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if (not request.user.is_superuser) and (not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists()):
            form.base_fields['assigned_to'].disabled = True
        return form
