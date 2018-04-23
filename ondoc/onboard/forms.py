from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Fieldset, Field
from ondoc.diagnostic.models import Lab, LabCertification, LabAward, LabAccreditation, LabManager, LabTiming, LabService
from ondoc.doctor.models import (Doctor, DoctorMobile, DoctorQualification, DoctorHospital,
                                DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
                                DoctorMedicalService, DoctorImage,)

from ondoc.crm.admin.common import award_year_choices
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
                             Div(CustomField('name', label_class='col-md-3', field_class='col-md-9',wrapper_class='col-md-8'), Div(CustomField('DELETE', wrapper_class='col-md-12', label_class='delete-checkbox', field_class=''), css_class='col-md-4'),css_class='row'))
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
                                    Field('DELETE', css_class='col-md-3'), css_class='row'))
        self.form_class = 'form-horizontal'


    class Meta:
        model = LabAward
        exclude = ['lab',]

class LabTimingForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['start'].label = 'Open Time'
        self.fields['end'].label = 'Cloe Time'
        self.helper = FormHelper()
        self.helper.form_tag = False;
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(Div(
                Div(CustomField('day', label_class='col-md-4 hidden', field_class='col-md-12'),css_class='col-md-3'),
                Div(CustomField('start', label_class='col-md-4', label='Open Time', field_class='col-md-6'),css_class='col-md-4'),
                Div(CustomField('end', label_class='col-md-4 ', label='Close Time',field_class='col-md-6'),css_class='col-md-4'),
                Div(CustomField('DELETE'), css_class='col-md-1'),
                css_class='row'))

    class Meta:
        model = LabTiming
        exclude = ['lab',]


class LabManagerForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False;
        self.helper.layout = Layout(Div(
                Div(CustomField('contact_type', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-4'),
                Div(CustomField('name', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-4'),
                Div(CustomField('number', label_class='col-md-4 col-md-offset-2', field_class='col-md-6'),css_class='col-md-4'),
                css_class='row'),
                Div(
                Div(CustomField('email', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-4'),
                Div(CustomField('details', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-4'),
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False;
        # self.helper.form_class = 'form-horizontal'
        # self.helper.add_input(Submit('submit','Submit',css_class='btn-primary btn-block'))
        self.helper.layout = Layout(
            CustomField('name', label_class='col-md-2', field_class='col-md-10'),
            CustomField('about', label_class='col-md-2', field_class='col-md-10'),
            
            Div(
                Div(CustomField('license', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('operational_since', label_class='col-md-4 col-md-offset-2', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'),
            Div(
                Div(CustomField('parking', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('hospital', label_class='col-md-4 col-md-offset-2', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'),

        )


    class Meta:
        model = Lab
        exclude = []

class LabAddressForm(LabForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper.form_class = 'form-horizontal'
        self.helper.form_tag = False;
        self.helper.layout = Layout(
            Div(
                Div(CustomField('building', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('sublocality', label_class='col-md-4 col-md-offset-2', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row'
            ),
            Div(
                Div(CustomField('locality', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('city', label_class='col-md-4 col-md-offset-2', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row',
            ),
            Div(
                Div(CustomField('state', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                Div(CustomField('country', label_class='col-md-4 col-md-offset-2', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row',
            ),
            Div(
                Div(CustomField('pin_code', label_class='col-md-4', field_class='col-md-6'),css_class='col-md-6'),
                css_class='row',
            )
        )

class LabServiceForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False;

    class Meta:
        model =LabService
        exclude = ['lab',]
        widgets = {'service': forms.CheckboxSelectMultiple}


class OTPForm(forms.Form):

    otp = forms.CharField(required=False, label="Please Enter the OTP sent on your Mobile", widget=forms.TextInput(attrs={'placeholder':'Enter OTP'}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-vertical'
        self.helper.add_input(Submit(name='submit',value='Submit',css_class='btn-primary btn-block'))
        self.helper.add_input(Submit(name='_resend_otp', value='Resend OTP', css_class='btn-primary btn-block'))



# include all formsets here

LabAwardFormSet = inlineformset_factory(Lab, LabAward, form=LabAwardForm, extra = 1, can_delete=True, exclude=('lab', ))
# LabCertificationFormSet = inlineformset_factory(Lab, LabCertification, form=LabCertificationForm,extra = 1, can_delete=True, exclude=('lab', ))
LabAccreditationFormSet = inlineformset_factory(Lab, LabAccreditation,form=LabAccreditationForm, extra = 1, can_delete=True, exclude=('lab', ))
LabManagerFormSet = inlineformset_factory(Lab, LabManager, form=LabManagerForm, extra = 1, can_delete=True, exclude=('lab', ))
LabTimingFormSet = inlineformset_factory(Lab, LabTiming, form = LabTimingForm, extra = 1, can_delete=True)
LabCertificationFormSet = inlineformset_factory(Lab, LabCertification, form=LabCertificationForm, extra = 2, can_delete=True, exclude=('lab', ))
LabServiceFormSet = inlineformset_factory(Lab, LabService, form=LabServiceForm, extra = 2, exclude=('lab', ))



# include all doctor onboarding forms here

class DoctorForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
        self.helper.layout = Layout(
            Div(
                Div('name',css_class='col-md-6',),
                Div('gender',css_class='col-md-6',),
                css_class='row',
            ),
            Div(
                Div('about',css_class='col-md-12',),
                css_class='row',
            ),
            Div(
                Div('license',css_class='col-md-6',),
                Div('practicing_since',css_class='col-md-6',),
                css_class='row',
            ),
            Div(
                Div('email',css_class='col-md-6',),
                Div('additional_details',css_class='col-md-6',),
                css_class='row',
            ),
        )

    class Meta:
        model = Doctor
        exclude = ('id',)


class DoctorMobileForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorMobile
        fields = ('country_code', 'number', )


class DoctorQualificationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorQualification
        fields = ('qualification', 'specialization', )


class DoctorHospitalForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorHospital
        fields = ('hospital', 'day', 'start', 'end', 'fees', )


class DoctorLanguageForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorLanguage
        fields = ('language', )


class DoctorAwardForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorAward
        fields = ('name', 'year', )


class DoctorAssociationForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorAssociation
        fields = ('name', )


class DoctorExperienceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorExperience
        fields = ('hospital', 'start_year', 'end_year', )


class DoctorMedicalServiceForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorMedicalService
        fields = ('service', )


class DoctorImageForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'

    class Meta:
        model = DoctorImage
        fields = ('name', )


DoctorMobileFormSet = inlineformset_factory(Doctor, DoctorMobile, form = DoctorMobileForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorQualificationFormSet = inlineformset_factory(Doctor, DoctorQualification, form = DoctorQualificationForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorHospitalFormSet = inlineformset_factory(Doctor, DoctorHospital, form = DoctorHospitalForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorLanguageFormSet = inlineformset_factory(Doctor, DoctorLanguage, form = DoctorLanguageForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorAwardFormSet = inlineformset_factory(Doctor, DoctorAward, form = DoctorAwardForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorAssociationFormSet = inlineformset_factory(Doctor, DoctorAssociation, form = DoctorAssociationForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorExperienceFormSet = inlineformset_factory(Doctor, DoctorExperience, form = DoctorExperienceForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorServiceFormSet = inlineformset_factory(Doctor, DoctorMedicalService, form = DoctorMedicalServiceForm,extra = 1, can_delete=True, exclude=('id', ))
DoctorImageFormSet = inlineformset_factory(Doctor, DoctorImage, form = DoctorImageForm,extra = 1, can_delete=True, exclude=('id', ))

