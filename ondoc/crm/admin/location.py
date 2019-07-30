from django.contrib.admin import TabularInline

from ondoc.crm.admin.doctor import ReadOnlyInline, forms
from ondoc.location.models import CompareLabPackagesSeoUrls, EntityUrls
from django.contrib import admin


class ComparePackagesSEOUrlsFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        lab_package = set()
        count = 0
        for value in self.cleaned_data:
            if value.get('lab') and value.get('package'):
                lab_package.add((value.get('lab'), value.get('package')))
                count += 1
        if count < 2:
            raise forms.ValidationError("Atleast two labs and packages are required")
        if count > 5:
                raise forms.ValidationError("More than five labs and packages cannot be selected")


class ComparePackagesSEOUrlsForm(forms.ModelForm):

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        entity = EntityUrls.objects.filter(url=self.cleaned_data.get('url'), is_valid=True)
        if entity:
            raise forms.ValidationError("URL already exists")


class CompareLabPackagesSeoUrlsInLine(TabularInline):
    model = CompareLabPackagesSeoUrls
    autocomplete_fields = ['lab', 'package']
    formset = ComparePackagesSEOUrlsFormSet
    extra = 0
    can_delete = True
    show_change_link = False
    fields = ['lab', 'package']


class ComparePackagesSEOUrlsAdmin(admin.ModelAdmin):
    form = ComparePackagesSEOUrlsForm
    inlines = [CompareLabPackagesSeoUrlsInLine]
    search_fields = ['url']
    list_display = ('url', 'title')
