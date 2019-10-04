from dal import autocomplete
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.gis import admin
from django.forms.utils import ErrorList
from reversion.admin import VersionAdmin
from django.db.models import Q
import datetime

from reversion_compare.admin import CompareVersionAdmin

from ondoc.crm.admin.doctor import CreatedByFilter
from ondoc.doctor.models import (HospitalImage, HospitalDocument, HospitalAward, Doctor,
                                 HospitalAccreditation, HospitalCertification, HospitalSpeciality, HospitalNetwork,
                                 Hospital, HospitalServiceMapping, HealthInsuranceProviderHospitalMapping,
                                 HospitalHelpline, HospitalTiming, DoctorClinic, CommonHospital, HospitalNetworkImage,
                                 HospitalSponsoredServices)
from ondoc.integrations.models import IntegratorHospitalCode
from .common import *
from ondoc.crm.constants import constants
from django.utils.safestring import mark_safe
from django.contrib.admin import SimpleListFilter
from ondoc.authentication.models import GenericAdmin, User, QCModel, DoctorNumber, AssociatedMerchant, SPOCDetails, \
    GenericQuestionAnswer
from ondoc.authentication.admin import SPOCDetailsInline
from django import forms, apps
from ondoc.api.v1.utils import GenericAdminEntity
import nested_admin
from .common import AssociatedMerchantInline, RemarkInline
from django.contrib import messages
from django.http import HttpResponseRedirect


import logging
logger = logging.getLogger(__name__)
PartnerHospitalLabMapping = apps.apps.get_model('provider', 'PartnerHospitalLabMapping')


class HospitalImageInline(admin.TabularInline):
    model = HospitalImage
    # template = 'imageinline.html'
    # exclude = ['cropped_image']
    readonly_fields = ['cropped_image']
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 10


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
    verbose_name = "Hospital Facility"
    verbose_name_plural = "Hospital Facilities"


class HospitalSponsoredServicesInline(admin.TabularInline):
    model = HospitalSponsoredServices
    extra = 0
    can_delete = True
    show_change_link = True
    fields = ['sponsored_service', ]


class HospitalTimingInlineFormSet(forms.BaseInlineFormSet):
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


class HospitalTimingInline(admin.TabularInline):
    model = HospitalTiming
    # form = HospitalTimingInlineForm
    formset = HospitalTimingInlineFormSet
    fk_name = 'hospital'
    extra = 0
    can_delete = True
    show_change_link = False
    # autocomplete_fields = ['hospital']
    # inlines = [DoctorClinicTimingInline, DoctorClinicProcedureInline, DoctorClinicIpdProcedureInline, AssociatedMerchantInline]
    # fields = '__all__'


class HospitalHelpineInlineForm(forms.ModelForm):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        std_code = data.get('std_code')
        number = data.get('number')
        if std_code:
            try:
                std_code = int(std_code)
            except:
                raise forms.ValidationError("Invalid STD code")

        if not std_code:
            if number and (number < 5000000000 or number > 9999999999):
                raise forms.ValidationError("Invalid mobile number")

    class Meta:
        fields = '__all__'


class HospitalDoctorInline(admin.TabularInline):
    model = DoctorClinic
    # form = HospitalHelpineInlineForm
    fk_name = 'hospital'
    extra = 0
    can_delete = False
    show_change_link = False
    fields = ['doctor', 'doc_qc_status', 'doc_onboarding_status', 'welcome_calling_done']
    readonly_fields = ['doctor', 'doc_qc_status', 'doc_onboarding_status']

    def doc_qc_status(self, obj):
        data_status_dict = dict(Doctor.DATA_STATUS_CHOICES)
        return data_status_dict[obj.doctor.data_status]

    def doc_onboarding_status(self, obj):
        onboarding_status_dict = dict(Doctor.ONBOARDING_STATUS)
        return onboarding_status_dict[obj.doctor.onboarding_status]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('doctor')

    def get_readonly_fields(self, request, obj=None):
        read_only_field = super().get_readonly_fields(request, obj)
        if not request.user.is_superuser and not request.user.groups.filter(
            name=constants['WELCOME_CALLING_TEAM']).exists():
            read_only_field.append('welcome_calling_done')
        return read_only_field


