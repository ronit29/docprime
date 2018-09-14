from django.forms import ModelForm, TextInput, EmailInput, FileInput, Select
from .models import OnlineLead, Career
from django import forms
import os


class OnlineLeadsForm(ModelForm):

    class Meta:
        model = OnlineLead
        widgets = {
            'member_type': Select(attrs={'class': 'form-control', 'id': 'select-profession'}),
            'name': TextInput(attrs={'placeholder': 'Name', 'class': 'form-control', 'id': 'name'}),
            'mobile': TextInput(attrs={'placeholder': 'Mobile Number', 'class': 'form-control', 'id': 'mobile',
                                       'type': 'number', 'min': 7000000000, 'max': 9999999999, }),
            'city_name': TextInput(attrs={'placeholder': 'City', 'class': 'form-control', 'id': 'city'}),
            'email': EmailInput(attrs={'placeholder': 'Email', 'class': 'form-control', 'id': 'email', 'pattern':
                                        "[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,3}$", 'oninvalid':
                                        "setCustomValidity('Enter a Valid Email Address')",
                                       'oninput': "setCustomValidity('')"}),
            }
        fields = ['member_type', 'name', 'city_name', 'mobile', 'email']


class CareersForm(ModelForm):

    def clean_resume(self):
        data = self.cleaned_data['resume']
        ext = os.path.splitext(data.name)[1]
        valid_extensions = ['.pdf', '.doc', '.docx']
        if not ext.lower() in valid_extensions:
            raise forms.ValidationError('Unsupported file extension.')
        if data.size > 10485760:
            raise forms.ValidationError('FileSize too large. Allowed filesize 10 MB')
        return data

    class Meta:
        model = Career
        widgets = {
            'profile_type': Select(attrs={'class': 'form-control'}),
            'name': TextInput(attrs={'placeholder': 'Your Name', 'class': 'form-control', 'id': 'name'}),
            'mobile': TextInput(attrs={'placeholder': 'Mobile Number', 'class': 'form-control', 'id': 'mobile',
                                       'type': 'number', 'min': 7000000000, 'max': 9999999999, }),
            'email': EmailInput(attrs={'placeholder': 'Email', 'class': 'form-control', 'id': 'email', 'pattern':
                                        "[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,3}$", 'oninvalid':
                                        "setCustomValidity('Enter a Valid Email Address')",
                                       'oninput': "setCustomValidity('')"}),
            'resume': FileInput(attrs={'id': 'upload-resume'}),
        }
        fields = ['profile_type', 'name', 'mobile', 'email', 'resume']

class SearchDataForm(forms.Form):

    file = forms.FileField()