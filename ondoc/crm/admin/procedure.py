from django.conf import settings
from django.contrib import messages, admin
from django.contrib.admin import TabularInline
from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.safestring import mark_safe
from reversion.admin import VersionAdmin

from ondoc.common.models import Feature, Service
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.procedure.models import Procedure, ProcedureCategory, ProcedureCategoryMapping, ProcedureToCategoryMapping, \
    IpdProcedure, IpdProcedureFeatureMapping, IpdProcedureCategoryMapping, IpdProcedureCategory, IpdProcedureDetail
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


class IpdCategoryInline(AutoComplete, TabularInline):
    model = IpdProcedureCategoryMapping
    fk_name = 'ipd_procedure'
    extra = 0
    max_num = 1
    can_delete = True
    autocomplete_fields = ['category']
    verbose_name = "IPD Procedure Category"
    verbose_name_plural = "IPD Procedure Categories"


class IpdProcedureAdminForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea, required=False)
    details = forms.CharField(widget=forms.Textarea, required=False)

    class Media:
        extend = False
        js = ('https://cdn.ckeditor.com/ckeditor5/10.1.0/classic/ckeditor.js', 'ipd_procedure/js/init.js')
        css = {'all': ('ipd_procedure/css/style.css',)}


class IpdProcedureAdmin(VersionAdmin):
    form = IpdProcedureAdminForm
    model = IpdProcedure
    search_fields = ['search_key']
    exclude = ['search_key']
    inlines = [IpdCategoryInline, FeatureInline, DetailInline]

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
