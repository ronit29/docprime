from django.shortcuts import render, HttpResponse, HttpResponseRedirect, redirect
from django.conf.urls import url
from django.conf import settings
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats
from django.utils.safestring import mark_safe
from django.contrib.gis import forms
from django.contrib.gis import admin
from django.contrib.admin import SimpleListFilter
from reversion.admin import VersionAdmin
from import_export.admin import ImportExportMixin
from django.db.models import Q
from django.db import models
from django.utils.dateparse import parse_datetime
from dateutil import tz
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import make_aware
from django.utils.html import format_html_join
import pytz
from ondoc.api.v1.diagnostic.views import TimeSlotExtraction
from ondoc.doctor.models import Hospital
from ondoc.diagnostic.models import (LabTiming, LabImage,
    LabManager,LabAccreditation, LabAward, LabCertification, AvailableLabTest,
    LabNetwork, Lab, LabOnboardingToken, LabService,LabDoctorAvailability,
    LabDoctor, LabDocument, LabTest, DiagnosticConditionLabTest, LabNetworkDocument, LabAppointment)
from .common import *
from ondoc.authentication.models import GenericAdmin, User, QCModel
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.admin.widgets import AdminSplitDateTime
from ondoc.crm.admin.doctor import CustomDateInput, TimePickerWidget


class LabTestResource(resources.ModelResource):
    excel_id = fields.Field(attribute='excel_id', column_name='Test ID')
    test_type = fields.Field(attribute='test_type', column_name='Test Type')
    sample_type = fields.Field(attribute='sample_type', column_name='Test SubType')
    #sub_type = fields.Field(attribute='sub_type', column_name='Test SubType')
    name = fields.Field(attribute='name', column_name="Test Name")
    is_package = fields.Field(attribute="is_package", column_name="Package (Y/N)", default="")
    why = fields.Field(attribute='why', column_name="Why This Test")
    pre_test_info = fields.Field(attribute='pre_test_info', column_name="Pre-Test Information")
    preferred_time = fields.Field(attribute='preferred_time', column_name="Preferred Time of day")
    sample_amount = fields.Field(attribute='sample_amount', column_name="Amount of Sample")
    expected_tat = fields.Field(attribute='expected_tat', column_name="Expected TAT")
    sample_collection_instructions = fields.Field(attribute='sample_collection_instructions',
                                                  column_name="How to Collect Sample")
    sample_handling_instructions = fields.Field(attribute='sample_handling_instructions',
                                                column_name="Sample handling before pickup")
    category = fields.Field(attribute='category', column_name='Category')
    home_collection_possible = fields.Field(attribute='home_collection_possible', column_name='Home Collection')
    class Meta:
        model = LabTest
        import_id_fields = ('excel_id',)

    def before_save_instance(self, instance, using_transactions, dry_run):
        instance.test_type = (LabTest.RADIOLOGY if instance.test_type.strip().lower() == 'radiology'
                              else LabTest.PATHOLOGY if instance.test_type.strip().lower() == 'pathology'
                              else None) if instance.test_type else None
        instance.is_package = (True if instance.is_package.strip().lower() == "yes" else False) if instance.is_package else False
        instance.excel_id = instance.excel_id.strip() if instance.excel_id else ""
        instance.sample_type = instance.sample_type.strip().lower() if instance.sample_type else ""
        instance.name = instance.name.strip() if instance.name else ""
        instance.why = instance.why.strip() if instance.why else ""
        instance.pre_test_info = instance.pre_test_info.strip() if instance.pre_test_info else ""
        instance.preferred_time = instance.preferred_time.strip() if instance.preferred_time else ""
        instance.sample_amount = str(instance.sample_amount).strip() if instance.sample_amount else ""
        instance.expected_tat = instance.expected_tat.strip() if instance.expected_tat else ""
        instance.category = instance.category.strip().upper() if instance.category else ""
        instance.sample_handling_instructions = (instance.sample_handling_instructions.strip()
                                                 if instance.sample_handling_instructions else "")
        instance.sample_collection_instructions = (instance.sample_collection_instructions.strip()
                                                   if instance.sample_collection_instructions else "")
        instance.home_collection_possible = (True if instance.home_collection_possible.strip().lower() == "yes" else False) if instance.home_collection_possible else False
        super().before_save_instance(instance, using_transactions, dry_run)

    # def after_save_instance(self, instance, using_transactions, dry_run):
    #     sub_type = instance.sub_type.strip().split(",")
    #     for sub_type_name in sub_type:
    #         obj, created = LabTestSubType.objects.get_or_create(name=sub_type_name.strip())
    #         LabTestSubTypeMapping.objects.get_or_create(lab_test=instance,
    #                                                     test_sub_type=obj)


