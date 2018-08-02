from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Fieldset, Field
from ondoc.diagnostic.models import Lab, LabCertification, LabAward, LabAccreditation, LabManager, LabTiming, LabService, LabDoctorAvailability, LabDoctor, LabImage, LabDocument
from ondoc.doctor.models import (Doctor, DoctorMobile, DoctorQualification, DoctorClinicTiming, DoctorClinic,
                                DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
                                DoctorMedicalService, DoctorImage, DoctorDocument, DoctorEmail)

from ondoc.crm.admin.common import award_year_choices, hospital_operational_since_choices, practicing_since_choices, college_passing_year_choices
from django import forms
from django.forms import inlineformset_factory
from crispy_forms.utils import TEMPLATE_PACK

# include all forms here

class CustomField(Field):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.template = 'customfield.html'
        # self.extra_context = kwargs.pop('extra_context', self.extra_context)

        # self.xlabel_class = 'col-md-2'

    def render(self, form, form_style, context, template_pack=TEMPLATE_PACK, extra_context=None, **kwargs):

        if extra_context is None:
            extra_context = {}
        if 'label_class' in self.attrs:
            extra_context['label_class'] = self.attrs['label_class']
        if 'label-class' in self.attrs:
            extra_context['label_class'] = self.attrs['label-class']

        if 'field_class' in self.attrs:
            extra_context['field_class'] = self.attrs['field_class']
        if 'field-class' in self.attrs:
            extra_context['field_class'] = self.attrs['field-class']


        return super(CustomField, self).render(form, form_style, context, template_pack, extra_context, **kwargs)


class LabCertificationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False;
        # self.layout = Layout(CustomField('name', label_class='col-md-2', field_class='col-md-6'),DELETE())
        self.helper.layout = Layout(
                             Div(CustomField('name', label_class='col-md-3', field_class='col-md-9',wrapper_class='col-md-8'), Div(CustomField('DELETE', wrapper_class='col-md-12', label_class='delete-checkbox', field_class=''), css_class='col-md-3 col-md-offset-1'),css_class='row'))
        self.form_class = 'form-horizontal'


    name = forms.CharField(label='Cerfication Name')

    class Meta:
        model = LabCertification
        exclude = ['lab',]


class LabAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices, required=False)
    name = forms.CharField(label='Award Name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False;

        self.helper.layout = Layout(Div(CustomField('name', label_class='col-md-3', field_class='col-md-9', wrapper_class='col-md-6'),
                                    CustomField('year', label_class='col-md-2', field_class='col-md-6',wrapper_class='col-md-3'),
                                    Div(CustomField('DELETE'),css_class='col-md-3'), css_class='row'))
        self.form_class = 'form-horizontal'


    class Meta:
        model = LabAward
        exclude = ['lab',]

class LabTimingForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['start'].label = 'Open Time'
        self.fields['end'].label = 'Close Time'
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(Div(
                Div(CustomField('day', label_class='col-md-4 hidden', field_class='col-md-12'),css_class='col-md-2'),
                Div(CustomField('start', label_class='col-md-4 col-md-offset-1', label='Open Time', field_class='col-md-7'),css_class='col-md-4'),
                Div(CustomField('end', label_class='col-md-4 col-md-offset-1', label='Close Time',field_class='col-md-7'),css_class='col-md-4'),
                css_class='row'))

    class Meta:
        model = LabTiming
        exclude = ['lab',]


class LabManagerForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.fields.keys():
            self.fields[key].disabled = True

        self.helper = FormHelper()
        self.helper.form_tag = False;
        self.helper.layout = Layout(Div(
                Div(CustomField('contact_type', label_class='col-md-4', field_class='col-md-8'),css_class='col-md-4'),
                Div(CustomField('name', label_class='col-md-2 col-md-offset-2', field_class='col-md-8'),css_class='col-md-4'),
                Div(CustomField('number', label_class='col-md-3 col-md-offset-2', field_class='col-md-6'),css_class='col-md-3'),
                css_class='row'),
                Div(
                Div(CustomField('email', label_class='col-md-4', field_class='col-md-8'),css_class='col-md-4'),
                Div(CustomField('details', label_class='col-md-2 col-md-offset-2', field_class='col-md-8'),css_class='col-md-4'),
                css_class='row'))
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = LabManager
        exclude = ['lab',]


# class LabCertificationFormSetHelper(FormHelper):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         # self.layout = Layout(CustomField('name', label_class='col-md-2', field_class='col-md-6'),DELETE())
#         self.layout = Layout(CustomField('name', label_class='col-md-2', field_class='col-md-6'))
#         self.form_class = 'form-horizontal'


class LabAccreditationForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False;
        # self.layout = Layout(CustomField('name', label_class='col-md-2', field_class='col-md-6'),DELETE())
        self.helper.layout = Layout(
                             Div(CustomField('name', label_class='col-md-3', field_class='col-md-9',wrapper_class='col-md-8'), Div(CustomField('DELETE', wrapper_class='col-md-12', label_class='delete-checkbox', field_class=''), css_class='col-md-4'),css_class='row'))
        self.form_class = 'form-horizontal'

    name = forms.CharField(label='Accreditation Name')

    class Meta:
        model = LabAccreditation
        exclude = ['lab',]


class LabForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea)
    license = forms.CharField(required=True)
    operational_since = forms.ChoiceField(required=True, choices=hospital_operational_since_choices)

    # license = forms.CharField(disabled=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        #instance = getattr(self, 'instance', None)
        #if instance and instance.pk:
        self.fields['license'].widget.attrs['disabled'] = True
        self.fields['license'].required = False
        self.fields['hospital'].widget.attrs['disabled'] = True
        self.fields['network'].widget.attrs['disabled'] = True

        self.helper = FormHelper()
        self.helper.form_tag = False;
        # self.helper.form_class = 'form-horizontal'
        # self.helper.add_input(Submit('submit','Submit',css_class='btn-primary btn-block'))
        self.helper.layout = Layout(
            CustomField('name', label_class='col-md-1', field_class='col-md-5'),
            CustomField('about', label_class='col-md-1', field_class='col-md-10'),
            
            Div(
                Div(CustomField('license', label_class='col-md-2', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('operational_since', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'),
            Div(
                Div(CustomField('parking', label_class='col-md-2', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('hospital', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'),
            Div(                
                Div(CustomField('network', label_class='col-md-2', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('network_type', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'))


    class Meta:
        model = Lab
        fields = ('name', 'about', 'license', 'operational_since', 'parking', 'hospital', 'network_type', 'network', )

class LabAddressForm(forms.ModelForm):

    location = forms.CharField(disabled=True)
    pin_code = forms.CharField()
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.fields['location'].required = False
        self.helper.layout = Layout(
            Div(
                Div(CustomField('building', label_class='col-md-3', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('sublocality', label_class='col-md-3 col-md-offset-3', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'
            ),
            Div(
                Div(CustomField('locality', label_class='col-md-3', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('city', label_class='col-md-3 col-md-offset-3', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row',
            ),
            Div(
                Div(CustomField('state', label_class='col-md-3', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('country', label_class='col-md-3 col-md-offset-3', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row',
            ),
            Div(
                Div(CustomField('pin_code', label_class='col-md-3', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('location', label_class='col-md-3 col-md-offset-3', field_class='col-md-6'),css_class='col-md-6 hidden'),
                css_class='row',
            )
        )

    class Meta:
        model = Lab
        fields = ('building', 'sublocality', 'locality', 'city', 'state', 'country', 'pin_code','location' )

class LabOpenForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False;
        self.helper.layout = Layout(CustomField('always_open'))
    class Meta:
        model = Lab
        fields = ('always_open',)


class LabServiceForm(forms.ModelForm):

    #service = forms.CharField( disabled=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(CustomField('is_available', label_class='hidden', field_class='col-md-6'),
                                    CustomField('service', label_class='col-md-4', field_class='col-md-6'))

    class Meta:
        model = LabService
        exclude = ['lab',]
        # widgets = {'service': forms.CheckboxSelectMultiple}                

class LabDoctorAvailabilityForm(forms.ModelForm):

    #service = forms.CharField( disabled=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['slot'].widget.attrs['disabled'] = True
        # self.fields['slot'].required = True

        self.fields['is_male_available'].label =''
        self.fields['is_female_available'].label =''
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
                            Div(
                            Div(CustomField('slot', label_class='hidden'),css_class='col-md-6 col-sm-6 col-xs-6'), 
                            Div(Div(CustomField('is_male_available', wrapper_class='col-md-6'), css_class='col-md-6 col-sm-6 col-xs-6'),
                            Div(CustomField('is_female_available',  wrapper_class='col-md-6'), css_class='col-md-6 col-sm-6 col-xs-6'), css_class='col-sm-6 col-xs-6 col-md-5 col-md-offset-1')
                            ,css_class='clearfix'))


    class Meta:
        model = LabDoctorAvailability
        exclude = ['lab',]


class LabDoctorForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields['registration_number'].label =''
        
    class Meta:
        model = LabDoctor
        exclude = ['lab',]

class LabImageForm(forms.ModelForm):
    class Meta:
        model = LabImage
        exclude = ['lab',]


class LabDocumentForm(forms.ModelForm):
    class Meta:
        model = LabDocument
        exclude = ['lab',]

# class LabDoctorAvailabilityForm(forms.ModelForm):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.helper = FormHelper()
#         self.helper.form_tag = False;

#     class Meta:
#         model = LabDoctorAvailability
#         exclude = ['lab',]
        # widgets = {'service': forms.CheckboxSelectMultiple}


class OTPForm(forms.Form):

    otp = forms.CharField(required=False, label="Please Enter the OTP sent on your Mobile", widget=forms.TextInput(attrs={'placeholder':'Enter OTP'}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-vertical'
        self.helper.add_input(Submit(name='verify',value='Verify',css_class='btn col-md-5'))
        self.helper.add_input(Submit(name='_resend_otp', value='Resend OTP', css_class='btn col-md-5 col-md-offset-2'))


# include all formsets here
LabDoctorAvailabilityFormSet = inlineformset_factory(Lab, LabDoctorAvailability, form=LabDoctorAvailabilityForm, extra = 0, can_delete=True, exclude=('lab', ))
LabAwardFormSet = inlineformset_factory(Lab, LabAward, form=LabAwardForm, extra = 0, can_delete=True, exclude=('lab', ))
# LabCertificationFormSet = inlineformset_factory(Lab, LabCertification, form=LabCertificationForm,extra = 1, can_delete=True, exclude=('lab', ))
LabAccreditationFormSet = inlineformset_factory(Lab, LabAccreditation,form=LabAccreditationForm, extra = 0, can_delete=True, exclude=('lab', ))
LabManagerFormSet = inlineformset_factory(Lab, LabManager, form=LabManagerForm, extra = 0, can_delete=True, exclude=('lab', ))
LabTimingFormSet = inlineformset_factory(Lab, LabTiming, form = LabTimingForm, extra = 0, can_delete=True)
LabCertificationFormSet = inlineformset_factory(Lab, LabCertification, form=LabCertificationForm, extra = 0, can_delete=True, exclude=('lab', ))
LabServiceFormSet = inlineformset_factory(Lab, LabService, form=LabServiceForm, extra=0, exclude=('lab', ))
LabDoctorFormSet = inlineformset_factory(Lab, LabDoctor, form=LabDoctorForm, extra=1 ,can_delete=False, exclude=('lab', ))


# include all doctor onboarding forms here

class DoctorForm(forms.ModelForm):
    about = forms.CharField(widget=forms.Textarea)
    practicing_since = forms.ChoiceField(choices=practicing_since_choices, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gender'].required = True
        self.fields['license'].required = True
        # self.fields['email'].required = True
        self.fields['license'].label ='MCI Number'
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        # self.fields['hospitals'].required = False
        # self.fields['onboarding_status'].required = False
        self.helper.layout = Layout(
            Div(
                Div(CustomField('name', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-6'),
                Div(CustomField('gender', field_class='col-md-6',label_class='col-md-4'), css_class='col-md-6'),
                css_class = 'row'
            ),
            Div(
                CustomField('about',label_class='col-md-1', field_class='col-md-10')
            ),
            Div(
                Div(CustomField('license', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-6'),
                Div(CustomField('practicing_since', field_class='col-md-6',label_class='col-md-4'), css_class='col-md-6'),
                css_class = 'row'
            ),
            
        )

    class Meta:
        model = Doctor
        fields = ('name', 'about', 'gender', 'practicing_since', 'license')


class DoctorMobileForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields['is_primary'].label = ''
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(
            Div(
                Div(CustomField('is_primary',disabled=True, field_class='col-md-12',label_class='hidden'), css_class='col-md-1 col-xs-2 number-check'),
                Div(CustomField('number', disabled=True, field_class='col-md-8',label_class='hidden'), css_class='col-md-6 col-xs-8'), 
                 css_class='clearfix'
            ))

    class Meta:
        model = DoctorMobile
        fields = ('is_primary', 'number', )

class DoctorEmailForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.fields['is_primary'].label = ''
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(
            Div(
                Div(CustomField('is_primary',disabled=True, field_class='col-md-12',label_class='hidden'), css_class='col-md-1 col-xs-2 number-check'),
                Div(CustomField('email',disabled=True, field_class='col-md-8',label_class='hidden'), css_class='col-md-6 col-xs-8'), 
                css_class='clearfix'
            ))

    class Meta:
        model = DoctorEmail
        fields = ('is_primary', 'email', )


class DoctorQualificationForm(forms.ModelForm):
    passing_year = forms.ChoiceField(choices=college_passing_year_choices, required=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(
                Div(CustomField('qualification', field_class='col-md-7',label_class='col-md-3'), css_class='col-md-5'),
                Div(CustomField('specialization', field_class='col-md-7',label_class='col-md-4'), css_class='col-md-5'),
                css_class = 'row'),
                Div(
                Div(CustomField('college', field_class='col-md-7',label_class='col-md-3'), css_class='col-md-5'),
                Div(CustomField('passing_year', field_class='col-md-7',label_class='col-md-4'), css_class='col-md-5'),
                Div(CustomField('DELETE'), css_class='col-md-1 col-md-offset-1'),
                css_class = 'row'))
    class Meta:
        model = DoctorQualification
        fields = ('qualification', 'specialization','college','passing_year')


class DoctorClinicForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.fields.keys():
            self.fields[key].disabled = True

        self.helper = FormHelper()
        # self.fields['start'].label = 'Open Time'
        # self.fields['end'].label = 'Close Time'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(
                Div(CustomField('hospital', field_class='col-md-7',label_class='col-md-3'), css_class='col-md-6'),
                # Div(CustomField('day', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-6'),
                css_class='row'),
        )

    class Meta:
        model = DoctorClinic
        fields = ('id', 'hospital',)


class DoctorClinicTimingForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in self.fields.keys():
            self.fields[key].disabled = True

        self.helper = FormHelper()
        self.fields['start'].label = 'Open Time'
        self.fields['end'].label = 'Close Time'
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(

                    Div(CustomField('day', field_class='col-md-7', label_class='col-md-4'), css_class='col-md-3'),
                    Div(CustomField('start', field_class='col-md-7', label_class='col-md-5'), css_class='col-md-3'),
                    Div(CustomField('end', field_class='col-md-7', label_class='col-md-5'), css_class='col-md-3'),
                    Div(CustomField('fees', field_class='col-md-7', label_class='col-md-4'), css_class='col-md-3'),
                    css_class='row',)
                    )

    class Meta:
        model = DoctorClinicTiming
        fields = ('day', 'start', 'end', 'fees')



class DoctorLanguageForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(
                Div(CustomField('language', field_class='col-md-7',label_class='col-md-3'), css_class='col-md-9'),
                Div(CustomField('DELETE', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-3'),
                css_class = 'row'),)

    class Meta:
        model = DoctorLanguage
        fields = ('language', )


class DoctorAwardForm(forms.ModelForm):

    year = forms.ChoiceField(choices=award_year_choices, required=True)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.fields['name'].label = 'Award Name'
        self.helper.layout = Layout(Div(
                Div(CustomField('name', field_class='col-md-7',label_class='col-md-3'), css_class='col-md-6'),
                Div(CustomField('year', field_class='col-md-7',label_class='col-md-3'), css_class='col-md-4'),
                Div(CustomField('DELETE', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-2'),
                css_class = 'row'),)

    class Meta:
        model = DoctorAward
        fields = ('name', 'year',)


class DoctorAssociationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False
        self.helper.layout = Layout(Div(
                Div(CustomField('name', field_class='col-md-11',label_class='col-md-3 hidden'), css_class='col-md-6 col-xs-10'),
                Div(CustomField('DELETE', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-2 col-xs-2'),
                css_class = 'row'),)


    class Meta:
        model = DoctorAssociation
        fields = ('name', )


class DoctorExperienceForm(forms.ModelForm):

    start_year = forms.ChoiceField(choices=practicing_since_choices, required=True)
    end_year = forms.ChoiceField(choices=practicing_since_choices, required=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(Div(
                Div(CustomField('hospital', field_class='col-md-8',label_class='col-md-3'), css_class='col-md-4'),
                Div(CustomField('start_year', field_class='col-md-7',label_class='col-md-5'), css_class='col-md-3'),
                Div(CustomField('end_year', field_class='col-md-7',label_class='col-md-5'), css_class='col-md-3'),
                Div(CustomField('DELETE', field_class='col-md-7',label_class='col-md-2'), css_class='col-md-2'),
                css_class = 'row'),)


    class Meta:
        model = DoctorExperience
        fields = ('hospital', 'start_year', 'end_year', )


class DoctorMedicalServiceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorMedicalService
        fields = ('service', )

class DoctorImageForm(forms.ModelForm):
    class Meta:
        model = DoctorImage
        exclude = ['doctor',]


class DoctorDocumentForm(forms.ModelForm):
    class Meta:
        model = DoctorDocument
        exclude = ['doctor',]


class RequiredFormset(forms.BaseInlineFormSet):

    def clean(self):
        super().clean()
        if any(self.errors):
            return


    class Meta:
        abstract=True

class BaseDoctorMobileFormSet(RequiredFormset):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        primary = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('is_primary'):
                primary += 1

        if count>0:
            if primary==0:
                self.forms[0].add_error('number', 'One primary number is required')
                #self.add_error('is_primary', "One primary number is required")
                #raise forms.ValidationError("One primary number is required")
            if primary>=2:
                self.forms[0].add_error('number', "Only one mobile number can be primary")
                # self.add_error('is_primary', "Only one mobile number can be primary")
                #raise forms.ValidationError("Only one mobile number can be primary")


class BaseDoctorEmailFormSet(RequiredFormset):
    def clean(self):
        super().clean()
        primary = 0
        count = 0
        for value in self.cleaned_data:
            count += 1
            if value.get('is_primary'):
                primary += 1

        if count>0:
            if primary==0:
                self.forms[0].add_error('email', 'One email is required')
                #self.add_error('is_primary', "One primary number is required")
                #raise forms.ValidationError("One primary number is required")
            if primary>=2:
                self.forms[0].add_error('email', "Only one email can be primary")
                # self.add_error('is_primary', "Only one mobile number can be primary")
                #raise forms.ValidationError("Only one mobile number can be primary")




DoctorEmailFormSet = inlineformset_factory(Doctor, DoctorEmail,formset=BaseDoctorEmailFormSet, form = DoctorEmailForm,extra = 0, can_delete=False, exclude=('doctor', ))
DoctorMobileFormSet = inlineformset_factory(Doctor, DoctorMobile,formset = BaseDoctorMobileFormSet, form = DoctorMobileForm,extra = 0, can_delete=False, exclude=('doctor', ))
DoctorQualificationFormSet = inlineformset_factory(Doctor, DoctorQualification, form = DoctorQualificationForm,extra = 0, can_delete=True, exclude=('doctor', ))
DoctorClinicFormSet = inlineformset_factory(Doctor, DoctorClinic, form = DoctorClinicForm,extra = 0, can_delete=True, exclude=('doctor', ))
DoctorClinicTimingFormSet = inlineformset_factory(DoctorClinic, DoctorClinicTiming, form=DoctorClinicTimingForm, extra=0, can_delete=True, exclude=('doctor_clinic', ))
DoctorLanguageFormSet = inlineformset_factory(Doctor, DoctorLanguage, form = DoctorLanguageForm,extra = 0, can_delete=True, exclude=('doctor', ))
DoctorAwardFormSet = inlineformset_factory(Doctor, DoctorAward, form = DoctorAwardForm,extra = 0, can_delete=True, exclude=('doctor', ))
DoctorAssociationFormSet = inlineformset_factory(Doctor, DoctorAssociation, form = DoctorAssociationForm,extra = 0, can_delete=True, exclude=('doctor', ))
DoctorExperienceFormSet = inlineformset_factory(Doctor, DoctorExperience, form = DoctorExperienceForm,extra = 0, can_delete=True, exclude=('doctor', ))
DoctorServiceFormSet = inlineformset_factory(Doctor, DoctorMedicalService, form = DoctorMedicalServiceForm,extra = 0, can_delete=True, exclude=('doctor', ))
# DoctorImageFormSet = inlineformset_factory(Doctor, DoctorImage, form = DoctorImageForm,extra = 0, can_delete=True, exclude=('doctor', ))
