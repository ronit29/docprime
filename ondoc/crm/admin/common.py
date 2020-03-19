import re

from dal import autocomplete
from django.db import transaction
from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.gis import admin
import datetime
from django.utils import timezone
from django.contrib.gis import forms
from django.core.exceptions import ObjectDoesNotExist
from import_export.tmp_storages import MediaStorage
from reversion_compare.admin import CompareVersionAdmin

from ondoc.crm.constants import constants
from dateutil import tz
from django.conf import settings
from django.utils.dateparse import parse_datetime
from ondoc.authentication.models import Merchant, AssociatedMerchant, QCModel
from ondoc.account.models import MerchantPayout, MerchantPayoutBulkProcess, PayoutMapping
from ondoc.common.models import Cities, MatrixCityMapping, PaymentOptions, Remark, MatrixMappedCity, MatrixMappedState, \
    GlobalNonBookable, UserConfig, BlacklistUser, BlockedStates, Fraud, SearchCriteria, GoogleLatLong
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats, ImportExportMixin, ImportExportModelAdmin, ExportMixin
from reversion.admin import VersionAdmin
import nested_admin
from django.urls import reverse
from django.utils.safestring import mark_safe
from django.contrib.contenttypes.models import ContentType
from import_export.admin import ImportExportMixin

from ondoc.diagnostic.models import Lab, LabAppointment, LabPricingGroup
from ondoc.doctor.models import Hospital, Doctor, OpdAppointment, HospitalNetwork
from ondoc.insurance.models import UserInsurance
from django.db.models import Q
from django import forms


class MediaImportMixin(ImportExportModelAdmin):
    from import_export.tmp_storages import MediaStorage
    tmp_storage_class = MediaStorage


def practicing_since_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-80,-1)]

def hospital_operational_since_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-100,-1)]

def college_passing_year_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-80,-1)]

def award_year_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-80,-1)]


def award_year_choices_no_blank():
    return [(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-60,-1)]


def datetime_from_date_and_time(date, time):
    '''
    Converts the date and time to datetime with timezone's information.

       :param date: The date
       :param time: The time
       :return: The date and time
       :rtype: datetime
       '''
    date_time_field = str(date) + " " + str(time)
    to_zone = tz.gettz(settings.TIME_ZONE)
    dt_field = parse_datetime(date_time_field).replace(tzinfo=to_zone)
    return dt_field


class QCPemAdmin(admin.ModelAdmin):
    change_form_template = 'custom_change_form.html'
    def list_created_by(self, obj):
        field =  ''
        if obj.created_by is not None:
            try:
                field = obj.created_by.staffprofile.name
            except ObjectDoesNotExist:
                field = obj.created_by.email if obj.created_by.email is not None else obj.created_by.phone_number
        return field
    list_created_by.admin_order_field = 'created_by'
    list_created_by.short_description = "Created By"

    def list_assigned_to(self, obj):
        field = ''
        if obj.assigned_to is not None:
            try:
                field = obj.assigned_to.staffprofile.name
            except ObjectDoesNotExist:
                field = obj.assigned_to.email if obj.assigned_to.email is not None else obj.assigned_to.phone_number
        return field
    list_assigned_to.admin_order_field = 'assigned_to'
    list_assigned_to.short_description = "Assigned To"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        final_qs = qs
        # if request.user.is_superuser or \
        #         request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists() or \
        #         request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists() or \
        #         request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists() or \
        #         request.user.groups.filter(name=constants['DOCTOR_SALES_GROUP']).exists():
        #     final_qs = qs
        # if final_qs:
        final_qs = final_qs.prefetch_related('created_by', 'assigned_to', 'assigned_to__staffprofile',
                                                 'created_by__staffprofile')
        return final_qs

    class Meta:
        abstract = True


class RefundableAppointmentForm(forms.ModelForm):
    refund_payment = forms.BooleanField(required=False)
    refund_reason = forms.CharField(widget=forms.Textarea,required=False)

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        refund_payment = cleaned_data.get('refund_payment')
        refund_reason = cleaned_data.get('refund_reason')
        if refund_payment:
            if not refund_reason:
                raise forms.ValidationError("Refund reason is compulsory")
            if self.instance and not self.instance.status == self.instance.COMPLETED:
                raise forms.ValidationError("Refund can be processed after Completion")
        # TODO : No refund should already be in process
        return cleaned_data


