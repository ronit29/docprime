from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Div, Fieldset


# import your models here
from ondoc.diagnostic.models import (Lab, LabCertification, LabAward, LabAccreditation,
                                    LabManager, LabTiming, )
from ondoc.doctor.models import (Doctor, DoctorMobile, DoctorQualification, DoctorHospital,
                                DoctorLanguage, DoctorAward, DoctorAssociation, DoctorExperience,
                                DoctorMedicalService, DoctorImage,)


# import your django libraries here
from django import forms
from django.forms import inlineformset_factory


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


# import all lab onboarding forms here

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

        self.included = ('id', 'name', 'about', 'license', 'operational_since', 'parking', 'hospital', 'network_type', 'network', )
        for field in self.fields:
            if field not in self.included:
                field.required = False

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
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
        fields = ('id', 'name', 'about', 'license', 'operational_since', 'parking', 'hospital', 'network_type', 'network', )

class LabAddressForm(forms.ModelForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.included = ('building', 'sublocality', 'locality', 'city', 'state', 'country', 'pin_code', )
        for field in self.fields:
            if field not in self.included:
                field.required = False

        self.helper = FormHelper()
        self.helper.form_class = 'form-horizontal'
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

    class Meta:
        model = Lab
        fields = ('building', 'sublocality', 'locality', 'city', 'state', 'country', 'pin_code' )


class OTPForm(forms.Form):

    otp = forms.CharField(required=False, label="Please Enter the OTP sent on your Mobile", widget=forms.TextInput(attrs={'placeholder':'Enter OTP'}))
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_class = 'form-vertical'
        self.helper.add_input(Submit(name='submit',value='Submit',css_class='btn-primary btn-block'))
        self.helper.add_input(Submit(name='_resend_otp', value='Resend OTP', css_class='btn-primary btn-block'))



# include all formsets here

LabAwardFormSet = inlineformset_factory(Lab, LabAward, form = LabAwardForm,extra = 1, can_delete=True, exclude=('id', ))
LabCertificationFormSet = inlineformset_factory(Lab, LabCertification, form = LabCertificationForm, extra = 1, can_delete=True, exclude=('lab', ))
LabAccreditationFormSet = inlineformset_factory(Lab, LabAccreditation, form=LabAccreditationForm,extra = 1, can_delete=True, exclude=('lab', ))
LabManagerFormSet = inlineformset_factory(Lab, LabManager, form = LabManagerForm, extra = 1, can_delete=True, exclude=('lab', ))
LabTimingFormSet = inlineformset_factory(Lab, LabTiming, form = LabTimingForm,extra = 1, can_delete=True)

