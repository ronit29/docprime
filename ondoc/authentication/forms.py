from django import forms
from . import models
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet


class BillingAccountFormSet(BaseGenericInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        enabled = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('enabled'):
                enabled += 1

        if count > 0:
            if enabled > 1:
                raise forms.ValidationError("Only one Billing Account can be enabled")


class BillingAccountForm(forms.ModelForm):

    class Meta:
        model = models.BillingAccount
        fields = ('merchant_id', 'type', 'account_number', 'ifsc_code', 'enabled', )

    def __init__(self, *args, **kwargs):
        super(BillingAccountForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['type'].widget = forms.TextInput(attrs={'readonly':True})
            self.fields['account_number'].widget.attrs['readonly'] = True
            # self.fields['account_number'].widget.attrs['disabled'] = True
            self.fields['ifsc_code'].widget.attrs['readonly'] = True
            # self.fields['ifsc_code'].widget.attrs['disabled'] = True