class FormCleanMixin(forms.ModelForm):

    def pin_code_qc_submit(self):
        if '_submit_for_qc' in self.data:
            # if hasattr(self.instance, 'pin_code') and self.instance.pin_code is not None:
            if hasattr(self.instance, 'pin_code'):
                if not self.cleaned_data.get('pin_code'):
                    raise forms.ValidationError("Cannot submit for QC without pincode ")
            # else:
            #     raise forms.ValidationError(
            #             "Cannot submit for QC without pincode ")

    def clean(self):
        self.pin_code_qc_submit()
        phone_no_flag = False
        if isinstance(self.instance, Hospital) and self.data and self.instance.network_type == 1:
            if 'authentication-spocdetails-content_type-object_id-TOTAL_FORMS' in self.data:
                total_forms = int(self.data.get('authentication-spocdetails-content_type-object_id-TOTAL_FORMS', '0'))
                for form in range(total_forms):
                    number_pattern = re.compile("(0/91)?[6-9][0-9]{9}")
                    phone_number = self.data.get('authentication-spocdetails-content_type-object_id-' + str(form) + '-number')
                    if phone_number and number_pattern.match(str(phone_number)):
                        phone_no_flag = True
            else:
                phone_no_flag = True  # Skip check if inline is not present.
            if phone_no_flag == False:
                raise forms.ValidationError("Atleast one mobile no is required for SPOC Details")

        if (not self.request.user.is_superuser and not self.request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists()):
            # and (not '_reopen' in self.data and not self.request.user.groups.filter(name__in=[constants['QC_GROUP_NAME'], constants['WELCOME_CALLING_TEAM']]).exists()):
            if isinstance(self.instance, Hospital) or isinstance(self.instance, HospitalNetwork):
                if self.cleaned_data.get('matrix_city') and hasattr(self.cleaned_data.get('matrix_city'), 'state'):
                    if self.cleaned_data.get('matrix_city').state != self.cleaned_data.get('matrix_state'):
                        raise forms.ValidationError("City does not belong to selected state")
                else:
                    raise forms.ValidationError("There is not state mapped with selected city")
            if self.instance.data_status == QCModel.QC_APPROVED:
                # allow welcome_calling_team to modify qc_approved data
                if not self.request.user.groups.filter(name__in=[constants['WELCOME_CALLING_TEAM'], constants['ARTICLE_TEAM']]).exists():
                    raise forms.ValidationError("Cannot modify QC approved Data")
            if not self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
                if self.instance.data_status == QCModel.SUBMITTED_FOR_QC:
                    raise forms.ValidationError("Cannot update Data submitted for QC approval")
                # if not self.request.user.groups.filter(name=constants['DOCTOR_SALES_GROUP']).exists():
                #     if self.instance.data_status in [QCModel.IN_PROGRESS] and self.instance.created_by and self.instance.created_by.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists() and self.instance.created_by != self.request.user:
                #         raise forms.ValidationError("Cannot modify Data added by other users")
            if '_submit_for_qc' in self.data:
                self.validate_qc()
                # if hasattr(self.instance, 'doctor_clinics') and self.instance.doctor_clinics is not None:
                #     for h in self.instance.doctor_clinics.all():
                #         if (h.hospital.data_status < 2):
                #             raise forms.ValidationError(
                #                 "Cannot submit for QC without submitting associated Hospitals: " + h.hospital.name)
                if hasattr(self.instance, 'network') and self.instance.network is not None:
                    if self.instance.network.data_status in [QCModel.IN_PROGRESS, QCModel.REOPENED]:
                        class_name = self.instance.network.__class__.__name__
                        raise forms.ValidationError(
                            "Cannot submit for QC without submitting associated " + class_name.rstrip(
                                'Form') + ": " + self.instance.network.name)
                if hasattr(self.instance, 'mobiles'):
                    mobile_error = True
                    mobile_count = int(self.data.get('mobiles-TOTAL_FORMS', 0))
                    for count in range(mobile_count):
                        if self.data.get('mobiles-' + str(count) + '-DELETE'):
                            continue
                        mobile_error = False if self.data.get('mobiles-' + str(count) + '-is_primary') else True
                        if not mobile_error:
                            break
                    if mobile_error:
                        raise forms.ValidationError("Doctor must have atleast and atmost one primary mobile number.")

            if '_qc_approve' in self.data:
                self.validate_qc()
                # if hasattr(self.instance, 'doctor_clinics') and self.instance.doctor_clinics is not None:
                #     for h in self.instance.doctor_clinics.all():
                #         if (h.hospital.data_status < 3):
                #             raise forms.ValidationError(
                #                 "Cannot approve QC check without approving associated Hospitals: " + h.hospital.name)
                if hasattr(self.instance, 'network') and self.instance.network is not None:
                    if self.instance.network.data_status in [QCModel.IN_PROGRESS, QCModel.REOPENED, QCModel.SUBMITTED_FOR_QC]:
                        class_name = self.instance.network.__class__.__name__
                        raise forms.ValidationError(
                            "Cannot approve QC check without approving associated" + class_name.rstrip(
                                'Form') + ": " + self.instance.network.name)

            if '_mark_in_progress' in self.data:
                if self.data.get('common-remark-content_type-object_id-INITIAL_FORMS', 0) == self.data.get(
                        'common-remark-content_type-object_id-TOTAL_FORMS', 1):
                    raise forms.ValidationError("Must add a remark with reopen status before rejecting.")
                else:
                    last_remark_id = int(self.data.get('common-remark-content_type-object_id-TOTAL_FORMS', 1)) - 1
                    last_remark_status = "common-remark-content_type-object_id-" + str(last_remark_id) + "-status"
                    if self.data.get(last_remark_status) != str(Remark.REOPEN):
                        raise forms.ValidationError("Must add a remark with reopen status before rejecting.")
                if self.instance.data_status == QCModel.QC_APPROVED:
                    if not self.request.user.groups.filter(name=constants['WELCOME_CALLING_TEAM']).exists():
                        raise forms.ValidationError("Cannot reject QC approved data")
            return super().clean()


