from django.contrib import admin
from django.contrib.admin import TabularInline

from ondoc.banner.models import Banner, SliderLocation, BannerLocation, Recommender, EmailBanner, RecommenderThrough
from django import forms
from django.contrib.contenttypes.admin import GenericTabularInline


class BannerForm(forms.ModelForm):
    body = forms.CharField(widget=forms.Textarea, required=False)

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
        resp = []
        if cleaned_data.get('url_params_included'):
            if cleaned_data.get('url_params_excluded'):
                for key1, value1 in cleaned_data.get('url_params_included').items():
                    for key2, value2 in cleaned_data.get('url_params_excluded').items():
                        if key1 == key2 and value1 == value2:
                            resp.append(str(key1) + ':' + str(value1))
                raise forms.ValidationError('Cannot input duplicate values in field url_params -> {}'.format(resp))

    class Media:
        extend = False
        # js = ('ckedit/js/ckeditor.js', 'articles/js/init.js')   # ckeditor-5 replaced with ckeditor-4.11.4
        js = ('https://cdn.ckeditor.com/4.11.4/standard-all/ckeditor.js', 'articles/js/init.js')
        css = {'all': ('articles/css/style.css',)}


class BannerLocationInline(admin.TabularInline):

    model = BannerLocation
    extra = 0
    can_delete = True
    show_change_link = False


class BannerAdmin(admin.ModelAdmin):

    model = Banner
    form = BannerForm
    inlines = [BannerLocationInline]
    list_display = ['title', 'priority', 'location', 'start_date', 'end_date', 'enable']
    readonly_fields = ['event_name']
    list_filter = ['enable']
    exclude = ['slider_locate']

class SliderLocationAdmin(admin.ModelAdmin):

    model = SliderLocation
    list_display = ['name']


class RecommenderAdmin(admin.ModelAdmin):

    model = Recommender

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        return form


class RecommenderInline(GenericTabularInline):
    can_delete = True
    extra = 0
    # form = SPOCDetailsForm
    model = RecommenderThrough
    show_change_link = False
    fields = ['recommender']

class EmailBannerAdmin(admin.ModelAdmin):

    model = EmailBanner
    inlines = (RecommenderInline, )


