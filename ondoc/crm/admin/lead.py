import json
from import_export import resources
from import_export.admin import ImportMixin, base_formats
from ondoc.lead import models
from ondoc.doctor.models import MedicalService, Specialization, DoctorAward
from reversion.admin import VersionAdmin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe


class HospitalLeadResource(resources.ModelResource):
    class Meta:
        model = models.HospitalLead


class DoctorLeadResource(resources.ModelResource):

    class Meta:
        model = models.DoctorLead


class HospitalLeadAdmin(ImportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    search_fields = []
    list_display = ('city', 'lab', 'name',)
    readonly_fields = ('name', 'lab', "timings", "services", 'city', "address", 'about',)
    exclude = ('source_id', "json", )
    resource_class = HospitalLeadResource

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
    readonly_fields = ("name", "city", "lab",  "services", "specializations", "awards", "about",
                       "LinkedClinic", )
    exclude = ('json', 'source_id',)
    resource_class = DoctorLeadResource

    def save_model(self, request, obj, form, change):

        super(DoctorLeadAdmin, self).save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return False

    # def has_change_permission(self, request, obj=None):
    #     return True

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