class ActionAdmin(admin.ModelAdmin):

    # actions = ['submit_for_qc','qc_approve', 'mark_in_progress']


    def get_actions(self, request):
        actions = super().get_actions(request)
        if request.user.is_superuser and request.user.is_staff:
            return actions

        if 'delete_selected' in actions:
            del actions['delete_selected']

        # # check if member of QC Team
        # if request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
        #     if 'submit_for_qc' in actions:
        #         del actions['submit_for_qc']
        #     return actions

        # # if field team member
        # if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
        #     if 'qc_approve' in actions:
        #         del actions['qc_approve']
        #     if 'mark_in_progress' in actions:
        #         del actions['mark_in_progress']
        #     return actions

        return actions

    # def mark_in_progress(self, request, queryset):
    #     rows_updated = queryset.filter(data_status=2).update(data_status=1)
    #     if rows_updated == 1:
    #         message_bit = "1 record was "
    #     else:
    #         message_bit = "%s records were" % rows_updated
    #     self.message_user(request, "%s sent back for information collection." % message_bit)

    # mark_in_progress.short_description = "Send back for information collection";


    # def submit_for_qc(self, request, queryset):

    #     rows_updated = 0
    #     for e in queryset.filter(data_status=2).all():
    #         e.data_status=2
    #         e.save()
    #         rows_updated += 1


    #     #rows_updated = queryset.filter(data_status=1).update(data_status=2)
    #     if rows_updated == 1:
    #         message_bit = "1 record was "
    #     else:
    #         message_bit = "%s records were" % rows_updated
    #     self.message_user(request, "%s submitted for Quality Check." % message_bit)

    # submit_for_qc.short_description = "Submit for Quality Check";


    # def qc_approve(self, request, queryset):
    #     rows_updated = queryset.filter(data_status=2).update(data_status=3)
    #     if rows_updated == 1:
    #         message_bit = "1 record was "
    #     else:
    #         message_bit = "%s records were" % rows_updated
    #     self.message_user(request, "%s approved Quality Check." % message_bit)

    # qc_approve.short_description = "Approve Quality Check";

    class Meta:
        abstract = True


class CitiesResource(resources.ModelResource):
    name = fields.Field(attribute='name', column_name='City')

    class Meta:
        model = Cities
        import_id_fields = ('id',)

    def before_save_instance(self, instance, using_transactions, dry_run):
        super().before_save_instance(instance, using_transactions, dry_run)


