from django import forms
from . import models
from django.contrib.contenttypes.forms import BaseGenericInlineFormSet


# class BillingAccountFormSet(BaseGenericInlineFormSet):
#     def clean(self):
#         super().clean()
#         if any(self.errors):
#             return


#         enabled = 0
#         count = 0
#         for value in self.cleaned_data:
#             count += 1
#             if value.get('enabled'):
#                 enabled += 1
#             if value.get('account_number'):
#                 try:
#                     int(value.get('account_number'))
#                 except ValueError:
#                     raise forms.ValidationError("Account Number must be numeric.")
#         if count > 0:
#             if enabled > 1:
#                 raise forms.ValidationError("Only one Billing Account can be enabled")


# class BillingAccountForm(forms.ModelForm):

#     account_copy = forms.ImageField()
#     pan_copy = forms.ImageField()


#     class Meta:
#         model = models.BillingAccount
#         fields = ('merchant_id', 'type', 'account_number', 'ifsc_code','pan_number','pan_copy','account_copy', 'enabled')

#     def __init__(self, *args, **kwargs):
#         super(BillingAccountForm, self).__init__(*args, **kwargs)
#         if self.instance.pk:
#             self.fields['type'].required = False
#             self.fields['account_number'].required = False
#             self.fields['pan_number'].required = False
#             self.fields['ifsc_code'].required = False
#             self.fields['pan_copy'].required = False
#             self.fields['account_copy'].required = False
#             #self.fields['pan_copy'].disabled = True
#             #self.fields['account_copy'].disabled = True
#             self.fields['type'].widget = forms.TextInput(attrs={'readonly': True})
#             self.fields['account_number'].widget.attrs['readonly'] = True
#             self.fields['pan_number'].widget.attrs['readonly'] = True
#             self.fields['ifsc_code'].widget.attrs['readonly'] = True


class SPOCDetailsForm(forms.ModelForm):
    def clean(self):
        super().clean()

        # if not self.cleaned_data.get('number') and not self.cleaned_data.get('email'):
        #     raise forms.ValidationError("Email or  Phone Number is required!")

        if not self.cleaned_data.get('number') or ((self.cleaned_data.get('std_code')) and (not self.cleaned_data.get('number'))):
            raise forms.ValidationError("Phone Number is required!")

        if (not self.cleaned_data.get('std_code')) and (self.cleaned_data.get('number')):
            if self.cleaned_data.get('number') < 5000000000 or self.cleaned_data.get('number') > 9999999999:
                raise forms.ValidationError("Invalid Phone Number!")


