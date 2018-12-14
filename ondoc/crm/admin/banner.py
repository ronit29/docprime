from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from import_export import fields, resources
from ondoc.banner.models import Banner
from ondoc.diagnostic.models import LabAppointment, Lab, LabTest
from ondoc.doctor.models import OpdAppointment, Doctor, PracticeSpecialization
from django import forms
from import_export.admin import ImportExportMixin, ImportExportActionModelAdmin

from ondoc.procedure.models import Procedure, ProcedureCategory


class BannerAdmin(admin.ModelAdmin):

    model = Banner
    list_display = ['title', 'object_id', 'start_date', 'end_date']


class BannerForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data

        if self.cleaned_data.get('slider_action') == 1:
            if not LabTest.objects.filter(id=self.cleaned_data.get('object_id')):
                raise forms.ValidationError('Test does not exist')

        if self.cleaned_data.get('slider_action') == 2:
            if not Procedure.objects.filter(id=self.cleaned_data.get('object_id')):
                raise forms.ValidationError('Procedure does not exist')

        if self.cleaned_data.get('slider_action') == 3:
            if not PracticeSpecialization.objects.filter(id=self.cleaned_data.get('object_id')):
                raise forms.ValidationError('Specialization does not exist')

        if self.cleaned_data.get('slider_action') == 4:
            if not ProcedureCategory.objects.filter(id=self.cleaned_data.get('object_id')):
                raise forms.ValidationError('Procedure category does not exist')








            TEST = 1
            PROCEDURES = 2
            SPECIALIZATION = 3
            PROCEDURE_CATEGORY = 4
            CONDITION = 5


class BannerAdmin(admin.ModelAdmin):

    model = Banner
    form = BannerForm
    list_display = ['title', 'object_id', 'start_date', 'end_date']