class CitiesAdmin(ImportMixin, admin.ModelAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name',)
    resource_class = CitiesResource


class MatrixCityResource(resources.ModelResource):
    city_id = fields.Field(attribute='city_id', column_name='id')
    name = fields.Field(attribute='name', column_name='City')

    class Meta:
        model = MatrixCityMapping
        import_id_fields = ('id',)

    def before_save_instance(self, instance, using_transactions, dry_run):
        super().before_save_instance(instance, using_transactions, dry_run)


class MatrixCityAdmin(ImportMixin, admin.ModelAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name',)
    resource_class = MatrixCityResource


class GenericAdminForm(forms.ModelForm):
    class Meta:
        widgets = {'name': forms.TextInput(attrs={'size': 13}),
                   'phone_number': forms.NumberInput(attrs={'size': 8})}


class MerchantResource(resources.ModelResource):
    class Meta:
        model = Merchant
        fields = ('id', 'beneficiary_name', 'merchant_add_1', 'merchant_add_2', 'merchant_add_3', 'merchant_add_4',
                  'city', 'pin', 'state', 'country', 'email', 'mobile', 'ifsc_code', 'account_number', 'enabled',
                  'verified_by_finance','type')

class MerchantForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        # state = self.cleaned_data.get('state', None)
        # abbr = None
        # if state:
        #     abbr = Merchant.get_abbreviation(state)
        # if state and not abbr:
        #     raise forms.ValidationError("No abbreviation for the state. Allowed states are " + Merchant.get_states_string())
        return self.cleaned_data


class MerchantAdmin(ImportExportMixin, VersionAdmin):
    resource_class = MerchantResource
    change_list_template = 'export_template.html'
    list_display = ('beneficiary_name', 'account_number', 'ifsc_code', 'enabled', 'verified_by_finance')
    search_fields = ['beneficiary_name', 'account_number']
    list_filter = ('enabled', 'verified_by_finance')
    form = MerchantForm


    def associated_to(self, instance):
        if instance and instance.id:
            asso_qs = AssociatedMerchant.objects.select_related('content_type').filter(merchant=instance)
            all_links = []
            for asso in asso_qs:
                content_type = asso.content_type
                change_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model),
                                     args=[asso.object_id])
                html = '''<a href='%s' target=_blank>%s</a><br>''' % (
                    change_url, asso.content_object.name if asso.content_object.name else change_url)
                all_links.append(html)
            return mark_safe(''.join(all_links))
        return None

    def get_readonly_fields(self, request, obj=None):
        if request.user.is_member_of(constants['MERCHANT_TEAM']):
            if obj and obj.verified_by:
                return [f.name for f in self.model._meta.fields if
                        f.name not in ['enabled', 'verified_by_finance', 'associated_to', 'enable_for_tds_deduction']]
            return []

        if obj and obj.verified_by:
            return [f.name for f in self.model._meta.fields if f.name not in ['enable_for_tds_deduction']] + ['associated_to']

        return ['verified_by_finance', 'associated_to']

    def save_model(self, request, obj, form, change):
        if form.cleaned_data.get('verified_by_finance') and not obj.verified_by:
            obj.verified_by = request.user
            obj.verified_at = timezone.now()
        super().save_model(request, obj, form, change)


class MerchantPayoutForm(forms.ModelForm):
    process_payout = forms.BooleanField(required=False)
    recreate_payout = forms.BooleanField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        payment_mode_options = []
        instance = self.instance
        merchant = instance.get_merchant()
        if merchant and merchant.ifsc_code and self.fields.get('payment_mode'):
            ifsc_code = merchant.ifsc_code
            if ifsc_code.upper().startswith(MerchantPayout.INTRABANK_IDENTIFIER):
                payment_mode_options = [(MerchantPayout.IFT,MerchantPayout.IFT)]
            else:
                payment_mode_options = [(MerchantPayout.NEFT, MerchantPayout.NEFT),
                                        (MerchantPayout.IMPS, MerchantPayout.IMPS)]
            self.fields.get('payment_mode').choices = payment_mode_options

    def clean(self):
        super().clean()
        if any(self.errors):
            return

        request = self.request
        user_groups = request.user.groups.values_list('name', flat=True)
        if 'qc_merchant_team' in user_groups and 'merchant_team' not in user_groups:
            raise forms.ValidationError("You are not authorized to perform this action.")
        else:
            if self.cleaned_data.get('type', None) == MerchantPayout.MANUAL and not self.cleaned_data.get('utr_no', None):
                raise forms.ValidationError("Enter UTR Number if payout type is manual.")
            if not self.cleaned_data.get('type', None) == MerchantPayout.MANUAL and (self.cleaned_data.get('utr_no', None) or self.cleaned_data.get('amount_paid', None)):
                raise forms.ValidationError("No need for UTR Number/Amount Paid if payout type is not manual.")

            process_payout = self.cleaned_data.get('process_payout')
            if process_payout:
                if not self.instance.get_merchant():
                    raise forms.ValidationError("No verified merchant found to process payments")

                merchant = self.instance.get_merchant()
                if not merchant.verified_by_finance or not merchant.enabled:
                    raise forms.ValidationError("Merchant is not verified or is not enabled.")

                billed_to = self.instance.get_billed_to()
                if not billed_to:
                    raise forms.ValidationError("Billing entity not defined.")

                if not self.instance.booking_type == self.instance.InsurancePremium:
                    if self.payout_type == 1:
                        associated_merchant = billed_to.merchant.first()
                        if not associated_merchant:
                            self.instance.update_billed_to_content_type()
                        if associated_merchant and not associated_merchant.verified:
                            raise forms.ValidationError("Associated Merchant not verified.")

                if self.instance.status not in [1, 2]:
                    raise forms.ValidationError("Only pending and attempted payouts can be processed.")

            recreate_payout = self.cleaned_data.get('recreate_payout')
            if recreate_payout:
                if self.instance.status not in [6, 7] and not self.instance.merchant_has_advance_payment():
                    raise forms.ValidationError("Only failed or advance paid payout can be re-created.")

            if self.instance.status in [3, 4, 5]:
                raise forms.ValidationError("This payout is already under process or completed.")

            return self.cleaned_data


