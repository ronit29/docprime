from dal import autocomplete
from django.conf import settings
from django.contrib import messages, admin
from django.contrib.admin import TabularInline
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from import_export import resources, fields, widgets
from import_export.admin import ImportExportMixin

from ondoc.crm import constants
from ondoc.notification import tasks as notification_tasks
from reversion.admin import VersionAdmin

from ondoc.common.models import Feature, Service, AppointmentHistory, VirtualAppointment
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.procedure.models import Procedure, ProcedureCategory, ProcedureCategoryMapping, ProcedureToCategoryMapping, \
    IpdProcedure, IpdProcedureFeatureMapping, IpdProcedureCategoryMapping, IpdProcedureCategory, IpdProcedureDetail, \
    IpdProcedureSynonym, IpdProcedureSynonymMapping, SimilarIpdProcedureMapping, IpdProcedurePracticeSpecialization, \
    IpdProcedureLead, PotentialIpdLeadPracticeSpecialization, IpdProcedureCostEstimate, IpdProcedureLeadCostEstimateMapping, IpdCostEstimateRoomType, \
    IpdCostEstimateRoomTypeMapping
from django import forms


class ParentProcedureCategoryInlineForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        value = self.cleaned_data
        if value.get('child_category') == value.get('parent_category'):
            raise forms.ValidationError("Category can't be related to itself.")
        if value.get('DELETE') and value.get('is_manual', False):
            raise forms.ValidationError("Cannot delete a link not created on CRM.")
        parent_category = value.get('parent_category')
        if parent_category.procedures.count():  # PROCEDURE_category_SAME_level
            raise forms.ValidationError("Category already has few procedures under it. Procedure and Category can't be on same level.")


class ParentProcedureCategoryInline(AutoComplete, TabularInline):
    model = ProcedureCategoryMapping
    exclude = ['is_manual']
    # readonly_fields = ['is_manual']
    fk_name = 'child_category'
    extra = 0
    can_delete = True
    autocomplete_fields = ['parent_category']
    verbose_name = "Parent Category"
    verbose_name_plural = "Parent Categories"
    form = ParentProcedureCategoryInlineForm

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_manual=False)