class LabTimingForm(forms.ModelForm):
    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end and start>=end:
            raise forms.ValidationError("Start time should be less than end time")


class LabTimingInline(admin.TabularInline):
    model = LabTiming
    form = LabTimingForm
    extra = 0
    can_delete = True
    show_change_link = False

# class LabImageForm(forms.ModelForm):
#     name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))

class LabImageInline(admin.TabularInline):
    model = LabImage
    # form = LabImageForm
    extra = 0
    can_delete = True
    show_change_link = False
    max_num = 3


class LabManagerInline(admin.TabularInline):
    model = LabManager
    formfield_overrides = {
        models.BigIntegerField: {'widget': forms.TextInput},
    }

    extra = 0
    can_delete = True
    show_change_link = False


class LabAccreditationInline(admin.TabularInline):
    model = LabAccreditation
    extra = 0
    can_delete = True
    show_change_link = False


class LabAwardForm(forms.ModelForm):
    year = forms.ChoiceField(choices=award_year_choices_no_blank, required=True)


class LabAwardInline(admin.TabularInline):
    model = LabAward
    form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class LabServiceInline(admin.TabularInline):
    model = LabService
    #form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


class LabDoctorInline(admin.TabularInline):
    model = LabDoctor
    #form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False

# class LabDocumentForm(forms.ModelForm):
#     name = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'image/x-png,image/jpeg'}))


class LabDocumentFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        choices = dict(LabDocument.CHOICES)
        count = {}
        for key, value in LabDocument.CHOICES:
            count[key] = 0

        for value in self.cleaned_data:
            if value and not value['DELETE']:
                count[value['document_type']] += 1

        for key, value in count.items():
            if not key==LabDocument.ADDRESS and value>1:
                raise forms.ValidationError("Only one "+choices[key]+" is allowed")

        if not self.instance.network or not self.instance.network.is_billing_enabled:
            if '_submit_for_qc' in self.request.POST or '_qc_approve' in self.request.POST:
                for key, value in count.items():
                    if not key==LabDocument.GST and value<1:
                        raise forms.ValidationError(choices[key]+" is required")



class LabDocumentInline(admin.TabularInline):
    model = LabDocument
    formset = LabDocumentFormSet
    # form = LabDocumentForm
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        formset.request = request
        return formset

    extra = 0
    can_delete = True
    show_change_link = False


class LabDoctorAvailabilityInline(admin.TabularInline):
    model = LabDoctorAvailability
    #form = LabAwardForm
    extra = 0
    can_delete = True
    show_change_link = False


# class GenericAdminInline(admin.TabularInline):
#     model = GenericAdmin
#     extra = 0
#     can_delete = True
#     show_change_link = False
#     readonly_fields = ['user']
#     verbose_name_plural = "Admins"


class LabCertificationInline(admin.TabularInline):
    model = LabCertification
    extra = 0
    can_delete = True
    show_change_link = False