class HospitalHelplineInline(admin.TabularInline):
    model = HospitalHelpline
    form = HospitalHelpineInlineForm
    fk_name = 'hospital'
    extra = 0
    can_delete = True
    show_change_link = False


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
              'write_permission', 'is_partner_lab_admin', 'user', 'updated_at']

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

    class Meta:
        widgets = {
            'matrix_state': autocomplete.ModelSelect2(url='matrix-state-autocomplete'),
            'matrix_city': autocomplete.ModelSelect2(url='matrix-city-autocomplete', forward=['matrix_state'])
        }

    class Media:
        extend = True
        js = ('https://cdn.ckeditor.com/4.11.4/standard-all/ckeditor.js', 'doctor/js/init.js')
        css = {'all': ('doctor/css/style.css',)}

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
                       'registration_number': 'req', 'building': 'req', 'locality': 'req',
                       'country': 'req', 'pin_code': 'req', 'hospital_type': 'req', 'network_type': 'req',
                       'matrix_city': 'req', 'matrix_state': 'req',
                       'authentication-spocdetails-content_type-object_id': 'count', 'matrix_lead_id': 'value_req'}

        # if (not self.instance.network or not self.instance.network.is_billing_enabled) and self.instance.is_billing_enabled:
        #     qc_required.update({
        #         'hospital_documents': 'count'
        #     })

        if self.instance.network and self.instance.network.data_status != QCModel.QC_APPROVED:
            raise forms.ValidationError("Hospital Network is not QC approved.")

        for key, value in qc_required.items():
            if value == 'req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key + " is required for Quality Check")
            if self.data.get(key + '_set-TOTAL_FORMS') and value == 'count' and int(
                    self.data[key + '_set-TOTAL_FORMS']) <= 0:
                raise forms.ValidationError("Atleast one entry of " + key + " is required for Quality Check")
            if self.data.get(key + '-TOTAL_FORMS') and value == 'count' and int(
                    self.data.get(key + '-TOTAL_FORMS')) <= 0:
                raise forms.ValidationError("Atleast one entry of " + key + " is required for Quality Check")
            if value == 'value_req':
                if hasattr(self.instance, key) and not getattr(self.instance, key):
                    raise forms.ValidationError(key + " is required for Quality Check")
        if self.cleaned_data['network_type'] == 2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Hospital")

        number_of_spocs = self.data.get('authentication-spocdetails-content_type-object_id-TOTAL_FORMS', '0')
        try:
            number_of_spocs = int(number_of_spocs)
        except Exception as e:
            logger.error("Something went wrong while counting SPOCs for hospital - " + str(e))
            raise forms.ValidationError("Something went wrong while counting SPOCs.")
        if number_of_spocs > 0:
            if not any([self.data.get('authentication-spocdetails-content_type-object_id-{}-contact_type'.format(i),
                                      0) == str(SPOCDetails.SPOC) and self.data.get(
                'authentication-spocdetails-content_type-object_id-{}-number'.format(i)) for i in
                        range(number_of_spocs)]):
                raise forms.ValidationError("Must have Single Point Of Contact number.")

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        data = self.cleaned_data
        if self.data.get('search_distance') and float(self.data.get('search_distance')) > float(50000):
            raise forms.ValidationError("Search Distance should be less than 50 KM.")
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

            if self.cleaned_data.get('is_enabled') == False and (not self.request.user.is_superuser == True):
                raise forms.ValidationError('User is not Super User')
        # if '_mark_in_progress' in self.data and data.get('enabled'):
        #     raise forms.ValidationError("Must be disabled before rejecting.")

        if data.get('enabled_for_online_booking'):
            if self.instance and self.instance.data_status == QCModel.QC_APPROVED:
                pass
            elif self.instance and self.instance.data_status != QCModel.QC_APPROVED and '_qc_approve' in self.data:
                pass
            else:
                raise forms.ValidationError("Must be QC Approved for enable online booking")

        if '_mark_in_progress' in self.request.POST:
            if data.get('enabled_for_online_booking'):
                raise forms.ValidationError("Enable for online booking should be disabled for QC Reject/Reopen")
            else:
                pass

        if data.get('is_live'):
            if self.instance and self.instance.source == 'pr':
                pass
            else:
                history_obj = self.instance.history.filter(status=QCModel.QC_APPROVED).first()
                if self.instance and self.instance.enabled and history_obj:
                    pass
                elif self.instance and not self.instance.enabled and data.get('enabled') and history_obj:
                    pass
                else:
                    raise forms.ValidationError("Should be enabled and QC Approved once for is_live")


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


class QuestionAnswerInline(GenericTabularInline):
    model = GenericQuestionAnswer
    extra = 0
    can_delete = True
    verbose_name = "FAQ"
    verbose_name_plural = "FAQs"
    fields = ['add_or_change_link', 'preview']
    readonly_fields = ['add_or_change_link', 'preview']

    def add_or_change_link(self, obj):
        if obj and obj.id:
            url = reverse('admin:authentication_genericquestionanswer_change', kwargs={"object_id": obj.id})
        else:
            url = reverse('admin:authentication_genericquestionanswer_add')
        final_url = "<a href='{}' target=_blank>Click Here</a>".format(url)
        return mark_safe(final_url)
    add_or_change_link.short_description = "Link"

    def preview(self, obj):
        result = None
        if obj and obj.id:
            result = "{}".format(obj.question)
        return result


class CloudLabAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Lab.objects.none()
        queryset = Lab.objects.filter(is_b2b=True)
        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)
        return queryset.distinct()


class PartnerLabsInlineForm(forms.ModelForm):

    class Meta:
        model = PartnerHospitalLabMapping
        fields = ('lab',)
        widgets = {
            'lab': autocomplete.ModelSelect2(url='cloud-lab-autocomplete', forward=[]),
        }


class PartnerLabsInline(admin.TabularInline):
    model = PartnerHospitalLabMapping
    extra = 0
    can_delete = True
    verbose_name = "Provider Lab"
    verbose_name_plural = "Provider Labs"
    readonly_fields = []
    fields = ['lab']
    autocomplete_fields = []
    form = PartnerLabsInlineForm

    def get_queryset(self, request):
        return super(PartnerLabsInline, self).get_queryset(request).select_related('hospital', 'lab').filter(lab__is_b2b=True)


class HospitalCodeInline(admin.TabularInline):
    model = IntegratorHospitalCode
    extra = 0
    can_delete = True
    show_change_link = False


class HospitalAdmin(admin.GeoModelAdmin, CompareVersionAdmin, ActionAdmin, QCPemAdmin):
    list_filter = ('data_status', 'welcome_calling_done', 'enabled_for_online_booking', 'enabled', CreatedByFilter,
                   HospCityFilter)
    readonly_fields = ('source', 'batch', 'associated_doctors', 'is_live', 'matrix_lead_id', 'city', 'state', 'live_seo_url', 'edit_url')
    exclude = ('search_key', 'live_at', 'qc_approved_at', 'disabled_at', 'physical_agreement_signed_at',
               'welcome_calling_done_at', 'provider_encrypt', 'provider_encrypted_by', 'encryption_hint', 'encrypted_hospital_id', 'is_big_hospital')
    list_display = ('name', 'locality', 'city', 'is_live', 'updated_at', 'data_status', 'welcome_calling_done', 'doctor_count',
                    'list_created_by', 'list_assigned_to')
    form = HospitalForm
    search_fields = ['name']
    # autocomplete_fields = ['matrix_city', 'matrix_state']
    inlines = [
        # HospitalNetworkMappingInline,
        HospitalDoctorInline,
        HospitalHelplineInline,
        HospitalServiceInline,
        HospitalTimingInline,
        HospitalHealthInsuranceProviderInline,
        HospitalSpecialityInline,
        HospitalAwardInline,
        HospitalAccreditationInline,
        HospitalImageInline,
        HospitalDocumentInline,
        HospitalCertificationInline,
        QuestionAnswerInline,
        GenericAdminInline,
        SPOCDetailsInline,
        AssociatedMerchantInline,
        RemarkInline,
        HospitalSponsoredServicesInline,
        PartnerLabsInline,
        HospitalCodeInline,
    ]
    map_width = 200
    map_template = 'admin/gis/gmap.html'
    extra_js = ['js/admin/GoogleMap.js',
                'https://maps.googleapis.com/maps/api/js?key=AIzaSyDFxu_VGlmLojtgiwn892OYzV6IY_Inl6I&callback=initGoogleMap']

    # def get_inline_instances(self, request, obj=None):
    #     res = super().get_inline_instances(request, obj)
    #     if obj and obj.id and obj.data_status == obj.QC_APPROVED:
    #         res = [x for x in res if not isinstance(x, RemarkInline)]
    #     return res

    def get_fields(self, request, obj=None):
        all_fields = super().get_fields(request, obj)
        if not request.user.is_superuser and not request.user.groups.filter(name=constants['WELCOME_CALLING_TEAM']).exists():
            if 'welcome_calling_done' in all_fields:
                all_fields.remove('welcome_calling_done')
        if 'network' in all_fields:
            if 'add_network_link' in all_fields:
                all_fields.remove('add_network_link')
            network_index = all_fields.index('network')
            all_fields.insert(network_index + 1, 'add_network_link')
        # reorder welcome_calling_after any other field
        # if 'additional_details' in all_fields and 'welcome_calling_done' in all_fields:
        #     all_fields.remove('welcome_calling_done')
        #     additional_details_index = all_fields.index('additional_details')
        #     all_fields.insert(additional_details_index + 1, 'welcome_calling_done')
        return all_fields

    def associated_doctors(self, instance):
        if instance.id:
            html = "<ul style='margin-left:0px !important'>"
            for doc in Doctor.objects.filter(hospitals=instance.id).distinct():
                html += "<li><a target='_blank' href='/admin/doctor/doctor/%s/change'>%s</a></li>"% (doc.id, doc.name)
            html += "</ul>"
            return mark_safe(html)
        else:
            return ''

    def live_seo_url(self, instance):
        if instance.id:
            from ondoc.location.models import EntityUrls
            entity_obj = EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE,
                                                   is_valid=True, entity_id=instance.id).first()
            hospital_url = None
            if entity_obj:
                hospital_url = "{}/{}".format(settings.BASE_URL, entity_obj.url)
            if hospital_url:
                html = "<ul style='margin-left:0px !important'>"
                html += "<li><a target='_blank' href='{}'>Link</a></li>".format(hospital_url)
                html += "</ul>"
                return mark_safe(html)

        return ''

    def edit_url(self, instance):
        if instance.id:
            from ondoc.location.models import EntityUrls
            entity_obj = EntityUrls.objects.filter(sitemap_identifier=EntityUrls.SitemapIdentifier.HOSPITAL_PAGE,
                                                   is_valid=True, entity_id=instance.id).first()
            hospital_url = None
            if entity_obj:
                hospital_url = reverse('admin:location_entityurls_change', kwargs={"object_id": entity_obj.id})
            if hospital_url:
                html = "<ul style='margin-left:0px !important'>"
                html += "<li><a target='_blank' href='{}'>Link</a></li>".format(hospital_url)
                html += "</ul>"
                return mark_safe(html)
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
            obj.data_status = QCModel.SUBMITTED_FOR_QC
        if '_qc_approve' in request.POST:
            obj.data_status = QCModel.QC_APPROVED
            #obj.is_live = True
            #obj.live_at = datetime.datetime.now()
            obj.qc_approved_at = datetime.datetime.now()
        if '_mark_in_progress' in request.POST:
            obj.data_status = QCModel.REOPENED
        if not obj.source_type:
            obj.source_type = Hospital.AGENT

        obj.status_changed_by = request.user
        obj.city = obj.matrix_city.name
        obj.state = obj.matrix_state.name

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
            if isinstance(instance, Remark):
                if (not instance.user):
                    instance.user = request.user
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
        network_field = form.base_fields.get('network')
        if network_field:
            network_field.queryset = HospitalNetwork.objects.filter(Q(data_status=QCModel.SUBMITTED_FOR_QC) | Q(data_status=QCModel.QC_APPROVED) | Q(created_by=request.user))
            network_field.widget.can_add_related = False
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

    def get_readonly_fields(self, *args, **kwargs):
        read_only = super().get_readonly_fields(*args, **kwargs)
        if args:
            request = args[0]
            if request.GET.get('AgentId', None):
                self.matrix_agent_id = request.GET.get('AgentId', None)
            read_only += ('add_network_link',)
        if not request.user.is_superuser and not request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists():
            read_only += ('is_listed_on_docprime',)
        if not request.user.groups.filter(
                name__in=[constants['WELCOME_CALLING_TEAM'],
                          constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']]) and not request.user.is_superuser:
            read_only += ('is_location_verified',)

        return read_only

    def add_network_link(self, obj):
        content_type = ContentType.objects.get_for_model(HospitalNetwork)
        add_network_link = reverse('admin:%s_%s_add' % (content_type.app_label, content_type.model))
        if hasattr(self, 'matrix_agent_id') and self.matrix_agent_id:
            add_network_link += '?AgentId={}'.format(self.matrix_agent_id)
        html = '''<a href='%s' target=_blank>%s</a><br>''' % (add_network_link, "Add Network")
        return mark_safe(html)


class CommonHospitalForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        network = self.cleaned_data.get('network')
        hospital = self.cleaned_data.get('hospital')
        if all([network, hospital]) or not any([network, hospital]):
            raise forms.ValidationError('One and only of network and hospital.')
        # if hospital and not hospital.is_live:
        #     raise forms.ValidationError('Hospital must be live.')
        # if network and not network.assoc_hospitals.filter(is_live=True).exists():
        #     raise forms.ValidationError('Network must have live hospital(s).')


class CommonHospitalAdmin(admin.ModelAdmin):
    autocomplete_fields = ['hospital', 'network']
    form = CommonHospitalForm
    list_display = ['id', 'hospital', 'network']

    class Meta:
        model = CommonHospital
        fields = '__all__'


class GenericQuestionAnswerForm(forms.ModelForm):

    class Media:
        extend = True
        js = ('https://cdn.ckeditor.com/4.11.4/standard-all/ckeditor.js', 'q_a/js/init.js')
        css = {'all': ('q_a/css/style.css',)}


class GenericQuestionAnswerAdmin(admin.ModelAdmin):
    form = GenericQuestionAnswerForm
