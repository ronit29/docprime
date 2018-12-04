from django.contrib.contenttypes.admin import GenericTabularInline
from django.contrib.gis import admin
import datetime
from django.contrib.gis import forms
from django.core.exceptions import ObjectDoesNotExist
from ondoc.crm.constants import constants
from dateutil import tz
from django.conf import settings
from django.utils.dateparse import parse_datetime
from ondoc.authentication.models import Merchant, AssociatedMerchant
from ondoc.account.models import MerchantPayout
from ondoc.common.models import Cities, MatrixCityMapping
from import_export import resources, fields
from import_export.admin import ImportMixin, base_formats, ImportExportMixin
from reversion.admin import VersionAdmin
import nested_admin

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


class FormCleanMixin(forms.ModelForm):
    def clean(self):
        if not self.request.user.is_superuser and not self.request.user.groups.filter(
                name=constants['SUPER_QC_GROUP']).exists():
            if self.instance.data_status == 3:
                raise forms.ValidationError("Cannot modify QC approved Data")
            if not self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
                if self.instance.data_status == 2:
                    raise forms.ValidationError("Cannot update Data submitted for QC approval")
                if not self.request.user.groups.filter(name=constants['DOCTOR_SALES_GROUP']).exists():
                    if self.instance.data_status == 1 and self.instance.created_by and self.instance.created_by != self.request.user:
                        raise forms.ValidationError("Cannot modify Data added by other users")
            if '_submit_for_qc' in self.data:
                self.validate_qc()
                # if hasattr(self.instance, 'doctor_clinics') and self.instance.doctor_clinics is not None:
                #     for h in self.instance.doctor_clinics.all():
                #         if (h.hospital.data_status < 2):
                #             raise forms.ValidationError(
                #                 "Cannot submit for QC without submitting associated Hospitals: " + h.hospital.name)
                if hasattr(self.instance, 'network') and self.instance.network is not None:
                    if self.instance.network.data_status < 2:
                        class_name = self.instance.network.__class__.__name__
                        raise forms.ValidationError(
                            "Cannot submit for QC without submitting associated " + class_name.rstrip(
                                'Form') + ": " + self.instance.network.name)
                if hasattr(self.instance, 'mobiles') and not self.instance.mobiles.filter(is_primary=True).count() == 1:
                    raise forms.ValidationError("Doctor must have atleast and atmost one primary mobile number.")
            if '_qc_approve' in self.data:
                self.validate_qc()
                # if hasattr(self.instance, 'doctor_clinics') and self.instance.doctor_clinics is not None:
                #     for h in self.instance.doctor_clinics.all():
                #         if (h.hospital.data_status < 3):
                #             raise forms.ValidationError(
                #                 "Cannot approve QC check without approving associated Hospitals: " + h.hospital.name)
                if hasattr(self.instance, 'network') and self.instance.network is not None:
                    if self.instance.network.data_status < 3:
                        class_name = self.instance.network.__class__.__name__
                        raise forms.ValidationError(
                            "Cannot approve QC check without approving associated" + class_name.rstrip(
                                'Form') + ": " + self.instance.network.name)

            if '_mark_in_progress' in self.data:
                if self.instance.data_status == 3:
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


class MerchantAdmin(VersionAdmin):
    model = Merchant

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [f.name for f in self.model._meta.fields if f.name not in ['enabled','verified_by_finance']]
        return []

class MerchantPayoutAdmin(VersionAdmin):
    model = MerchantPayout
    fields = ['id','charged_amount','updated_at','created_at','payable_amount','status','payout_time','paid_to',
    'appointment_id', 'get_billed_to', 'get_merchant']

    def get_readonly_fields(self, request, obj=None):
        base = ['appointment_id', 'get_billed_to', 'get_merchant']
        readonly = [f.name for f in self.model._meta.fields if f.name not in ['payout_approved']]
        return base + readonly

    def appointment_id(self, instance):
        appt = self.get_appointment(instance)
        if appt:
            return appt.id

        return None

    def get_appointment(self, instance):
        if instance.lab_appointment.first():
            return instance.lab_appointment.first()
        elif instance.opd_appointment.first():
            return instance.opd_appointment.first()
        return None


    def get_billed_to(self, instance):
        appt = self.get_appointment(instance)

        if appt and appt.get_billed_to:
            return appt.get_billed_to
        return ''

    def get_merchant(self, instance):
        appt = self.get_appointment(instance)

        if appt and appt.get_merchant:
            return appt.get_merchant
        return ''


class AssociatedMerchantInline(GenericTabularInline, nested_admin.NestedTabularInline):
    can_delete = False
    extra = 0
    model = AssociatedMerchant
    show_change_link = False
    #fields = "__all__"
    #readonly_fields = ['merchant_id']
    #fields = ['merchant_id', 'type', 'account_number', 'ifsc_code', 'pan_number', 'pan_copy', 'account_copy', 'enabled']
