from crispy_forms.helper import FormHelper
from ondoc.diagnostic.models import Lab
from django import forms


class LabForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = Lab
        exclude = ['name']
