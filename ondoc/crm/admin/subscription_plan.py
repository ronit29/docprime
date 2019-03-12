from django.contrib.admin import TabularInline
from reversion.admin import VersionAdmin
from django import forms

from ondoc.subscription_plan.models import Plan, PlanFeature


class SubscriptionPlanFeatureInline(TabularInline):
    model = PlanFeature
    max_num = 1
    extra = 0
    autocomplete_fields = ['network', 'lab', 'test']

    # def get_form(self, request, obj=None, **kwargs):
    #     form = super().get_form(request, obj=obj, **kwargs)
    #     form.request = request
    #     form.base_fields['cancellation_reason'].queryset = CancellationReason.objects.filter(
    #         Q(type=Order.DOCTOR_PRODUCT_ID) | Q(type__isnull=True), visible_on_admin=True)
    #     if obj is not None and obj.time_slot_start:
    #         time_slot_start = timezone.localtime(obj.time_slot_start, pytz.timezone(settings.TIME_ZONE))
    #         form.base_fields['start_date'].initial = time_slot_start.strftime('%Y-%m-%d')
    #         form.base_fields['start_time'].initial = time_slot_start.strftime('%H:%M')
    #     return form


class SubscriptionPlanAdmin(VersionAdmin):
    model = Plan
    inlines = [SubscriptionPlanFeatureInline]

