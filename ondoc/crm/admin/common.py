from django.contrib.gis import admin
import datetime
from django.contrib.gis import forms
from django.core.exceptions import ObjectDoesNotExist
from ondoc.crm.constants import constants

def practicing_since_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-60,-1)]

def hospital_operational_since_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-100,-1)]

def college_passing_year_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-60,-1)]

def award_year_choices():
    return [(None,'---------')]+[(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-60,-1)]


def award_year_choices_no_blank():
    return [(x, str(x)) for x in range(datetime.datetime.now().year,datetime.datetime.now().year-60,-1)]


class QCPemAdmin(admin.ModelAdmin):
    change_form_template = 'custom_change_form.html'
    def list_created_by(self, obj):
        field =  ''
        try:
            field = obj.created_by.staffprofile.name
        except ObjectDoesNotExist:
            field = obj.created_by.email if obj.created_by.email is not None else obj.created_by.phone_number
        return field
    list_created_by.admin_order_field = 'created_by'
    list_created_by.short_description = "Created By"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser or request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
            return qs
        if request.user.groups.filter(name=constants['DOCTOR_NETWORK_GROUP_NAME']).exists():
            return qs.filter(created_by=request.user )

    class Meta:
        abstract = True

class FormCleanMixin(forms.ModelForm):
   def clean(self):
       if not self.request.user.is_superuser:
           if self.instance.data_status == 3:
               raise forms.ValidationError("Cannot modify QC approved Data")
           if not self.request.user.groups.filter(name=constants['QC_GROUP_NAME']).exists():
               if self.instance.data_status == 2:
                   raise forms.ValidationError("Cannot update Data submitted for QC approval")
               elif self.instance.data_status == 1 and self.instance.created_by and self.instance.created_by != self.request.user:
                   raise forms.ValidationError("Cannot modify Data added by other users")
           if '_submit_for_qc' in self.data:
               self.validate_qc()
               if hasattr(self.instance,'availability') and self.instance.availability is not None:
                   for h in self.instance.availability.all():
                       if (h.hospital.data_status < 2):
                           raise forms.ValidationError(
                               "Cannot submit for QC without submitting associated Hospitals: " + h.hospital.name)
               if hasattr(self.instance,'network') and self.instance.network is not None:
                   if self.instance.network.data_status < 2:
                       class_name = self.instance.network.__class__.__name__
                       raise forms.ValidationError("Cannot submit for QC without submitting associated " + class_name.rstrip('Form')+ ": " + self.instance.network.name)
           if '_qc_approve' in self.data:
               self.validate_qc()
               if hasattr(self.instance,'availability') and self.instance.availability is not None:
                   for h in self.instance.availability.all():
                       if (h.hospital.data_status < 3):
                           raise forms.ValidationError(
                                "Cannot approve QC check without approving associated Hospitals: " + h.hospital.name)
               if hasattr(self.instance,'network') and self.instance.network is not None:
                   if self.instance.network.data_status < 3:
                       class_name = self.instance.network.__class__.__name__
                       raise forms.ValidationError("Cannot approve QC check without approving associated"+ class_name.rstrip('Form') + ": " + self.instance.network.name)
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
