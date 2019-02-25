from django.contrib import admin
from ondoc.banner.models import Banner, SliderLocation
from django import forms


class BannerForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data

        # if cleaned_data.get('slider_action') == 1:
        #     if not LabTest.objects.filter(id=cleaned_data.get('object_id')):
        #         raise forms.ValidationError('Test does not exist')
        #
        # if cleaned_data.get('slider_action') == 2:
        #     if not Procedure.objects.filter(id=cleaned_data.get('object_id')):
        #         raise forms.ValidationError('Procedure does not exist')
        #
        # if cleaned_data.get('slider_action') == 3:
        #     if not PracticeSpecialization.objects.filter(id=cleaned_data.get('object_id')):
        #         raise forms.ValidationError('Specialization does not exist')
        #
        # if cleaned_data.get('slider_action') == 4:
        #     if not ProcedureCategory.objects.filter(id=cleaned_data.get('object_id')):
        #         raise forms.ValidationError('Procedure category does not exist')
        #
        # if cleaned_data.get('slider_action') == 5:
        #     if not MedicalCondition.objects.filter(id=cleaned_data.get('object_id')):
        #         raise forms.ValidationError('Condition does not exist')

        if cleaned_data.get('start_date'):
            if not cleaned_data.get('start_date') < cleaned_data.get('end_date'):
                raise forms.ValidationError('End date is invalid')

        if cleaned_data.get('latitude'):
            if not cleaned_data.get('longitude'):
                raise forms.ValidationError('Longitude is required')
            if not cleaned_data.get('radius'):
                raise forms.ValidationError('Radius is required')
        elif cleaned_data.get('longitude'):
            if not cleaned_data.get('latitude'):
                raise forms.ValidationError('Latitude is required')
            if not cleaned_data.get('radius'):
                raise forms.ValidationError('Radius is required')
        elif cleaned_data.get('radius'):
            if not cleaned_data.get('latitude'):
                raise forms.ValidationError('Latitude is required')
            if not cleaned_data.get('longitude'):
                raise forms.ValidationError('Longitude is required')
        # if cleaned_data.slider_locate:
        #     cleaned_data.exclude('slider_locate',)



class BannerAdmin(admin.ModelAdmin):

    model = Banner
    form = BannerForm
    list_display = ['title', 'priority', 'location', 'start_date', 'end_date']
    readonly_fields = ['event_name', 'slider_locate']
    # exclude = ['slider_locate']

class SliderLocationAdmin(admin.ModelAdmin):

    model = SliderLocation
    list_display = ['name']