from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.gis import admin
from reversion.admin import VersionAdmin
from django.db.models import Q
import datetime
from ondoc.crm.admin.doctor import CreatedByFilter
from ondoc.doctor.models import (HospitalImage, HospitalDocument, HospitalAward, Doctor,
                                 HospitalAccreditation, HospitalCertification, HospitalSpeciality, HospitalNetwork,
                                 Hospital, HospitalServiceMapping, HealthInsuranceProviderHospitalMapping)
from .common import *
from ondoc.crm.constants import constants
from django.utils.safestring import mark_safe
from django.contrib.admin import SimpleListFilter
from ondoc.authentication.models import GenericAdmin, User, QCModel, DoctorNumber, AssociatedMerchant
from ondoc.authentication.admin import SPOCDetailsInline
from django import forms
from ondoc.api.v1.utils import GenericAdminEntity
import nested_admin
from .common import AssociatedMerchantInline
from django.contrib import messages
from django.http import HttpResponseRedirect


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


class HospitalServiceInline(admin.TabularInline):
    model = HospitalServiceMapping
    fk_name = 'hospital'
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['service']


class HospitalHealthInsuranceProviderInline(admin.TabularInline):
    model = HealthInsuranceProviderHospitalMapping
    fk_name = 'hospital'
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['provider']


# class HospitalNetworkMappingInline(admin.TabularInline):
#     model = HospitalNetworkMapping
#     extra = 0
#     can_delete = True
#     show_change_link = False
class GenericAdminFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        appnt_manager_flag = self.instance.is_appointment_manager
        validate_unique = []
        if self.cleaned_data:
            phone_number = False
            for data in self.cleaned_data:
                if data.get('phone_number') and data.get('permission_type') in [GenericAdmin.APPOINTMENT, GenericAdmin.ALL]:
                    phone_number = True
                    # break
                if not data.get('DELETE'):
                    if not data.get('super_user_permission'):
                        row = (data.get('phone_number'), data.get('doctor'), data.get('permission_type'))
                        if row in validate_unique:
                            raise forms.ValidationError("Duplicate Permission with this %s exists." % (data.get('phone_number')))
                        else:
                            validate_unique.append(row)
            if phone_number:
                if not appnt_manager_flag:
                    if not(len(self.deleted_forms) == len(self.cleaned_data)):
                        raise forms.ValidationError("Enabled for Managing Appointment should be set if a Admin is Entered.")
            else:
                if appnt_manager_flag:
                    raise forms.ValidationError(
                        "An Admin phone number is required if 'Enabled for Managing Appointment' Field is Set.")
        else:
            if appnt_manager_flag:
                raise forms.ValidationError("An Admin phone number is required if 'Enabled for Managing Appointment' Field is Set.")
            pass
        if len(self.deleted_forms) == len(self.cleaned_data):
            if appnt_manager_flag:
                raise forms.ValidationError(
                    "An Admin phone number is required if 'Enabled for Managing Appointment' Field is Set.")
        # if validate_unique:
        #     numbers = list(zip(*validate_unique))[0]
        #     for row in validate_unique:
        #         if row[1] is None and numbers.count(row[0]) > 2:
        #             raise forms.ValidationError(
        #                 "Permissions for all doctors already allocated for %s." % (row[0]))
        doc_num_list = []
        if self.instance:
            doc_num = DoctorNumber.objects.filter(hospital_id=self.instance.id)
            doc_num_list = [(dn.phone_number, dn.doctor) for dn in doc_num.all()]
            if doc_num.exists():
                validate_unique_del = [(d[0],d[1]) for d in validate_unique]
                for data in self.deleted_forms:
                    del_tuple = (data.cleaned_data.get('phone_number'), data.cleaned_data.get('doctor'))
                    if del_tuple[0] not in dict(validate_unique_del) and (del_tuple in doc_num_list or
                                                                      (del_tuple[1] is None and del_tuple[0] in dict(doc_num_list))):
                        raise forms.ValidationError(
                            "Doctor (%s) Mapping with this number needs to be deleted." % (dict(doc_num_list).get(del_tuple[0])))


