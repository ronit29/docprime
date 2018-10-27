from django.contrib.admin import TabularInline
from reversion.admin import VersionAdmin
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.procedure.models import Procedure, ProcedureCategory, ProcedureCategoryMapping, ProcedureToCategoryMapping
from django import forms


class ParentProcedureCategoryInlineFormset(forms.BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        for value in self.cleaned_data:
                if value.get('child_category') == value.get('parent_category'):
                    raise forms.ValidationError("Category can't be related to itself.")


class ParentProcedureCategoryInline(AutoComplete, TabularInline):
    model = ProcedureCategoryMapping
    exclude = ['is_manual']
    fk_name = 'child_category'
    extra = 0
    can_delete = True
    autocomplete_fields = ['parent_category']
    verbose_name = "Parent Category"
    verbose_name_plural = "Parent Categories"
    formset = ParentProcedureCategoryInlineFormset

    def get_queryset(self, request):
        return super().get_queryset(request).filter(is_manual=False)


class ProcedureToParentCategoryInlineFormset(forms.BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        all_parent_categories = []
        for value in self.cleaned_data:
            if not value.get("DELETE"):
                all_parent_categories.append(value.get('parent_category'))
        if all_parent_categories and ProcedureCategoryMapping.objects.filter(parent_category__in=all_parent_categories,
                                                                             child_category__in=all_parent_categories).count():
            raise forms.ValidationError("Some Categories are already related, so can't be added together.")
        if any([category.related_parent_category.count() for category in all_parent_categories]):
            raise forms.ValidationError("Procedure and Category can't be on same level.")


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


class ProcedureCategoryAdmin(VersionAdmin):
    model = ProcedureCategory
    search_fields = ['search_key']
    inlines = [ParentProcedureCategoryInline]
    exclude = ['search_key']
