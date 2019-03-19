from django.contrib.admin import TabularInline
from reversion.admin import VersionAdmin

from ondoc.diagnostic.models import LabTest
from ondoc.subscription_plan.models import Plan, PlanFeature, PlanFeatureMapping, UserPlanMapping


class PlanFeatureMappingInline(TabularInline):
    model = PlanFeatureMapping
    max_num = 1
    extra = 0
    autocomplete_fields = ['feature']

    def get_readonly_fields(self, request, obj=None):
        read_only = super().get_readonly_fields(request, obj)
        # if self.instance and self.:
        #     read_only += ('feature', 'count')
        return read_only


class SubscriptionPlanAdmin(VersionAdmin):
    model = Plan
    inlines = [PlanFeatureMappingInline]
    search_fields = ['name']

    def get_readonly_fields(self, request, obj=None):
        read_only = super().get_readonly_fields(request, obj)
        if obj and obj.id:
            read_only += ('mrp', 'deal_price', 'priority_queue', 'unlimited_online_consultation', 'name')
        return read_only


class SubscriptionPlanFeatureAdmin(VersionAdmin):
    model = PlanFeature
    list_display = ['id', 'name', 'test']
    search_fields = ['name']
    exclude = ['network', 'lab']

    def get_readonly_fields(self, request, obj=None):
        read_only = super().get_readonly_fields(request, obj)
        if obj and obj.id:
            read_only += ('test',)
        return read_only

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.request = request
        name_field = form.base_fields.get('name')
        if name_field:
            name_field.required = True
        test_field = form.base_fields.get('test')
        if test_field:
            test_field.queryset = LabTest.objects.filter(is_package=True, enable_for_retail=True, searchable=True)
        return form


class UserPlanMappingAdmin(VersionAdmin):
    model = UserPlanMapping
    list_display = ['id', 'plan', 'user', 'expire_at', 'is_active']
    search_fields = ['user', 'plan']
    exclude = ['extra_details', 'money_pool']
    autocomplete_fields = ['plan', 'user']

    def get_readonly_fields(self, request, obj=None):
        read_only = super().get_readonly_fields(request, obj)
        if obj and obj.id:
            read_only += ('id', 'plan', 'user', 'expire_at', 'created_at')
        return read_only
