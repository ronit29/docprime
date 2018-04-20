from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Fieldset
from ondoc.diagnostic.models import Lab, LabCertification, LabAward, LabAccreditation, LabManager, LabTiming
from django import forms
from django.forms import inlineformset_factory

# include all forms here

class LabAwardForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = LabAward
        exclude = ['lab',]

class LabTimingForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
 
    class Meta:
        model = LabTiming
        exclude = ['lab',]


class LabManagerForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
 
    class Meta:
        model = LabManager
        exclude = ['lab',]


class LabCertificationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = LabCertification
        exclude = ['lab',]

class LabAccreditationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = LabAccreditation
        exclude = ['lab',]


class LabForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        # self.helper.add_input(Submit('submit','Submit',css_class='btn-primary btn-block'))
        self.helper.layout = Layout(
            'name',
            'about',
            Div(
                Div('license',css_class='col-md-6',),
                Div('operational_since',css_class='col-md-6',),
                css_class='row',
            ),
            Div(
                Div('parking',css_class='col-md-6',),
                Div('hospital',css_class='col-md-6',),
                css_class='row',
            ),
            Div(
                Div('network_type',css_class='col-md-6',),
                Div('network',css_class='col-md-6',),
                css_class='row',
            ),
        )


    class Meta:
        model = Lab
        exclude = []

class LabAddressForm(LabForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.layout = Layout(
            Div(
                Div('building',css_class='col-md-offset-1 col-md-4',),
                Div('sublocality',css_class='col-sm-offset-3 col-md-4',),
                css_class='row',
            ),
            Div(
                Div('locality',css_class='col-md-6',),
                Div('city',css_class='col-md-6',),
                css_class='row',
            ),
            Div(
                Div('state',css_class='col-md-6',),
                Div('country',css_class='col-md-6',),
                css_class='row',
            ),
            'pin_code',
        )


class OTPForm(forms.Form):

    otp = forms.CharField(required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.add_input(Submit(name='submit',value='Submit',css_class='btn-primary btn-block'))
        self.helper.add_input(Submit(name='_resend_otp', value='Resend OTP', css_class='btn-primary btn-block'))



# include all formsets here

LabAwardFormSet = inlineformset_factory(Lab, LabAward,extra = 1, can_delete=True, exclude=('lab', ))
LabCertificationFormSet = inlineformset_factory(Lab, LabCertification,extra = 1, can_delete=True, exclude=('lab', ))
LabAccreditationFormSet = inlineformset_factory(Lab, LabAccreditation,extra = 1, can_delete=True, exclude=('lab', ))
LabManagerFormSet = inlineformset_factory(Lab, LabManager,extra = 1, can_delete=True, exclude=('lab', ))
LabTimingFormSet = inlineformset_factory(Lab, LabTiming, form = LabTimingForm,extra = 1, can_delete=True)

