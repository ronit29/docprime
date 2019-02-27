from django.contrib.admin import TabularInline
from reversion.admin import VersionAdmin

from ondoc.common.models import Feature, Service
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.procedure.models import Procedure, ProcedureCategory, ProcedureCategoryMapping, ProcedureToCategoryMapping, \
    IpdProcedure, IpdProcedureFeatureMapping
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


class FeatureInline(AutoComplete, TabularInline):
    model = IpdProcedureFeatureMapping
    fk_name = 'ipd_procedure'
    extra = 0
    can_delete = True
    autocomplete_fields = ['feature']
    verbose_name = "IPD Procedure"
    verbose_name_plural = "IPD Procedures"


class IpdProcedureAdmin(VersionAdmin):
    model = IpdProcedure
    search_fields = ['search_key']
    exclude = ['search_key']
    inlines = [FeatureInline]


class FeatureAdmin(VersionAdmin):
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