class ProcedureToParentCategoryInlineFormset(forms.BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        all_parent_categories = []
        count_is_primary = 0
        for value in self.cleaned_data:
            if not value.get("DELETE"):
                all_parent_categories.append(value.get('parent_category'))
                if value.get('is_primary', False):
                    count_is_primary += 1

        if not count_is_primary == 1:
            raise forms.ValidationError("Must have one and only one primary parent category.")
        if all_parent_categories and ProcedureCategoryMapping.objects.filter(parent_category__in=all_parent_categories,
                                                                             child_category__in=all_parent_categories).count():
            raise forms.ValidationError("Some Categories are already related, so can't be added together.")
        if any([category.related_parent_category.count() for category in
                all_parent_categories]):  # PROCEDURE_category_SAME_level
            raise forms.ValidationError("Procedure and Category can't be on same level.")


class IpdProcedureDetailAdminForm(forms.ModelForm):
    value = forms.CharField(widget=forms.Textarea, required=False)

    class Media:
        extend = True
        # js = ('ckedit/js/ckeditor.js', 'ipd_procedure_detail/js/init.js')
        js = ('https://cdn.ckeditor.com/4.11.4/standard-all/ckeditor.js', 'ipd_procedure_detail/js/init.js')
        css = {'all': ('ipd_procedure_detail/css/style.css',)}


class IpdProcedureDetailAdmin(admin.ModelAdmin):
    form = IpdProcedureDetailAdminForm
    autocomplete_fields = ['ipd_procedure', 'detail_type']
    list_display = ['ipd_procedure', 'detail_type']
    # fields = ['ipd_procedure', 'detail_type']

    def get_readonly_fields(self, request, obj=None):
        read_only = super().get_readonly_fields(request, obj=None)
        if obj and obj.id:
            read_only += ('ipd_procedure',)
        return read_only


class IpdProcedureDetailTypeAdmin(admin.ModelAdmin):
    search_fields = ['name']


class DetailInline(AutoComplete, TabularInline):
    model = IpdProcedureDetail
    fk_name = 'ipd_procedure'
    extra = 0
    can_delete = True
    # autocomplete_fields = ['feature']
    verbose_name = "IPD Procedure Detail"
    verbose_name_plural = "IPD Procedure Details"
    fields = ['add_or_change_link', 'detail_type']
    readonly_fields = ['detail_type', 'add_or_change_link']

    def add_or_change_link(self, obj):
        if obj and obj.id:
            url = reverse('admin:procedure_ipdproceduredetail_change', kwargs={"object_id": obj.id})
        else:
            url = reverse('admin:procedure_ipdproceduredetail_add')
        final_url = "<a href='{}' target=_blank>Click Here</a>".format(url)
        return mark_safe(final_url)
    add_or_change_link.short_description = "Link"


class FeatureInline(AutoComplete, TabularInline):
    model = IpdProcedureFeatureMapping
    fk_name = 'ipd_procedure'
    extra = 0
    can_delete = True
    autocomplete_fields = ['feature']
    verbose_name = "IPD Procedure Feature"
    verbose_name_plural = "IPD Procedure Features"

# class IpdProcedureSynonymInline(TabularInline):
#     model = IpdProcedureSynonym
#     extra = 0
#     max_num = 1
#     can_delete = True
#     verbose_name = "IPD Procedure Synonyms"
#     verbose_name_plural = "IPD Procedure Synonyms"



class IpdProcedureSynonymMappingInline(TabularInline):
    model = IpdProcedureSynonymMapping
    extra = 0
    can_delete = True
    verbose_name = "IPD Procedure Synonym"
    verbose_name_plural = "IPD Procedure Synonyms"


class SimilarIpdProcedureMappingInline(TabularInline):
    model = SimilarIpdProcedureMapping
    autocomplete_fields = ['similar_ipd_procedure']
    fk_name = 'ipd_procedure'
    extra = 0
    can_delete = True
    verbose_name = "Similar IPD Procedure"
    verbose_name_plural = "Similar IPD Procedure Synonyms"


class IpdCategoryInline(AutoComplete, TabularInline):
    model = IpdProcedureCategoryMapping
    fk_name = 'ipd_procedure'
    extra = 0
    max_num = 1
    can_delete = True
    autocomplete_fields = ['category']
    verbose_name = "IPD Procedure Category"
    verbose_name_plural = "IPD Procedure Categories"


class IpdProcedurePracticeSpecializationInline(AutoComplete, TabularInline):
    model = IpdProcedurePracticeSpecialization
    extra = 0
    can_delete = True
    autocomplete_fields = ['practice_specialization']
    verbose_name = "Associated Specialization"
    verbose_name_plural = "Associated Specializations"


class IpdProcedureAdminForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea, required=False)
    details = forms.CharField(widget=forms.Textarea, required=False)
    icon = forms.ImageField(required=False)

    class Media:
        extend = False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'ipd_procedure/js/init.js')
        css = {'all': ('ipd_procedure/css/style.css',)}


class IpdProcedureAdmin(VersionAdmin):
    form = IpdProcedureAdminForm
    model = IpdProcedure
    search_fields = ['search_key']
    exclude = ['search_key']
    inlines = [IpdCategoryInline, IpdProcedurePracticeSpecializationInline, FeatureInline, DetailInline,
               IpdProcedureSynonymMappingInline, SimilarIpdProcedureMappingInline]

    def delete_view(self, request, object_id, extra_context=None):
        obj = self.model.objects.filter(id=object_id).first()

        content_type = ContentType.objects.get_for_model(obj)
        if not obj:
            pass
        elif obj.is_enabled == False:
            pass
        else:
            messages.set_level(request, messages.ERROR)
            messages.error(request, '{} should be disabled before delete'.format(content_type.model))
            return HttpResponseRedirect(reverse('admin:{}_{}_change'.format(content_type.app_label,
                                                                            content_type.model), args=[object_id]))
        return super().delete_view(request, object_id, extra_context)

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if request.user.is_member_of(constants.constants['ARTICLE_TEAM']):
            fields = ['about']
        return fields

class FeatureAdmin(VersionAdmin):
    model = Feature
    search_fields = ['name']


class IpdProcedureCategoryAdmin(VersionAdmin):
    model = IpdProcedureCategory
    exclude = ['search_key']
    search_fields = ['name']