class MerchantPayoutResource(resources.ModelResource):
    appointment_id = fields.Field()
    merchant = fields.Field()
    verified_by_finance = fields.Field()

    def export(self, queryset=None, *args, **kwargs):
        queryset = self.get_queryset(**kwargs)
        fetched_queryset = list(queryset)
        return super().export(fetched_queryset)

    def get_queryset(self, **kwargs):
        date_range = [datetime.datetime.strptime(kwargs.get('from_date'), '%Y-%m-%d').date(), datetime.datetime.strptime(
                                        kwargs.get('to_date'), '%Y-%m-%d').date()]
        payout_status = kwargs.get('payout_status')
        booking_type = kwargs.get('booking_type')
        payout_type = kwargs.get('payout_type')

        payouts = MerchantPayout.objects.filter(created_at__date__range=date_range)
        if payout_status:
            if [str(x[0]) for x in MerchantPayout.STATUS_CHOICES]:
                payouts = payouts.filter(status=payout_status)

        if booking_type:
            if [str(x[0]) for x in MerchantPayout.BookingTypeChoices]:
                payouts = payouts.filter(booking_type=booking_type)

        if payout_type:
            if [str(x[0]) for x in MerchantPayout.PAYOUT_TYPE_CHOICES]:
                payouts = payouts.filter(payout_type=payout_type)

        payouts = payouts.order_by('-updated_at')
        return payouts

    def dehydrate_appointment_id(self, merchant_payout):
        appt = merchant_payout.get_appointment()
        if appt:
            return appt.id

        return ''

    def dehydrate_status(self, merchant_payout):
        return dict(MerchantPayout.STATUS_CHOICES)[merchant_payout.status]

    def dehydrate_booking_type(self, merchant_payout):
        if merchant_payout.booking_type:
            return dict(MerchantPayout.BookingTypeChoices)[merchant_payout.booking_type]

        return ''

    def dehydrate_merchant(self, merchant_payout):
        if merchant_payout.paid_to:
            merchant = Merchant.objects.filter(id=merchant_payout.paid_to_id).first()
            if merchant:
                return "{}-{}".format(merchant.beneficiary_name, merchant.id)

        return ''

    def dehydrate_verified_by_finance(self, merchant_payout):
        if merchant_payout.paid_to:
            merchant = Merchant.objects.filter(id=merchant_payout.paid_to_id).first()
            if merchant and merchant.verified_by_finance:
                return 1

        return 0

    def dehydrate_api_response(self, merchant_payout):
        if merchant_payout.api_response and merchant_payout.api_response.get('result', []):
            result = merchant_payout.api_response.get('result')[0]
            if result.get('responseError', ''):
                return result.get('responseError').get('errorMsg')

        return ''

    class Meta:
        model = MerchantPayout
        fields = ('id', 'payment_mode', 'payout_ref_id', 'charged_amount', 'payable_amount', 'payout_approved',
                  'status', 'payout_time', 'paid_to', 'utr_no', 'type', 'amount_paid',
                  'content_type', 'object_id', 'appointment_id', 'booking_type', 'merchant', 'verified_by_finance', 'api_response')

        export_order = ('appointment_id', 'booking_type', 'id', 'payment_mode', 'payout_ref_id', 'charged_amount', 'payable_amount', 'payout_approved',
                  'status', 'payout_time', 'merchant', 'paid_to', 'verified_by_finance', 'utr_no', 'type', 'amount_paid', 'content_type', 'object_id', 'api_response')


