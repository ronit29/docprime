from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Fieldset, Field, ButtonHolder
from django import forms
from ondoc.diagnostic.models import Lab, AvailableLabTest, LabTest
from ondoc.onboard.forms import CustomField
from dal import autocomplete
from django.urls import reverse


# class LabForm(forms.ModelForm):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.helper = FormHelper()
#         self.fields['name'].label = 'Lab name'
#         self.fields['name'].widget = forms.TextInput(attrs={'readonly': True})
#         self.fields['pathology_agreed_price_percentage'].label = 'Path Agreed Price Percentage'
#         self.fields['pathology_deal_price_percentage'].label = 'Path Deal Price Percentage'
#         self.fields['radiology_agreed_price_percentage'].label = 'Radio Agreed Price Percentage'
#         self.fields['radiology_deal_price_percentage'].label = 'Radio Deal Price Percentage'
#         self.helper.form_tag = False
#         self.helper.layout = Layout(
#                 Div(
#                     Div(CustomField('pathology_agreed_price_percentage', field_class='col-md-2 col-sm-2',
#                                     label_class='col-sm-6 col-md-6'),css_class='col-sm-6 col-md-6'),
#                     Div(CustomField('pathology_deal_price_percentage', field_class='col-md-2 col-sm-2',
#                                     label_class='col-sm-6 col-md-6'),css_class='col-md-6 col-sm-6'),
#                     css_class='row test_margin'),
#                 Div(
#                     Div(CustomField('radiology_agreed_price_percentage', field_class='col-md-2 col-sm-2',
#                                     label_class='col-sm-6 col-md-6'),css_class='col-md-6 col-sm-6'),
#                     Div(CustomField('radiology_deal_price_percentage', field_class='col-md-2 col-sm-2',
#                                     label_class='col-md-6 col-sm-6'),css_class='col-md-6 col-sm-6'),
#                     css_class='row test_margin'),

#                 Div(
#                     Div(CustomField('lab_test', field_class='col-md-6 col-sm-6',
#                                     label_class='col-sm-2 col-md-2'), css_class='col-md-9 col-sm-9'),
#                     css_class='row'),
#                 # Submit('submit', u'Submit', css_class='btn btn-success lab_form_submit'),

#         )

#     lab_test = forms.ModelChoiceField(
#         queryset=LabTest.objects.all(),
#         required=False,
#         widget=autocomplete.ModelSelect2(url='/labtestauto')
#     )

#     class Meta:
#         model = Lab
#         fields = ('name', 'pathology_agreed_price_percentage', 'pathology_deal_price_percentage',
#                   'radiology_agreed_price_percentage', 'radiology_deal_price_percentage', 'lab_test')



class LabForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['pathology_agreed_price_percentage'].label = 'Path Agreed Price Percentage'
        self.fields['pathology_deal_price_percentage'].label = 'Path Deal Price Percentage'
        self.fields['radiology_agreed_price_percentage'].label = 'Radio Agreed Price Percentage'
        self.fields['radiology_deal_price_percentage'].label = 'Radio Deal Price Percentage'
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Div(CustomField('pathology_agreed_price_percentage'),css_class="col-md-3"),
            Div(CustomField('pathology_deal_price_percentage'),css_class="col-md-3"),
            Div(CustomField('radiology_agreed_price_percentage'),css_class="col-md-3"),
            Div(CustomField('radiology_deal_price_percentage'),css_class="col-md-3")
            )

    lab_test = forms.ModelChoiceField(
        queryset=LabTest.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(url='/labtestauto')
    )

    class Meta:
        model = Lab
        fields = ('pathology_agreed_price_percentage', 'pathology_deal_price_percentage',
                  'radiology_agreed_price_percentage', 'radiology_deal_price_percentage')


class LabMapForm(forms.ModelForm):

    class Meta:
        model = Lab
        fields = ("is_insurance_enabled", "is_retail_enabled",
                  "is_ppc_pathology_enabled", "is_ppc_radiology_enabled",
                   )