class HealthInsuranceProviderAdmin(VersionAdmin):
    model = Feature
    search_fields = ['name']


class ServiceAdmin(VersionAdmin):
    model = Service
    search_fields = ['name']


class ParentCategoryInline(AutoComplete, TabularInline):
    model = ProcedureToCategoryMapping
    fk_name = 'procedure'
    extra = 0
    can_delete = True
    autocomplete_fields = ['parent_category']
    verbose_name = "Parent Category"
    verbose_name_plural = "Parent Categories"
    formset = ProcedureToParentCategoryInlineFormset


class ProcedureAdmin(VersionAdmin):
    model = Procedure
    search_fields = ['search_key']
    exclude = ['search_key']
    inlines = [ParentCategoryInline]


class ProcedureCategoryForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        procedure = cleaned_data.get('preferred_procedure', None)
        is_live = cleaned_data.get('is_live', False)
        if is_live and not procedure:
            raise forms.ValidationError('Category can\'t go live without a preferred procedure.')
        if procedure:
            if self.instance.pk:
                all_organic_parents = procedure.categories.all().values_list('pk', flat=True)
                all_parents = ProcedureCategoryMapping.objects.filter(
                    child_category__in=all_organic_parents).values_list('parent_category', flat=True)
                all_parents = set(all_organic_parents).union(set(all_parents))
                if self.instance.pk not in all_parents:
                        raise forms.ValidationError('Category and preferred procedure should be related.')
                if not procedure.categories.filter(pk=self.instance.pk).exists():  # PROCEDURE_category_SAME_level
                    raise forms.ValidationError(
                        'Category should be direct parent of the preferred procedure.')
            else:
                raise forms.ValidationError('Category and preferred procedure should be related.')


class ProcedureCategoryAdmin(VersionAdmin):
    model = ProcedureCategory
    search_fields = ['search_key']
    inlines = [ParentProcedureCategoryInline]
    exclude = ['search_key']
    form = ProcedureCategoryForm


class IpdProcedureSynonymAdmin(admin.ModelAdmin):
    model = IpdProcedureSynonym
    list_display = ['name']


class IpdProcedureSynonymMappingAdmin(admin.ModelAdmin):
    model = IpdProcedureSynonymMapping
    list_display = ['get_ipd_procedure_name', 'get_ipd_procedure_synonym_name']

    def get_ipd_procedure_synonym_name(self, obj):
        return obj.ipd_procedure_synonym.name
    get_ipd_procedure_synonym_name.admin_order_field = 'ipd_procedure_synonym'  #Allows column order sorting
    get_ipd_procedure_synonym_name.short_description = 'Ipd Procedure Synonym'


    def get_ipd_procedure_name(self, obj):
        return obj.ipd_procedure.name
    get_ipd_procedure_name.admin_order_field  = 'ipd_procedure'  #Allows column order sorting
    get_ipd_procedure_name.short_description = 'Ipd Procedure'


class IpdProcedurePracticeSpecializationResource(resources.ModelResource):
    class Meta:
        model = IpdProcedurePracticeSpecialization
        fields = ('id', 'ipd_procedure', 'practice_specialization')


class IpdProcedurePracticeSpecializationAdmin(ImportExportMixin, VersionAdmin):
    search_fields = ['ipd_procedure__name']
    resource_class = IpdProcedurePracticeSpecializationResource
    list_display = ['ipd_procedure', 'practice_specialization']
    autocomplete_fields = ['ipd_procedure', 'practice_specialization']
    # change_list_template = 'superuser_import_export.html'


class IpdProcedureLeadCostEstimateMappingInline(TabularInline):
    model = IpdProcedureLeadCostEstimateMapping
    extra = 0
    can_delete = True
    verbose_name = "Procedure Cost Estimates"
    verbose_name_plural = "Procedure Cost Estimates"
    autocomplete_fields = ['cost_estimate']