class MerchantPayoutAdmin(MediaImportMixin, VersionAdmin):
    export_template_name = "export_merchant_payout.html"
    resource_class = MerchantPayoutResource
    formats = (base_formats.XLS,)
    form = MerchantPayoutForm
    model = MerchantPayout
    fields = ['id','booking_type', 'payment_mode','charged_amount', 'updated_at', 'created_at', 'payable_amount', 'tds_amount', 'status', 'payout_time', 'paid_to',
              'appointment_id', 'get_billed_to', 'get_merchant', 'process_payout', 'type', 'utr_no', 'amount_paid','api_response','pg_status','status_api_response', 'duplicate_of', 'recreate_payout', 'remarks']
    list_display = ('id', 'status', 'payable_amount', 'appointment_id', 'doc_lab_name', 'booking_type')
    search_fields = ['name', 'id', 'appointment_id']
    list_filter = ['status', 'booking_type', 'payout_type']

    class Media:
        js = ('js/admin/ondoc.js',)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(payable_amount__gt=0).order_by('-id').prefetch_related('lab_appointment__lab',
                                                                                                           'opd_appointment__doctor', 'user_insurance')

    def get_search_results(self, request, queryset, search_term):
        queryset, use_distinct = super().get_search_results(request, queryset, None)
        if search_term:
            queryset = queryset.filter(Q(opd_appointment__doctor__name__icontains=search_term) |
                                       Q(lab_appointment__lab__name__icontains=search_term) |
                                       Q(id__icontains=search_term) | Q(lab_appointment__id__icontains=search_term) |
                                       Q(opd_appointment__id__icontains=search_term))

        return queryset, use_distinct

    def get_readonly_fields(self, request, obj=None):
        user_groups = request.user.groups.values_list('name', flat=True)
        if 'qc_merchant_team' in user_groups and 'merchant_team' not in user_groups:
            return ['id', 'booking_type', 'payment_mode', 'charged_amount', 'updated_at', 'created_at',
                    'payable_amount', 'tds_amount', 'status', 'payout_time', 'paid_to',
                    'appointment_id', 'get_billed_to', 'get_merchant', 'type', 'utr_no',
                    'amount_paid', 'api_response', 'pg_status', 'status_api_response', 'duplicate_of',
                    'remarks']
        else:
            base = ['appointment_id', 'get_billed_to', 'get_merchant', 'booking_type', 'duplicate_of']
            editable_fields = ['payout_approved']
            if obj and obj.status == MerchantPayout.PENDING:
                editable_fields += ['type', 'amount_paid', 'payment_mode']
            if not obj or not obj.utr_no:
                editable_fields += ['utr_no', 'remarks']

            readonly = [f.name for f in self.model._meta.fields if f.name not in editable_fields]
            return base + readonly

    def save_model(self, request, obj, form, change):
        obj.process_payout = form.cleaned_data.get('process_payout')

        if form.cleaned_data.get('recreate_payout', False):
            obj.recreate_failed_payouts()
            obj.status = obj.ARCHIVE

        super().save_model(request, obj, form, change)

    def doc_lab_name(self, instance):
        appt = instance.get_appointment()
        if isinstance(appt, OpdAppointment):
            if appt.doctor:
                return appt.doctor.name
        elif isinstance(appt, LabAppointment):
            if appt.lab:
                return appt.lab.name
        elif isinstance(appt, UserInsurance):
            if appt.insurance_plan.insurer:
                return appt.insurance_plan.insurer.name

        return ''

    def appointment_id(self, instance):
        if instance.booking_type == 3:
            pm = PayoutMapping.objects.filter(payout_id=instance.id).first()
            if pm:
                ui = UserInsurance.objects.filter(id=pm.object_id).first()
                if ui:
                    content_type = ContentType.objects.get_for_model(ui.__class__)
                    change_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model),
                                     args=[ui.id])
                    html = '''<a href='%s' target=_blank>%s</a>''' % (change_url, ui.id)
                    return mark_safe(html)

            return None
        else:
            appt = instance.get_appointment()
            if appt:
                content_type = ContentType.objects.get_for_model(appt.__class__)
                change_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=[appt.id])
                html = '''<a href='%s' target=_blank>%s</a>''' % (change_url, appt.id)
                return mark_safe(html)

            return None

    def get_billed_to(self, instance):
        billed_to = instance.get_billed_to()
        if billed_to:
            content_type = ContentType.objects.get_for_model(billed_to.__class__)
            change_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=[billed_to.id])
            html = '''<a href='%s' target=_blank>%s</a>''' % (change_url, billed_to.name)
            return mark_safe(html)

        return ''

    def get_merchant(self, instance):
        merchant = instance.get_merchant()
        if merchant:
            content_type = ContentType.objects.get_for_model(merchant.__class__)
            change_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=[merchant.id])
            html = '''<a href='%s' target=_blank>%s</a>''' % (change_url, merchant.id)
            return mark_safe(html)

        return ''

    def duplicate_of(self, instance):
        if instance.recreated_from_id:
            content_type = ContentType.objects.get_for_model(instance.__class__)
            change_url = reverse('admin:%s_%s_change' % (content_type.app_label, content_type.model), args=[instance.recreated_from_id])
            html = '''<a href='%s' target=_blank>%s</a>''' % (change_url, instance.recreated_from_id)
            return mark_safe(html)

        return ''

    def get_export_data(self, file_format, queryset, *args, **kwargs):
        """
        Returns file_format representation for given queryset.
        """
        kwargs['from_date'] = kwargs.get('request').POST.get('from_date')
        kwargs['to_date'] = kwargs.get('request').POST.get('to_date')
        kwargs['payout_status'] = kwargs.get('request').POST.get('payout_status')
        kwargs['booking_type'] = kwargs.get('request').POST.get('booking_type')
        kwargs['payout_type'] = kwargs.get('request').POST.get('payout_type')
        resource_class = self.get_export_resource_class()
        data = resource_class(**self.get_export_resource_kwargs(kwargs.get('request'))).export(queryset, *args,
                                                                                               **kwargs)
        export_data = file_format.export_data(data)
        return export_data
        # return super().get_export_data(file_format, queryset, *args, **kwargs)

    def get_form(self, request, obj=None, **kwargs):
        kwargs['form'] = MerchantPayoutForm
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        return form


