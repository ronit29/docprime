import json
from import_export import resources
from import_export.admin import ImportMixin, base_formats
from ondoc.lead import models
from ondoc.doctor.models import MedicalService, Specialization
from reversion.admin import VersionAdmin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe
from django.contrib.admin.templatetags.admin_modify import register, submit_row as original_submit_row


@register.inclusion_tag('admin/submit_line.html', takes_context=True)
def submit_row(context):
    ctx = original_submit_row(context)
    ctx.update({
        'show_save_and_add_another': context.get('show_save_and_add_another',
                                                 ctx['show_save_and_add_another']),
        'show_save_and_continue': context.get('show_save_and_continue',
                                              ctx['show_save_and_continue']),
        'show_save': context.get('show_save',
                                 ctx['show_save']),
        'show_delete_link': context.get('show_delete_link', ctx['show_delete_link'])
    })
    return ctx


class HospitalLeadResource(resources.ModelResource):
    class Meta:
        model = models.HospitalLead

    def before_save_instance(self, instance, using_transactions, dry_run):
        if isinstance(instance.json, str):
            instance.json = json.loads(instance.json)
        super().before_save_instance(instance, using_transactions, dry_run)


class DoctorLeadResource(resources.ModelResource):

    class Meta:
        model = models.DoctorLead

    def before_save_instance(self, instance, using_transactions, dry_run):
        if isinstance(instance.json, str):
            instance.json = json.loads(instance.json)
        super().before_save_instance(instance, using_transactions, dry_run)


class HospitalLeadAdmin(ImportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    search_fields = []
    list_display = ('city', 'lab', 'name',)
    readonly_fields = ('name', 'lab', "timings", "services", 'city', "address", 'about',)
    exclude = ('source_id', "json", )
    resource_class = HospitalLeadResource

    def change_view(self, request, object_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save_and_continue'] = False
        hospital_lead = models.HospitalLead.objects.get(pk=object_id)
        if not hospital_lead.hospital:
            extra_context['show_save'] = True
        else:
            extra_context['show_save'] = False
        return super().change_view(request, object_id, extra_context=extra_context)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def timings(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if data:
            return format_html_join(
                mark_safe('<br/>'),
                '{} : {}',
                ((key, data.get("WeeklyOpenTime").get(key)) for key in data.get("WeeklyOpenTime").keys()),
            )

    def address(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if data:
            return data.get("Address")

    def services(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if not data:
            return
        return format_html_join(
            mark_safe('<br/>'),
            '{}',
            ((service_name if MedicalService.objects.filter(
                name=service_name).exists() else "{} - Does not exists.".format(service_name),) for service_name in
             data.get("Services").values()),
        )

    def name(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if data:
            return data.get('Name')

    def about(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if data:
            return data.get("About")

    address.short_description = 'Address'
    timings.short_description = "Timings"
    services.short_description = "Services"
    name.short_description = "Name"
    about.short_description = "About"


class DoctorLeadAdmin(ImportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    search_fields = []
    list_display = ('city', 'lab', )
    readonly_fields = ("doctor", "name", "city", "lab",  "services", "specializations", "awards", "about",
                       "LinkedClinic", )
    exclude = ('json', 'source_id',)
    resource_class = DoctorLeadResource

    def save_model(self, request, obj, form, change):
        obj.convert_lead(request.user)
        super(DoctorLeadAdmin, self).save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    def change_view(self, request, object_id, extra_context=None):
        extra_context = extra_context or {}
        extra_context['show_save_and_continue'] = False
        doctor_lead = models.DoctorLead.objects.get(pk=object_id)
        if not doctor_lead.doctor:
            extra_context['show_save'] = True
        else:
            extra_context['show_save'] = False
        return super().change_view(request, object_id, extra_context=extra_context)

    def services(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if not data:
            return
        return format_html_join(
            mark_safe('<br/>'),
            '{}',
            ((service_name if MedicalService.objects.filter(
                name=service_name).exists() else "{} - Does not exists.".format(service_name),) for service_name in
             data.get("Services").values()),
        )

    def specializations(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if not data:
            return
        return format_html_join(
            mark_safe('<br/>'),
            '{}',
            ((specialization_name if Specialization.objects.filter(
                name=specialization_name).exists() else "{} - Does not exists.".format(specialization_name),) for
             specialization_name in
             data.get("Specializations").values()),
        )

    def awards(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if not data:
            return
        return format_html_join(
            mark_safe('<br/>'),
            '{}',
            ((award_name for award_name in data.get("Awards").values()
              ) if data.get("Awards").values() else "None",
             ))

    def name(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if data:
            return data.get('Name')

    def about(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        if data:
            return data.get("About")

    def LinkedClinic(self, instance):
        # data = json.loads(instance.json)
        data = instance.json
        clinic_urls = list(map(lambda x:data.get("LinkedClinics").get(x)[2].get("Clinic URL"), data.get("LinkedClinics")))
        clinics = models.HospitalLead.objects.filter(json__URL__in=clinic_urls)
        if not clinics:
            return
        return clinics.values()

