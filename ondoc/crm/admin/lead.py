import json
from import_export import resources
from import_export.admin import ImportExportModelAdmin
from ondoc.lead.models import HospitalLead
from reversion.admin import VersionAdmin
from django.utils.html import format_html_join
from django.utils.safestring import mark_safe


class HospitalLeadResource(resources.ModelResource):

    class Meta:
        model = HospitalLead


class HospitalLeadAdmin(ImportExportModelAdmin, VersionAdmin):
    search_fields = []
    list_display = ('source_id', 'city', 'lab', 'name', )
    readonly_fields = ('source_id', 'city', 'lab', "timings", "address", "services", 'name',
                       'about', )
    exclude = ('json', )
    resource_class = HospitalLeadResource

    def timings(self, instance):
        data = json.loads(instance.json)
        if data:
            return data.get("WeeklyOpenTime")

    def address(self, instance):
        data = json.loads(instance.json)
        if data:
            return data.get("Address")

    def services(self, instance):
        data = json.loads(instance.json)
        # if data:
        #     return ", ".join([value for value in data.get("Services").values()])
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