class LabForm(FormCleanMixin):
    about = forms.CharField(widget=forms.Textarea, required=False)
    primary_mobile = forms.CharField(required=True)
    primary_email = forms.EmailField(required=True)
    city = forms.CharField(required=True)
    operational_since = forms.ChoiceField(required=False, choices=hospital_operational_since_choices)
    onboarding_status = forms.ChoiceField(disabled=True, required=False, choices=Lab.ONBOARDING_STATUS)
    # agreed_rate_list = forms.FileField(required=False, widget=forms.FileInput(attrs={'accept':'application/pdf'}))

    class Meta:
        model = Lab
        exclude=()
        # exclude = ('pathology_agreed_price_percentage', 'pathology_deal_price_percentage', 'radiology_agreed_price_percentage',
        #            'radiology_deal_price_percentage', )

    def clean_operational_since(self):
        data = self.cleaned_data['operational_since']
        if data == '':
            return None
        return data

    def validate_qc(self):
        qc_required = {'name':'req','location':'req','operational_since':'req','parking':'req',
            'license':'req','building':'req','locality':'req','city':'req','state':'req',
            'country':'req','pin_code':'req','network_type':'req','lab_image':'count'}

        if self.instance.network and self.instance.network.data_status != QCModel.QC_APPROVED:
            raise forms.ValidationError("Lab Network is not QC approved.")

        if not self.instance.network or not self.instance.network.is_billing_enabled:
            qc_required.update({
                'lab_documents': 'count'
            })
        for key,value in qc_required.items():
            if value=='req' and not self.cleaned_data[key]:
                raise forms.ValidationError(key+" is required for Quality Check")
            if value=='count' and int(self.data[key+'-TOTAL_FORMS'])<=0:
                raise forms.ValidationError("Atleast one entry of "+key+" is required for Quality Check")
        if self.cleaned_data['network_type']==2 and not self.cleaned_data['network']:
            raise forms.ValidationError("Network cannot be empty for Network Lab")


class LabCityFilter(SimpleListFilter):
    title = 'city'
    parameter_name = 'city'

    def lookups(self, request, model_admin):
        cities = set([(c['city'].upper(),c['city'].upper()) if(c.get('city')) else ('','') for c in Lab.objects.values('city')])
        return cities

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(city__iexact=self.value()).distinct()


