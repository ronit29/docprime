from dal import autocomplete
from django.contrib import admin
from django import forms
from ondoc.doctor.models import PracticeSpecialization
from ondoc.diagnostic.models import LabNetwork, Lab, LabTest, LabTestCategory
from ondoc.coupon.models import Coupon, UserSpecificCoupon, RandomGeneratedCoupon
from ondoc.procedure.models import Procedure, ProcedureCategory
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from ondoc.authentication.models import User
from django.utils.crypto import get_random_string


class LabNetworkAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LabNetwork.objects.none()
        queryset = LabNetwork.objects.all()
        lab = self.forwarded.get('lab', default=None)
        test = self.forwarded.get('test', default=[])
        test_categories = self.forwarded.get('test_categories', default=[])

        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)
        if lab:
            queryset = queryset.filter(lab__id=lab)
        if test:
            queryset = queryset.filter(lab__lab_pricing_group__available_lab_tests__test__in=test)
        if test_categories:
            queryset = queryset.filter(lab__lab_pricing_group__available_lab_tests__test__categories__in=test_categories)

        return queryset.distinct()


class LabAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Lab.objects.none()
        queryset = Lab.objects.all()
        lab_network = self.forwarded.get('lab_network', None)
        test = self.forwarded.get('test', default=[])
        test_categories = self.forwarded.get('test_categories', default=[])
        if lab_network:
            queryset = queryset.filter(network=lab_network)
        if test:
            queryset = queryset.filter(lab_pricing_group__available_lab_tests__test__in=test)
        if test_categories:
            queryset = queryset.filter(lab_pricing_group__available_lab_tests__test__categories__in=test_categories)
        if self.q:
            queryset = queryset.filter(name__istartswith=self.q)
        return queryset.distinct()


class TestAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LabTest.objects.none()
        lab_network = self.forwarded.get('lab_network', None)
        lab = self.forwarded.get('lab', None)
        test_categories = self.forwarded.get('test_categories', default=[])
        queryset = LabTest.objects.all()

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)

        if lab:
            queryset = queryset.filter(availablelabs__lab_pricing_group__labs=lab, availablelabs__enabled=True)
        if lab_network:
            queryset = queryset.filter(availablelabs__lab_pricing_group__labs__network=lab_network, availablelabs__enabled=True)
        if test_categories:
            queryset = queryset.filter(categories__in=test_categories)

        return queryset.distinct()


class TestCategoriesAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LabTestCategory.objects.none()
        lab_network = self.forwarded.get('lab_network', default=None)
        lab = self.forwarded.get('lab', default=None)
        test = self.forwarded.get('test', default=[])
        queryset = LabTestCategory.objects.all()

        if self.q:
            queryset = queryset.filter(name__icontains=self.q, is_live=True)

        if lab_network:
            queryset = queryset.filter(lab_tests__availablelabs__lab_pricing_group__labs__network=lab_network)
        if lab:
            queryset = queryset.filter(lab_tests__availablelabs__lab_pricing_group__labs=lab)
        if test:
            queryset = queryset.filter(lab_tests__in=test)

        return queryset.distinct()


# class SpecializationsAutocomplete(autocomplete.Select2QuerySetView):
#
#     def get_queryset(self):
#         if not self.request.user.is_authenticated:
#             return LabTest.objects.none()
#         doctor = self.forwarded.get('doctor', None)
#         queryset = PracticeSpecialization.objects.all()
#
#         if self.q:
#             queryset = queryset.filter(name__icontains=self.q)
#
#        if doctor:
#            queryset = queryset.filter(specialization__doctor=doctor,
#                                       specialization__doctor__is_live=True,
#                                       specialization__enabled=True )
#
#         return queryset.distinct()


class ProceduresAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Procedure.objects.none()
        procedure_categories = self.forwarded.get('procedure_categories', [])
        queryset = Procedure.objects.filter(is_enabled=True)

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        if procedure_categories:
            queryset = queryset.filter(categories__in=procedure_categories)

        return queryset.distinct()


class ProcedureCategoriesAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        procedures = self.forwarded.get('procedures', [])
        queryset = ProcedureCategory.objects.all()

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)

        if procedures:
            queryset = queryset.filter(procedures__in=procedures, procedures__is_enabled=True)

        return queryset.distinct()


class CouponForm(forms.ModelForm):

    class Meta:
        model = Coupon
        fields = ('__all__')
        widgets = {
            'lab_network': autocomplete.ModelSelect2(url='lab-network-autocomplete', forward=['lab', 'test', 'test_categories']),
            'lab': autocomplete.ModelSelect2(url='lab-autocomplete', forward=['lab_network', 'test', 'test_categories']),
            'test': autocomplete.ModelSelect2Multiple(url='test-autocomplete', forward=['lab', 'lab_network', 'test_categories']),
            'test_categories': autocomplete.ModelSelect2Multiple(url='test-categories-autocomplete', forward=['lab', 'lab_network', 'test']),
            # 'specializations': autocomplete.ModelSelect2Multiple(url='specializations-autocomplete', forward=[]),
            'procedures': autocomplete.ModelSelect2Multiple(url='procedures-autocomplete', forward=['procedure_categories']),
            'procedure_categories': autocomplete.ModelSelect2Multiple(url='procedure-categories-autocomplete', forward=['procedures'])
        }

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        age_start = cleaned_data.get('age_start')
        age_end = cleaned_data.get('age_end')
        if age_end and not age_start:
            age_start = 0
        if age_start and not age_end:
            age_end = 100
        if age_start > age_end:
            raise forms.ValidationError('Age End is smaller than Age Start.')


class CouponAdmin(admin.ModelAdmin):

    list_display = (
        'id', 'code', 'is_user_specific', 'type', 'count', 'created_at', 'updated_at')

    autocomplete_fields = ['specializations']

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
        users = User.objects.filter(phone_number__in=import_phone_numbers, user_type=User.CONSUMER).all()
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


class RandomGeneratedCouponAdmin(admin.ModelAdmin):

    readonly_fields = ('random_coupon', 'sent_at', 'consumed_at')

    list_display = ('id', 'random_coupon', 'coupon', 'user', 'sent_at', 'consumed_at', 'created_at', 'updated_at')

    def save_model(self, request, obj, form, change):

        if not obj.random_coupon:
            obj.random_coupon = get_random_string(length=10).upper()
            while RandomGeneratedCoupon.objects.filter(random_coupon=obj.random_coupon).exists():
                obj.random_coupon = get_random_string(length=10).upper()
        super().save_model(request, obj, form, change)

    class Meta:
        model = RandomGeneratedCoupon
        fields = ('__all__')