class IpdProcedureLeadAdminForm(forms.ModelForm):
    send_estimate = forms.BooleanField(label='Send estimate', initial=False, required=False)

    # class Meta:
    #     widgets = {
    #         'hospital': autocomplete.ModelSelect2(url='admin:doctor_hospital_autocomplete'),
    #         'doctor': autocomplete.ModelSelect2(url='admin:doctor_doctor_autocomplete'),
    #     }

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        curr_status = cleaned_data.get('status')
        planned_date = cleaned_data.get('planned_date')
        if curr_status and curr_status in [IpdProcedureLead.PLANNED]:
            if not planned_date:
                raise forms.ValidationError("Planned Date is mandatory for {} status.".format(
                    dict(IpdProcedureLead.STATUS_CHOICES)[curr_status]))
        if cleaned_data.get('send_estimate'):
            if not int(self.data.get('lead-TOTAL_FORMS', '0')) > 0:
                raise forms.ValidationError("Procedure Cost Estimate not found.")
            if self.instance.email or self.instance.phone_number:
                notification_tasks.send_ipd_procedure_cost_estimate.apply_async((self.instance.pk,), countdown=60)
            else:
                raise forms.ValidationError("Phone number or Email is required to send estimate.")


class VirtualAppointmentInline(GenericTabularInline):
    can_delete = True
    extra = 0
    # form = SPOCDetailsForm
    model = VirtualAppointment
    show_change_link = False
    readonly_fields = ['id']
    # fields = ['name', 'std_code', 'number', 'email', 'details', 'contact_type']


class IpdProcedureLeadAdmin(VersionAdmin):
    form = IpdProcedureLeadAdminForm
    list_filter = ['created_at', 'source', 'ipd_procedure', 'planned_date', 'source']
    search_fields = ['phone_number', 'matrix_lead_id']
    list_display = ['id', 'phone_number', 'name', 'matrix_lead_id']
    autocomplete_fields = ['doctor', 'hospital', 'insurer', 'tpa', 'ipd_procedure']
    exclude = ['user', 'lat', 'long']
    readonly_fields = ['phone_number', 'id', 'matrix_lead_id', 'comments', 'data', 'source', 'current_age',
                       'related_speciality', 'is_insured', 'insurance_details', 'opd_appointments', 'lab_appointments',
                       'is_automatically_potential']
    inlines = [IpdProcedureLeadCostEstimateMappingInline, VirtualAppointmentInline]

    fieldsets = (
        (None, {
            'fields': (
                'id', 'name', 'gender', 'phone_number', 'is_insured', 'alternate_number', 'dob', 'current_age', 'city', 'email')
        }),
        ('Lead Info', {
            # 'classes': ('collapse',),
            'fields': ('matrix_lead_id', 'is_automatically_potential', 'comments', 'data', 'ipd_procedure', 'related_speciality',
                       'hospital', 'doctor', 'hospital_reference_id', 'source', 'status', 'planned_date', 'requested_date_time',
                       'payment_type', 'payment_amount', 'insurer', 'tpa', 'num_of_chats', 'remarks'),
        }),
        ('History', {
            # 'classes': ('collapse',),
            'fields': ('insurance_details', 'opd_appointments', 'lab_appointments'),
        }),
        ('Communication', {
            'fields': ('send_estimate',),
        }),
    )

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        responsible_user = request.user
        obj._responsible_user = responsible_user if responsible_user and not responsible_user.is_anonymous else None
        if obj and obj.id:
            obj._source = AppointmentHistory.CRM
        super().save_model(request, obj, form, change)

    def related_speciality(self, obj):
        result = []
        if obj and obj.id and obj.ipd_procedure:
            result = IpdProcedurePracticeSpecialization.objects.filter(ipd_procedure=obj.ipd_procedure).values_list(
                'practice_specialization__name', flat=True)
        return ', '.join(result)

    def is_insured(self, obj):
        if obj:
            return obj.is_user_insured()
        return False

    def insurance_details(self, obj):
        result = None
        if obj and obj.user:
            t_obj = obj.user.active_insurance
            if t_obj:
                exit_point_url = settings.ADMIN_BASE_URL + reverse(
                    'admin:{}_{}_change'.format(t_obj.__class__._meta.app_label, t_obj.__class__._meta.model_name),
                    kwargs={"object_id": t_obj.id})
                result = mark_safe('<a href="{}">Active Insurance</a>'.format(exit_point_url))
        return result

    def opd_appointments(self, obj):
        result = []
        if obj and obj.user:
            qs = obj.user.recent_opd_appointment
            for t_obj in qs:
                exit_point_url = reverse(
                    'admin:{}_{}_change'.format(t_obj.__class__._meta.app_label, t_obj.__class__._meta.model_name),
                    kwargs={"object_id": t_obj.id})
                result.append(mark_safe('<a href="{}" target="_blank">{}</a>'.format(exit_point_url, t_obj.id)))
        return mark_safe(', '.join(result))

    def lab_appointments(self, obj):
        result = []
        if obj and obj.user:
            qs = obj.user.recent_lab_appointment
            for t_obj in qs:
                exit_point_url = reverse(
                    'admin:{}_{}_change'.format(t_obj.__class__._meta.app_label, t_obj.__class__._meta.model_name),
                    kwargs={"object_id": t_obj.id})
                result.append(mark_safe('<a href="{}" target="_blank">{}</a>'.format(exit_point_url, t_obj.id)))
        return mark_safe(', '.join(result))

    def current_age(self, obj):
        from django.utils import timezone
        from math import ceil
        result = None
        if obj and obj.dob:
            result = str(ceil(((timezone.now() - obj.dob).days / (365.25))))
        if not result and obj.age:
            result = str(obj.age)
        return result

    def is_automatically_potential(self, obj):
        if obj:
            return obj.is_potential_ipd()
        return False
    is_automatically_potential.short_description = "Has Lead been marked potential by the system?"


