from django.contrib.admin import TabularInline
from reversion.admin import VersionAdmin
from ondoc.crm.admin.doctor import AutoComplete
from ondoc.procedure.models import Procedure, ProcedureCategory, ProcedureCategoryMapping
from django.contrib.gis import forms


# class ParentProcedureCategoryForm(forms.ModelForm):
#     def clean(self):
#         super().clean()
#         # LOGIC


class ParentProcedureCategoryInline(AutoComplete, TabularInline):
    model = ProcedureCategoryMapping
    # exclude = ['is_manual']
    fk_name = 'child_category'
    extra = 0
    can_delete = True
    autocomplete_fields = ['parent_category']
    verbose_name = "Parent Category"
    verbose_name_plural = "Parent Categories"
    # form = ParentProcedureCategoryForm


class ProcedureAdmin(VersionAdmin):
    model = Procedure
    search_fields = ['name']


class ProcedureCategoryAdmin(VersionAdmin):
    model = ProcedureCategory
    search_fields = ['name']
    inlines = [ParentProcedureCategoryInline]
