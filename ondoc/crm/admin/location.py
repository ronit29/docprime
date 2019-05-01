from django.contrib.admin import TabularInline

from ondoc.crm.admin.doctor import ReadOnlyInline, forms
from ondoc.location.models import CompareLabPackagesSeoUrls, EntityUrls
from django.contrib import admin


class ComparePackagesSEOUrlsForm(forms.ModelForm):

    def clean(self):
        if self.cleaned_data and self.cleaned_data.get('url'):
            entity = EntityUrls.objects.filter(url=self.cleaned_data.get('url'), is_valid=True)
            if entity:
                if self.cleaned_data.get('url') == entity.first().url:
                    raise forms.ValidationError("URL already exists")


class CompareLabPackagesSeoUrlsInLine(TabularInline):
    model = CompareLabPackagesSeoUrls
    autocomplete_fields = ['lab', 'package']
    extra = 0
    forms = ComparePackagesSEOUrlsForm
    can_delete = True
    show_change_link = False
    fields = ['lab', 'package']


class ComparePackagesSEOUrlsAdmin(admin.ModelAdmin):
    form = ComparePackagesSEOUrlsForm
    inlines = [CompareLabPackagesSeoUrlsInLine]
    search_fields = ['url']