class GenericAdminInline(admin.TabularInline):
    model = GenericAdmin
    extra = 0
    can_delete = True
    show_change_link = False
    form = GenericAdminForm
    formset = GenericAdminFormSet
    readonly_fields = ['user', 'updated_at']
    verbose_name_plural = "Admins"
    fields = ['phone_number', 'name', 'doctor', 'permission_type', 'super_user_permission',
              'write_permission', 'user', 'updated_at']

    def get_queryset(self, request):
        return super(GenericAdminInline, self).get_queryset(request).select_related('doctor', 'hospital', 'user')\
            .filter(entity_type=GenericAdminEntity.HOSPITAL)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "doctor":
            hospital_id = request.resolver_match.kwargs.get('object_id')
            kwargs["queryset"] = Doctor.objects.filter(hospitals=hospital_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    # def get_formset(self, request, obj=None, **kwargs):
    #     from django.core.exceptions import MultipleObjectsReturned
    #     formset = super().get_formset(request, obj=obj, **kwargs)
    #     if not request.POST and obj is not None:
    #         formset.form.base_fields['doctor'].queryset = Doctor.objects.filter(
    #                     hospitals=obj).distinct()
    #
    #
    #     return formset


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

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        if self.instance and self.instance.id and self.instance.data_status == QCModel.QC_APPROVED:
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
                        "Cannot have disabled after/disabled reason/disable comments if hospital is enabled or not enabled for online booking.")
            elif not is_enabled or not enabled_for_online_booking:
                if not all([data.get('disabled_after', None), data.get('disable_reason', None)]):
                    raise forms.ValidationError("Must have disabled after/disable reason if hospital is not enabled or not enabled for online booking.")
                if data.get('disable_reason', None) and data.get('disable_reason', None) == Hospital.OTHERS and not data.get(
                        'disable_comments', None):
                    raise forms.ValidationError("Must have disable comments if disable reason is others.")


class HospCityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'city'

    def lookups(self, request, model_admin):
        cities = set([(c['city'].upper(), c['city'].upper()) if (c.get('city')) else ('', '') for c in
                      Hospital.objects.all().values('city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(city__iexact=self.value()).distinct()


class HospitalAdmin(admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):
    list_filter = ('data_status', HospCityFilter, CreatedByFilter)
    readonly_fields = ('source', 'batch', 'associated_doctors', 'is_live', )
    exclude = (
    'search_key', 'live_at', 'qc_approved_at', 'disabled_at', 'physical_agreement_signed_at', 'welcome_calling_done_at')

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
        if not form.cleaned_data.get('enabled', False) and not obj.disabled_by:
            obj.disabled_by = request.user
        elif form.cleaned_data.get('enabled', False) and obj.disabled_by:
            obj.disabled_by = None
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

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)

        for obj in formset.deleted_objects:
            obj.delete()

        for instance in instances:
            if isinstance(instance, GenericAdmin):
                if (not instance.created_by):
                    instance.created_by = request.user
                if (not instance.id):
                    instance.entity_type = GenericAdmin.HOSPITAL
                    instance.source_type = GenericAdmin.CRM
            instance.save()
        formset.save_m2m()

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
            count = instance.assoc_doctors.count()
            #count  = len(set(instance.assoc_doctors.values_list('id', flat=True)))
            #count = DoctorHospital.objects.filter(hospital_id=instance.id).count()
            return count

        else:
            return ''

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.model.objects.filter(id=object_id).first()
        opd_appointment = OpdAppointment.objects.filter(hospital_id=object_id).first()
        content_type = ContentType.objects.get_for_model(obj)
        if opd_appointment:
            messages.set_level(request, messages.ERROR)
            messages.error(request, '{} could not deleted, as {} is present in appointment history'.format(content_type.model, content_type.model))
            return HttpResponseRedirect(reverse('admin:{}_{}_change'.format(content_type.app_label,
                                                                     content_type.model), args=[object_id]))
        if not obj:
            pass
        elif obj.enabled == False:
            pass
        else:
            messages.set_level(request, messages.ERROR)
            messages.error(request, '{} should be disable before delete'.format(content_type.model))
            return HttpResponseRedirect(reverse('admin:{}_{}_change'.format(content_type.app_label,
                                                                            content_type.model), args=[object_id]))
        return super().delete_view(request, object_id, extra_context)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    list_display = ('name', 'updated_at', 'data_status', 'doctor_count', 'list_created_by', 'list_assigned_to')
    form = HospitalForm
    search_fields = ['name']
    inlines = [
        # HospitalNetworkMappingInline,
        HospitalServiceInline,
        HospitalHealthInsuranceProviderInline,
        HospitalSpecialityInline,
        HospitalAwardInline,
        HospitalAccreditationInline,
        HospitalImageInline,
        HospitalDocumentInline,
        HospitalCertificationInline,
        GenericAdminInline,
        SPOCDetailsInline,
        AssociatedMerchantInline
    ]

    map_width = 200
    map_template = 'admin/gis/gmap.html'
    extra_js = ['js/admin/GoogleMap.js','https://maps.googleapis.com/maps/api/js?key=AIzaSyA-5gVhdnhNBInTuxBxMJnGuErjQP40nNc&callback=initGoogleMap']