class LabAdmin(ImportExportMixin, admin.GeoModelAdmin, VersionAdmin, ActionAdmin, QCPemAdmin):

    change_list_template = 'superuser_import_export.html'

    list_display = ('name', 'updated_at', 'onboarding_status','data_status', 'list_created_by', 'list_assigned_to', 'get_onboard_link',)

    # readonly_fields=('onboarding_status', )
    list_filter = ('data_status', 'onboarding_status', 'is_insurance_enabled', LabCityFilter)

    exclude = ('is_home_pickup_available','search_key','pathology_agreed_price_percentage', 'pathology_deal_price_percentage', 'radiology_agreed_price_percentage',
                   'radiology_deal_price_percentage', )

    def get_readonly_fields(self, request, obj=None):
        if (not request.user.groups.filter(name='qc_group').exists()) and (not request.user.is_superuser):
            return ('lead_url','matrix_lead_id','matrix_reference_id', 'lab_pricing_group', 'is_live')
        return ('lead_url','matrix_lead_id','matrix_reference_id', 'is_live')

    def lead_url(self, instance):
        if instance.id:
            ref_id = instance.matrix_reference_id
            if ref_id is not None:
                html ='''<a href='/admin/lead/doctorlead/%s/change/' target=_blank>Lead Page</a>'''%(ref_id)
                return mark_safe(html)
        else:
            return mark_safe('''<span></span>''')

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            url('onboardlab_admin/(?P<userid>\d+)/', self.admin_site.admin_view(self.onboardlab_admin), name="onboardlab_admin"),
        ]
        return my_urls + urls

    def onboardlab_admin(self, request, userid):
        host = request.get_host()
        try:
            lab_obj = Lab.objects.get(id = userid)
        except Exception as e:
            return HttpResponse('invalid lab')

        count = 0
        try:
            count = LabOnboardingToken.objects.filter(lab = lab_obj).count()
        except Exception as e:
            pass
            # last_token = None

        #last_url = None
        #created_at = ""
        # if last_token:
        #     last_url = host+'/onboard/lab?token='+str(last_token.token)
        #     created_at = last_token.created_at

        # check for errors
        errors = []
        required = ['name','about','license','primary_email','primary_mobile','operational_since', 'parking', 'network_type', 'location','building','city','state','country','pin_code','agreed_rate_list']
        for req in required:
            if not getattr(lab_obj, req):
                errors.append(req+' is required')

        if not lab_obj.locality and not lab_obj.sublocality:
            errors.append('locality or sublocality is required')

        length_required = ['labservice', 'labdoctoravailability', 'labmanager', 'labaccreditation']
        if lab_obj.labservice_set.filter(service = LabService.RADIOLOGY).exists():
            length_required.append('labdoctor')
        for req in length_required:
            if not len(getattr(lab_obj, req+'_set').all()):
                errors.append(req + ' is required')
        if not lab_obj.lab_timings.exists():
            errors.append('Lab Timings is required')

        #if not lab_obj.lab_services_set:
            # errors.append('lab services are required')

        # if not lab_obj.license:
        #     errors.append('License is required')
        # if not lab_obj.primary_email:
        #     errors.append('Primary Email is required')
        # if not lab_obj.primary_mobile:
        #     errors.append('Primary Mobile is required')
        # if not lab_obj.agreed_rate_list:
        #     errors.append('Agreed rate list in required')

        return render(request, 'onboardlab.html', {'lab': lab_obj, 'count': count, 'errors': errors})

    def get_onboard_link(self, obj = None):
        if obj.data_status == Lab.IN_PROGRESS and obj.onboarding_status in (Lab.NOT_ONBOARDED, Lab.REQUEST_SENT):
            return mark_safe("<a href='/admin/diagnostic/lab/onboardlab_admin/%s'>generate onboarding url</a>" % obj.id)
        return ""
    get_onboard_link.allow_tags = True

    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user
        if not obj.assigned_to:
            obj.assigned_to = request.user
        if '_submit_for_qc' in request.POST:
            obj.data_status = 2
        if '_qc_approve' in request.POST:
            obj.data_status = 3
        if '_mark_in_progress' in request.POST:
            obj.data_status = 1

        super().save_model(request, obj, form, change)



    def get_form(self, request, obj=None, **kwargs):
        form = super(LabAdmin, self).get_form(request, obj=obj, **kwargs)
        form.request = request
        form.base_fields['network'].queryset = LabNetwork.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        form.base_fields['hospital'].queryset = Hospital.objects.filter(Q(data_status = 2) | Q(data_status = 3) | Q(created_by = request.user))
        form.base_fields['assigned_to'].queryset = User.objects.filter(user_type=User.STAFF)
        if (not request.user.is_superuser) and (not request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists()):
            form.base_fields['assigned_to'].disabled = True
        return form

    form = LabForm
    search_fields = ['name', 'lab_pricing_group__group_name', ]
    inlines = [LabDoctorInline, LabServiceInline, LabDoctorAvailabilityInline, LabCertificationInline, LabAwardInline, LabAccreditationInline,
        LabManagerInline, LabTimingInline, LabImageInline, LabDocumentInline]
    autocomplete_fields = ['lab_pricing_group', ]

    map_width = 200
    map_template = 'admin/gis/gmap.html'

    class Media:
        js = ('js/admin/ondoc.js',)


