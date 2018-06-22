from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Fieldset, Field
from django import forms
from ondoc.diagnostic.models import Lab, AvailableLabTest, LabTest
from ondoc.onboard.forms import CustomField
from dal import autocomplete
from django.urls import reverse


class LabForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.fields['name'].label = 'Lab name'
        self.fields['name'].widget = forms.TextInput(attrs={'readonly': True})
        self.fields['pathology_agreed_price_percent'].label = 'Path Agreed Price'
        self.fields['pathology_deal_price_percent'].label = 'Path Deal Price'
        self.fields['radiology_agreed_price_percent'].label = 'Radio Agreed Price'
        self.fields['radiology_deal_price_percent'].label = 'Radio Deal Price'
        self.helper.form_tag = False
        self.helper.layout = Layout(
                Div(
                    Div(CustomField('name', field_class='col-md-4 test_margin', label_class='col-md-2'), css_class='col-md-9'),
                    css_class='row'),
                Div(
                    Div(CustomField('pathology_agreed_price_percent', field_class='col-md-6 col-sm-6',
                                    label_class='col-sm-5 col-md-5'),css_class='col-sm-4 col-md-4'),
                    Div(CustomField('pathology_deal_price_percent', field_class='col-md-6 col-sm-6',
                                    label_class='col-sm-5 col-md-5'),css_class='col-md-4 col-sm-6'),
                    css_class='row test_margin'),
                Div(
                    Div(CustomField('radiology_agreed_price_percent', field_class='col-md-6 col-sm-6',
                                    label_class='col-sm-5 col-md-5'),css_class='col-md-4 col-sm-4'),
                    Div(CustomField('radiology_deal_price_percent', field_class='col-md-6 col-sm-6',
                                    label_class='col-md-5 col-sm-5'),css_class='col-md-4 col-sm-4'),
                    css_class='row test_margin'),

                Div(
                    Div(CustomField('lab_test', field_class='col-md-6 col-sm-6',
                                    label_class='col-sm-2 col-md-2'), css_class='col-md-9 col-sm-9'),
                    css_class='row'),
                # Submit('submit', u'Submit', css_class='btn btn-success lab_form_submit'),

        )

    lab_test = forms.ModelChoiceField(
        queryset=LabTest.objects.all(),
        required=False,
        widget=autocomplete.ModelSelect2(url='/labtestauto')
    )

    class Meta:
        model = Lab
        fields = ('name', 'pathology_agreed_price_percent', 'pathology_deal_price_percent',
                  'radiology_agreed_price_percent', 'radiology_deal_price_percent', 'lab_test')




