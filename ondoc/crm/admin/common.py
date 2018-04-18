from django.contrib.gis import admin
import datetime

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