class LabAppointmentForm(forms.ModelForm):

    start_date = forms.DateField(widget=CustomDateInput(format=('%d-%m-%Y'), attrs={'placeholder':'Select a date'}))
    start_time = forms.CharField(widget=TimePickerWidget())

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        if cleaned_data.get('start_date') and cleaned_data.get('start_time'):
            date_time_field = str(cleaned_data.get('start_date')) + " " + str(cleaned_data.get('start_time'))
            dt_field = parse_datetime(date_time_field)
            time_slot_start = make_aware(dt_field)
        if time_slot_start:
            hour = round(float(time_slot_start.hour) + (float(time_slot_start.minute) * 1 / 60), 2)
        else:
            raise forms.ValidationError("Enter valid start date and time.")
        if self.instance.id:
            lab_test = self.instance.lab_test.all()
            lab = self.instance.lab
        elif cleaned_data.get('lab') and cleaned_data.get('lab_test'):
            lab_test = cleaned_data.get('lab_test').all()
            lab = cleaned_data.get('lab')
        else:
            raise forms.ValidationError("Lab and lab test details not entered.")

        if not lab.lab_pricing_group:
            raise forms.ValidationError("Lab is not in any lab pricing group.")

        selected_test_ids = lab_test.values_list('test', flat=True)
        if not LabTiming.objects.filter(
                lab=lab,
                lab__lab_pricing_group__available_lab_tests__test__in=selected_test_ids,
                day=time_slot_start.weekday(),
                start__lte=hour, end__gt=hour).exists():
            raise forms.ValidationError("This lab test is not available on selected day and time.")

        return cleaned_data