class OfferAdminForm(forms.ModelForm):
    tnc = forms.CharField(widget=forms.Textarea, required=False)

    class Media:
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'offer/js/init.js')
        css = {'all': ('offer/css/style.css',)}


class OfferAdmin(VersionAdmin):
    autocomplete_fields = ['coupon', 'ipd_procedure', 'hospital', 'network']
    list_display = ['id', 'title', 'is_live']
    list_filter = ['is_live']
    form = OfferAdminForm


class PotentialIpdLeadPracticeSpecializationResource(resources.ModelResource):
    class Meta:
        model = PotentialIpdLeadPracticeSpecialization
        fields = ('id', 'practice_specialization')


class PotentialIpdLeadPracticeSpecializationAdmin(ImportExportMixin, VersionAdmin):
    search_fields = ['practice_specialization__name']
    resource_class = PotentialIpdLeadPracticeSpecializationResource
    list_display = ['id', 'practice_specialization']
    autocomplete_fields = ['practice_specialization']
    # change_list_template = 'superuser_import_export.html'


class PotentialIpdCityAdmin(VersionAdmin):
    search_fields = ['city__name']
    # resource_class = PotentialIpdLeadPracticeSpecializationResource
    list_display = ['id', 'city']
    autocomplete_fields = ['city']
    # change_list_template = 'superuser_import_export.html'


class IpdCostEstimateRoomTypeAdmin(VersionAdmin):
    model = IpdCostEstimateRoomType
    list_display = ['room_type']
    search_fields = ('room_type',)



class IpdCostEstimateRoomTypeMappingInline(TabularInline):
    model = IpdCostEstimateRoomTypeMapping
    extra = 0
    can_delete = True
    verbose_name = "Room Type Cost"
    verbose_name_plural = "Room Type Costs"
    autocomplete_fields = ['room_type']


class IpdProcedureCostEstimateAdmin(VersionAdmin):
    model = IpdProcedureCostEstimate
    list_display = ['ipd_procedure', 'hospital', 'stay_duration']
    autocomplete_fields = ['ipd_procedure', 'hospital']
    inlines = [IpdCostEstimateRoomTypeMappingInline]
    search_fields = ('hospital__name', 'ipd_procedure__name')


class UploadCostEstimateDataAdmin(admin.ModelAdmin):
    list_display = ('id', 'source', 'batch', 'status', 'file')
    readonly_fields = ('status', 'error_message', 'user', 'lines')

    def save_model(self, request, obj, form, change):
        if obj:
            if not obj.user:
                obj.user = request.user
        super().save_model(request, obj, form, change)

    def error_message(self, instance):
        final_message = ''
        if instance.error_msg:
            for message in instance.error_msg:
                if isinstance(message, dict):
                    final_message += '{}  ::  {}\n\n'.format(message.get('line number', ''), message.get('message', ''))
                else:
                    final_message += str(message)
        return final_message
