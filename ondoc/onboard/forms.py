from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from ondoc.diagnostic.models import Lab
from django import forms


class LabForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.add_input(Submit('submit','Submit',css_class='btn-primary btn-block'))
    class Meta:
        model = Lab
        exclude = ['name']

class OTPForm(forms.Form):

    otp = forms.CharField(required=False)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.add_input(Submit(name='submit',value='Submit',css_class='btn-primary btn-block'))
        self.helper.add_input(Submit(name='_resend_otp', value='Resend OTP', css_class='btn-primary btn-block'))