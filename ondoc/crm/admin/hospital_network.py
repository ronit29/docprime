from django.contrib.gis import admin
from django.contrib.gis import forms
from django.db import models
from reversion.admin import VersionAdmin
from django.db.models import Q

from ondoc.doctor.models import (HospitalNetworkManager, HospitalNetwork,
    HospitalNetworkHelpline, HospitalNetworkEmail, HospitalNetworkAccreditation,
    HospitalNetworkAward, HospitalNetworkCertification)

from .common import *


class HospitalNetworkCertificationInline(admin.TabularInline):
    model = HospitalNetworkCertification
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalNetworkAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class HospitalNetworkAwardInline(admin.TabularInline):
    model = HospitalNetworkAward
    form = HospitalNetworkAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalNetworkAccreditationInline(admin.TabularInline):
    model = HospitalNetworkAccreditation
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalNetworkEmailInline(admin.TabularInline):
    model = HospitalNetworkEmail
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalNetworkHelplineInline(admin.TabularInline):
    model = HospitalNetworkHelpline
    extra = 0
    can_delete = True
    show_change_link = False
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }



class HospitalNetworkManagerInline(admin.TabularInline):
    model = HospitalNetworkManager
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    extra = 0
    can_delete = True
    show_change_link = False

class HospitalNetworkForm(FormCleanMixin):
    operational_since = forms.ChoiceField(choices=hospital_operational_since_choices, required=False)
    about = forms.CharField(widget=forms.Textarea, required=False)

    def validate_qc(self):
        qc_required = {'name':'req','operational_since':'req','about':'req','network_size':'req',
            'building':'req','locality':'req','city':'req','state':'req',
            'country':'req','pin_code':'req','hospitalnetworkmanager':'count',
            'hospitalnetworkhelpline':'count','hospitalnetworkemail':'count'}

        for key, value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'_set-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")


    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data


class HospitalNetworkAdmin(VersionAdmin, ActionAdmin, QCPemAdmin):
    form = HospitalNetworkForm

    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }
    list_display = ('name', 'updated_at', 'data_status', 'created_by')
    list_filter = ('data_status',)
    search_fields = ['name']
    inlines = [
        HospitalNetworkManagerInline,
        HospitalNetworkHelplineInline,
        HospitalNetworkEmailInline,
        HospitalNetworkAccreditationInline,
        HospitalNetworkAwardInline,
        HospitalNetworkCertificationInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        parent_qs = super(QCPemAdmin, self).get_queryset(request)
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return parent_qs.filter(Q(data_status=2) | Q(data_status=3) | Q(created_by=request.user))
        else:
            return qs

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

    def get_form(self, request, obj=None, **kwargs):
        form = super(HospitalNetworkAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        return form