class AssociatedMerchantInline(GenericTabularInline, nested_admin.NestedTabularInline):
    can_delete = False
    extra = 0
    model = AssociatedMerchant
    show_change_link = False
    autocomplete_fields = ['merchant', ]

    #fields = "__all__"
    #readonly_fields = ['merchant_id']
    #fields = ['merchant_id', 'type', 'account_number', 'ifsc_code', 'pan_number', 'pan_copy', 'account_copy', 'enabled']


class PaymentOptionsAdmin(admin.ModelAdmin):
    model = PaymentOptions
    list_display = ['name', 'description', 'is_enabled']
    search_fields = ['name']


class GlobalNonBookableAdmin(admin.ModelAdmin):
    model = GlobalNonBookable
    list_display = ['booking_type', 'start_date', 'end_date', 'start_time', 'end_time']


class RemarkInlineForm(forms.ModelForm):
    # content = forms.CharField(widget=forms.Textarea, required=False)
    # print(content)

    # class Meta:
    #     model = Remark
    #     fields = ('__all__')

    # def __init__(self, *args, **kwargs):
    #     a=5
    #     super(RemarkInlineForm, self).__init__(*args, **kwargs)
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        if self.instance and self.instance.id:
            if self.changed_data:
                raise forms.ValidationError("Cannot alter already saved remarks.")


class RemarkInline(GenericTabularInline, nested_admin.NestedTabularInline):
    can_delete = True
    extra = 0
    model = Remark
    show_change_link = False
    readonly_fields = ['user', 'created_at']
    fields = ['status', 'user', 'content', 'created_at']
    form = RemarkInlineForm
    # formset = RemarkInlineFormSet

    # def get_readonly_fields(self, request, obj=None):
    #     print(self)
    #     editable_fields = ['user']
    #     if obj:
    #         editable_fields += ['content']
    #     return editable_fields


class MatrixMappedStateResource(resources.ModelResource):
    id = fields.Field(attribute='id', column_name='StateId')
    name = fields.Field(attribute='name', column_name='State')

    class Meta:
        model = MatrixMappedState


class MatrixMappedStateAdmin(ImportMixin, admin.ModelAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name',)
    readonly_fields = ('name',)
    search_fields = ['name']
    resource_class = MatrixMappedStateResource

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser and not request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists():
            return super().get_readonly_fields(request, obj)
        return ()


class MatrixMappedCityResource(resources.ModelResource):
    id = fields.Field(attribute='id', column_name='CityID')
    state_id = fields.Field(attribute='state_id', column_name='StateId')
    name = fields.Field(attribute='name', column_name='City')

    class Meta:
        model = MatrixMappedCity
        fields = ('id', 'name', 'state_id')


class MatrixMappedCityAdminForm(forms.ModelForm):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        state = cleaned_data.get('state', None)
        city_name = cleaned_data.get('name', '')
        if not state:
            raise forms.ValidationError("State is required.")
        if state and city_name:
            if MatrixMappedCity.objects.filter(name__iexact=city_name.strip(), state=state).exists():
                raise forms.ValidationError("City-State combination already exists.")


class MatrixMappedCityAdmin(ImportMixin, admin.ModelAdmin):
    form = MatrixMappedCityAdminForm
    formats = (base_formats.XLS, base_formats.XLSX,)
    list_display = ('name', 'state')
    readonly_fields = ('name', 'state', )
    search_fields = ['name']
    resource_class = MatrixMappedCityResource

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        qs = qs.select_related('state')
        return qs

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser and not request.user.groups.filter(name=constants['SUPER_QC_GROUP']).exists():
            return super().get_readonly_fields(request, obj)
        return ()


class MatrixStateAutocomplete(autocomplete.Select2QuerySetView):

        def get_queryset(self):
            queryset = MatrixMappedState.objects.all()

            if self.q:
                queryset = queryset.filter(name__istartswith=self.q)

            return queryset


class MatrixCityAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        queryset = MatrixMappedCity.objects.none()
        matrix_state = self.forwarded.get('matrix_state', None)

        if matrix_state:
            queryset = MatrixMappedCity.objects.filter(state_id=matrix_state)
        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)

        return queryset


class RelatedHospitalAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        queryset = Hospital.objects.filter(is_ipd_hospital=True)

        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)

        return queryset


class ContactUsAdmin(admin.ModelAdmin):
    list_display = ('name', 'mobile', 'email', 'from_app')
    fields = ('name', 'mobile', 'email', 'message', 'from_app')
    readonly_fields = ('name', 'mobile', 'email', 'message', 'from_app')
    list_filter = ("from_app",)


class UserConfigAdmin(admin.ModelAdmin):
    model = UserConfig
    list_display = ('key',)


class LabPricingAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        queryset = LabPricingGroup.objects.all()

        if self.q:
            queryset = queryset.filter(group_name__istartswith=self.q)

        return queryset


class BlacklistUserForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super(BlacklistUserForm, self).__init__(*args, **kwargs)
        if self.instance and self.instance.id and self.instance.user:
            self.fields['phone_number'].initial = self.instance.user.phone_number

    phone_number = forms.CharField(required=True)

    def clean(self):
        super().clean()
        cleaned_data = self.cleaned_data
        from ondoc.authentication.models import User
        phone_number = cleaned_data['phone_number']
        user = User.objects.filter(user_type=User.CONSUMER, phone_number=phone_number).first()
        if user:
            if cleaned_data.get('type') and BlacklistUser.get_state_by_number(user.phone_number, cleaned_data.get('type')):
                raise forms.ValidationError('User with given block state already exists.')

            self.instance.user = user
        else:
            raise forms.ValidationError('User with given number does not exists.')

        return cleaned_data


class BlacklistUserAdmin(VersionAdmin):
    model = BlacklistUser
    form = BlacklistUserForm
    list_display = ('user', 'type')
    fields = ('phone_number', 'type', 'reason', 'enabled')
    # autocomplete_fields = ['user']

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        responsible_user = request.user
        obj.blocked_by = responsible_user if responsible_user and not responsible_user.is_anonymous else None

        super().save_model(request, obj, form, change)


class BlockedStatesAdmin(VersionAdmin):
    model = BlockedStates
    list_display = ('state_name', 'message')
    fields = ('state_name', 'message')


class FraudForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        instance = getattr(self, 'instance', None)
        if instance and instance.pk:
            if instance.reason:
                self.fields['reason'].widget.attrs['readonly'] = True


class FraudInline(GenericTabularInline, nested_admin.NestedGenericTabularInline):
    can_delete = False
    form = FraudForm
    extra = 0
    model = Fraud
    show_change_link = False
    fields = ['reason', 'user', 'created_at']
    editable = False
    readonly_fields = ['created_at', 'user']


class MerchantPayoutBulkProcessAdmin(admin.ModelAdmin):
    model = MerchantPayoutBulkProcess
    list_display = ('id',)

    class Media:
        js = ('js/admin/ondoc.js',)

    def get_readonly_fields(self, request, obj=None):
        if obj:  # editing an existing object
            return self.readonly_fields + ('payout_ids',)
        return self.readonly_fields


class AdvanceMerchantPayoutAdmin(admin.ModelAdmin):
    fields = ['id', 'booking_type', 'charged_amount', 'payable_amount', 'tds_amount', 'status',  'paid_to', 'type', 'utr_no']
    list_display = ('id', 'status', 'payable_amount', 'booking_type')
    search_fields = ['id']
    list_filter = ['status', 'booking_type']
    readonly_fields = ('id', 'booking_type', 'charged_amount', 'payable_amount', 'tds_amount', 'status',  'paid_to', 'type', 'utr_no')


class AdvanceMerchantAmountAdmin(admin.ModelAdmin):
    fields = ['id', 'total_amount', 'amount', 'merchant_id']
    list_display = ('id', 'total_amount', 'amount', 'merchant_id')
    readonly_fields = ['id', 'total_amount', 'amount', 'merchant_id']


class SearchCriteriaAdmin(CompareVersionAdmin):
    model = SearchCriteria
    list_display = ('id', 'search_key', 'search_value')
    fields = ('search_key', 'search_value')


class GoogleLatLongAdminResource(resources.ModelResource):
    tmp_storage_class = MediaStorage

    class Meta:
        model = GoogleLatLong
        fields = ('id', 'latitude', 'longitude', 'coordinates')
        export_order = ('id', 'latitude', 'longitude', 'coordinates')


class GoogleLatLongAdmin(ImportExportMixin, CompareVersionAdmin):
    list_display = ['latitude', 'longitude', 'coordinates']
    formats = (base_formats.XLS, base_formats.XLSX,)
    resource_class = GoogleLatLongAdminResource
