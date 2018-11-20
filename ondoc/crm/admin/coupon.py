from dal import autocomplete
from django.contrib import admin
from django import forms
from ondoc.diagnostic.models import Lab, LabTest
from ondoc.coupon.models import Coupon


class LabAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Lab.objects.none()
        queryset = Lab.objects.all()
        lab_network = self.forwarded.get('lab_network', None)
        if lab_network:
            queryset = queryset.filter(network=lab_network)
        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)
        return queryset


class TestAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LabTest.objects.none()
        lab_network = self.forwarded.get('lab_network', None)
        lab = self.forwarded.get('lab', None)
        if lab_network and lab:
            queryset = LabTest.objects.filter(availablelabs__lab_pricing_group__labs__id=lab)
        elif lab_network and not lab:
            queryset = LabTest.objects.filter(availablelabs__lab_pricing_group__labs__id__in=Lab.objects.filter(network=lab_network))
        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)
        return queryset


class CouponForm(forms.ModelForm):

    class Meta:
        model = Coupon
        fields = ('__all__')
        widgets = {
            'lab': autocomplete.ModelSelect2(url='lab-autocomplete', forward=['lab_network']),
            'test': autocomplete.ModelSelect2Multiple(url='test-autocomplete', forward=['lab', 'lab_network'])
        }


class CouponAdmin(admin.ModelAdmin):

    list_display = (
        'code', 'is_user_specific', 'type', 'count')

    autocomplete_fields = ['lab_network']

    search_fields = ['code']
    form = CouponForm