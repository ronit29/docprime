import json
from import_export import resources
from import_export.admin import ImportMixin, base_formats
from ondoc.lead.models import HospitalLead
from reversion.admin import VersionAdmin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe


class HospitalLeadResource(resources.ModelResource):

    class Meta:
        model = HospitalLead


class HospitalLeadAdmin(ImportMixin, VersionAdmin):
    formats = (base_formats.XLS, base_formats.XLSX,)
    search_fields = []
    list_display = ('city', 'lab', 'name', )
    readonly_fields = ('name', 'lab', "timings", "services", 'city',  "address", 'about', )
    exclude = ('json', 'source_id', )
    resource_class = HospitalLeadResource

    def has_delete_permission(self, request, obj=None):
        return False

    def timings(self, instance):
        data = json.loads(instance.json)
        if data:
            return format_html_join(
                mark_safe('<br/>'),
                '{} : {}',
                ((key, data.get("WeeklyOpenTime").get(key)) for key in data.get("WeeklyOpenTime").keys()),
            )

    def address(self, instance):
        data = json.loads(instance.json)
        if data:
            return data.get("Address")

    def services(self, instance):
        data = json.loads(instance.json)
        if not data:
            return
        return format_html_join(
            mark_safe('<br/>'),
            '{}',
            ((line,) for line in data.get("Services").values()),
        )

    def name(self, instance):
        data = json.loads(instance.json)
        if data:
            return data.get('Name')

    def about(self, instance):
        data = json.loads(instance.json)
        if data:
            return data.get("About")


    address.short_description = 'Address'
    timings.short_description = "Timings"
    services.short_description = "Services"