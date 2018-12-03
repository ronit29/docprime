from dal import autocomplete
from django.contrib import admin
from django import forms
from ondoc.diagnostic.models import Lab, LabTest
from ondoc.coupon.models import Coupon, UserSpecificCoupon
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from ondoc.authentication.models import User

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
        queryset = LabTest.objects.all()

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)

        if lab:
            queryset = queryset.filter(availablelabs__lab_pricing_group__labs=lab, availablelabs__enabled=True)
        elif lab_network:
            queryset = queryset.filter(availablelabs__lab_pricing_group__labs__network=lab_network, availablelabs__enabled=True)


        return queryset.distinct()


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
        'id', 'code', 'is_user_specific', 'type', 'count', 'created_at', 'updated_at')

    autocomplete_fields = ['lab_network']

    search_fields = ['code']
    form = CouponForm


class UserSpecificCouponResource(resources.ModelResource):

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        import_phone_numbers = []
        import_coupons = []
        if dataset.dict:
            for row in dataset.dict:
                ph_no = str(int(row['phone_number']))
                coupon_id = str(int(row['coupon']))
                import_phone_numbers.append(ph_no)
                import_coupons.append(coupon_id)

        self.users_dict = {}
        users = User.objects.filter(phone_number__in=import_phone_numbers).all()
        for user in users:
            self.users_dict[user.phone_number] = user.id

        self.coupons = {}
        coupons = UserSpecificCoupon.objects.select_related('coupon').filter(phone_number__in=import_phone_numbers,coupon_id__in=import_coupons).all()
        for coupon in coupons:
            self.coupons[str(coupon.coupon_id) + ":" + str(coupon.phone_number)] = True

        super().before_import(dataset, using_transactions, dry_run, **kwargs)

    def before_import_row(self, row, **kwargs):
        if row['phone_number']:
            row['phone_number'] = str(int(row['phone_number']))
            user = self.users_dict.get(row['phone_number'], None)
            if user:
                row['user'] = user
        super().before_import_row(row, **kwargs)

    def skip_row(self, instance, original):
        coupon_str = str(instance.coupon_id) + ":" + str(instance.phone_number)
        return coupon_str in self.coupons

    class Meta:
        model = UserSpecificCoupon
        fields = ('phone_number', 'coupon', 'id', 'user')


class UserSpecificCouponAdmin(ImportExportModelAdmin):
    resource_class = UserSpecificCouponResource