class LabAppointmentAdmin(admin.ModelAdmin):
    form = LabAppointmentForm
    list_display = ('get_profile', 'get_lab', 'status', 'time_slot_start', 'created_at',)
    list_filter = ('status', )
    date_hierarchy = 'created_at'

    def get_profile(self, obj):
        return obj.profile.name

    get_profile.admin_order_field = 'profile'
    get_profile.short_description = 'Profile Name'

    def get_lab(self, obj):
        return obj.lab.name

    get_lab.admin_order_field = 'lab'
    get_lab.short_description = 'Lab Name'

    def formfield_for_choice_field(self, db_field, request, **kwargs):
        allowed_status_for_agent = [(LabAppointment.RESCHEDULED_PATIENT, 'Rescheduled by patient'),
                                    (LabAppointment.RESCHEDULED_LAB, 'Rescheduled by lab'),
                                    (LabAppointment.ACCEPTED, 'Accepted'),
                                    (LabAppointment.CANCELLED, 'Cancelled')]
        if db_field.name == "status" and request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            kwargs['choices'] = allowed_status_for_agent
        return super().formfield_for_choice_field(db_field, request, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        if obj is not None and obj.time_slot_start:
            time_slot_start = timezone.localtime(obj.time_slot_start, pytz.timezone(settings.TIME_ZONE))
            form.base_fields['start_date'].initial = time_slot_start.strftime('%Y-%m-%d') if time_slot_start else None
            form.base_fields['start_time'].initial = time_slot_start.strftime('%H:%M') if time_slot_start else None
        return form

    def get_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ('lab', 'lab_test', 'profile', 'user', 'profile_detail', 'status', 'price', 'agreed_price',
                    'deal_price', 'effective_price', 'start_date', 'start_time', 'otp', 'payment_status',
                    'payment_type', 'insurance', 'is_home_pickup', 'address', 'outstanding')
        elif request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('lab_name', 'get_lab_test', 'employees_details', 'used_profile_name', 'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_number', 'price', 'agreed_price',
                    'deal_price', 'effective_price', 'payment_status',
                    'payment_type', 'insurance', 'is_home_pickup', 'address', 'outstanding', 'status', 'start_date', 'start_time')
        else:
            return ()

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_superuser:
            return ()
        elif request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists():
            return ('lab_name', 'get_lab_test', 'employees_details', 'used_profile_name', 'used_profile_number', 'default_profile_name',
                    'default_profile_number', 'user_number', 'price', 'agreed_price',
                    'deal_price', 'effective_price', 'payment_status',
                    'payment_type', 'insurance', 'is_home_pickup', 'address', 'outstanding')
        else:
            return ()

    def lab_name(self, obj):
        profile_link = "lab/{}".format(obj.lab.id)
        return mark_safe('{name} (<a href="{consumer_app_domain}/{profile_link}">Profile</a>)'.format(
            name=obj.lab.name,
            consumer_app_domain=settings.CONSUMER_APP_DOMAIN,
            profile_link=profile_link))

    def employees_details(self, obj):
        employees = obj.lab.labmanager_set.all()
        details = ''
        for employee in employees:
            details += 'Name : {name}<br>Phone number : {number}<br>Email : {email}<br>Type : {type}<br><br>'.format(
                name=employee.name, number=employee.number, email=employee.email,
                type=dict(LabManager.CONTACT_TYPE_CHOICES)[employee.contact_type])
            # ' , '.join([str(employee.name), str(employee.number), str(employee.email), str(employee.details)])
            # details += '\n'
        return mark_safe('<p>{details}</p>'.format(details=details))

    def get_lab_test(self, obj):
        format_string = ""
        for data in obj.lab_test.all():
            format_string += "<div><span>{}</span></div>".format(data.test.name)
        return format_html_join(
            mark_safe('<br/>'),
            format_string,
            ((),),
        )
    get_lab_test.short_description = 'Lab Test'

    def used_profile_name(self, obj):
        return obj.profile.name

    def used_profile_number(self, obj):
        return obj.profile.phone_number

    def default_profile_name(self, obj):
        # return obj.profile.user.profiles.all()[:1][0].name
        default_profile = obj.profile.user.profiles.filter(is_default_user=True)
        if default_profile.exists():
            return default_profile.first().name
        else:
            return ''

    def default_profile_number(self, obj):
        # return obj.profile.user.profiles.all()[:1][0].phone_number
        default_profile = obj.profile.user.profiles.filter(is_default_user=True)
        if default_profile.exists():
            return default_profile.first().phone_number
        else:
            return ''

    def user_number(self, obj):
        return obj.user.phone_number

    def save_model(self, request, obj, form, change):
        if obj:
            # date = datetime.datetime.strptime(request.POST['start_date'], '%Y-%m-%d')
            # time = datetime.datetime.strptime(request.POST['start_time'], '%H:%M').time()
            #
            # date_time = datetime.datetime.combine(date, time)
            if request.POST['start_date'] and request.POST['start_time']:
                date_time_field = request.POST['start_date'] + " " + request.POST['start_time']
                to_zone = tz.gettz(settings.TIME_ZONE)
                dt_field = parse_datetime(date_time_field).replace(tzinfo=to_zone)

                if dt_field:
                    obj.time_slot_start = dt_field
        super().save_model(request, obj, form, change)



class LabTestAdmin(ImportExportMixin, VersionAdmin):
    change_list_template = 'superuser_import_export.html'
    formats = (base_formats.XLS, base_formats.XLSX,)
    search_fields = ['name']
    resource_class = LabTestResource


class LabTestTypeAdmin(VersionAdmin):
    search_fields = ['name']


# class LabSubTestTypeAdmin(VersionAdmin):
#     search_fields = ['name']


class AvailableLabTestAdmin(VersionAdmin):
    list_display = ['test', 'lab_pricing_group', 'get_type', 'mrp', 'computed_agreed_price',
                    'custom_agreed_price', 'computed_deal_price', 'custom_deal_price', 'enabled']
    search_fields = ['test__name', 'lab_pricing_group__group_name', 'lab_pricing_group__labs__name']


class DiagnosticConditionLabTestInline(admin.TabularInline):
    model = DiagnosticConditionLabTest
    extra = 0
    can_delete = True
    show_change_link = False
    autocomplete_fields = ['lab_test']


class CommonDiagnosticConditionAdmin(VersionAdmin):
    search_fields = ['name']
    inlines = [DiagnosticConditionLabTestInline]


class CommonTestAdmin(VersionAdmin):
    autocomplete_fields = ['test']

