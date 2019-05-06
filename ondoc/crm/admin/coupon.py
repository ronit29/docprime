from dal import autocomplete
from django.contrib import admin
from django import forms
from ondoc.doctor.models import PracticeSpecialization, Doctor, Hospital
from ondoc.diagnostic.models import LabNetwork, Lab, LabTest, LabTestCategory
from ondoc.coupon.models import Coupon, UserSpecificCoupon, RandomGeneratedCoupon
from ondoc.procedure.models import Procedure, ProcedureCategory
from import_export.admin import ImportExportModelAdmin
from import_export import resources
from ondoc.authentication.models import User, UserProfile
from django.utils.crypto import get_random_string


class LabNetworkAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return LabNetwork.objects.none()
        queryset = LabNetwork.objects.all()
        lab = self.forwarded.get('lab', None)
        test = self.forwarded.get('test', [])
        test_categories = self.forwarded.get('test_categories',[])

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
        test = self.forwarded.get('test', [])
        test_categories = self.forwarded.get('test_categories', [])
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
        test_categories = self.forwarded.get('test_categories', [])
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
        lab_network = self.forwarded.get('lab_network', None)
        lab = self.forwarded.get('lab', None)
        test = self.forwarded.get('test', [])
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


class DoctorsAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Doctor.objects.none()
        queryset = Doctor.objects.filter(is_live=True, enabled=True,)
        hospitals = self.forwarded.get('hospitals', [])
        specializations = self.forwarded.get('specializations', [])
        procedures = self.forwarded.get('procedures', [])
        procedure_categories = self.forwarded.get('procedure_categories', [])

        if self.q:
            queryset = queryset.filter(name__icontains=self.q, is_live=True)

        if hospitals:
            queryset = queryset.filter(hospitals__in=hospitals)
        if specializations:
            queryset = queryset.filter(doctorpracticespecializations__specialization__in=specializations)
        if procedures:
            queryset = queryset.filter(doctor_clinics__procedures_from_doctor_clinic__procedure__in=procedures,
                                       doctor_clinics__procedures_from_doctor_clinic__procedure__is_enabled=True)
        if procedure_categories:
            queryset = queryset.filter(doctor_clinics__procedures_from_doctor_clinic__procedure__categories__in=procedure_categories)
        return queryset.distinct()


class HospitalsAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Hospital.objects.none()
        queryset = Hospital.objects.all()
        doctors = self.forwarded.get('doctors', [])
        specializations = self.forwarded.get('specializations', [])
        procedures = self.forwarded.get('procedures', [])
        procedure_categories = self.forwarded.get('procedure_categories', [])

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)

        if doctors:
            queryset = queryset.filter(hospital_doctors__doctor__in=doctors,
                                       hospital_doctors__doctor__enabled=True,
                                       hospital_doctors__doctor__is_live=True)
        if specializations:
            queryset = queryset.filter(hospital_doctors__doctor__doctorpracticespecializations__specialization__in=specializations)
        if procedures:
            queryset = queryset.filter(hospital_doctors__procedures_from_doctor_clinic__procedure__in=procedures,
                                       hospital_doctors__procedures_from_doctor_clinic__procedure__is_enabled=True)
        if procedure_categories:
            queryset = queryset.filter(hospital_doctors__procedures_from_doctor_clinic__procedure__categories__in=procedure_categories)
        return queryset.distinct()


class SpecializationsAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return PracticeSpecialization.objects.none()
        queryset = PracticeSpecialization.objects.all()
        doctors = self.forwarded.get('doctors', [])
        hospitals = self.forwarded.get('hospitals', [])
        procedures = self.forwarded.get('procedures', [])
        procedure_categories = self.forwarded.get('procedure_categories', [])

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)

        if doctors:
            queryset = queryset.filter(specialization__doctor__in=doctors,
                                       specialization__doctor__is_live=True,
                                       specialization__doctor__enabled=True)
        if hospitals:
            queryset = queryset.filter(specialization__doctor__doctor_clinics__hospital__in=hospitals)
        if procedures:
            queryset = queryset.filter(specialization__doctor__doctor_clinics__procedures_from_doctor_clinic__procedure__in=procedures,
                                       specialization__doctor__doctor_clinics__procedures_from_doctor_clinic__procedure__is_enabled=True)
        if procedure_categories:
            queryset = queryset.filter(specialization__doctor__doctor_clinics__procedures_from_doctor_clinic__procedure__categories__in=procedure_categories)
        return queryset.distinct()


class ProceduresAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Procedure.objects.none()
        doctors = self.forwarded.get('doctors', [])
        hospitals = self.forwarded.get('hospitals', [])
        specializations = self.forwarded.get('specializations', [])
        procedure_categories = self.forwarded.get('procedure_categories', [])
        queryset = Procedure.objects.filter(is_enabled=True)

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        if doctors:
            queryset = queryset.filter(doctor_clinics_from_procedure__doctor_clinic__doctor__in=doctors,
                                       doctor_clinics_from_procedure__doctor_clinic__doctor__enabled=True,
                                       doctor_clinics_from_procedure__doctor_clinic__doctor__is_live=True)
        if hospitals:
            queryset = queryset.filter(doctor_clinics_from_procedure__doctor_clinic__hospital__in=hospitals)
        if specializations:
            queryset = queryset.filter(doctor_clinics_from_procedure__doctor_clinic__doctor__doctorpracticespecializations__specialization__in=specializations)
        if procedure_categories:
            queryset = queryset.filter(categories__in=procedure_categories)

        return queryset.distinct()


class ProcedureCategoriesAutocomplete(autocomplete.Select2QuerySetView):

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return ProcedureCategory.objects.none()
        doctors = self.forwarded.get('doctors', [])
        hospitals = self.forwarded.get('hospitals', [])
        specializations = self.forwarded.get('specializations', [])
        procedures = self.forwarded.get('procedures', [])
        queryset = ProcedureCategory.objects.all()

        if self.q:
            queryset = queryset.filter(name__icontains=self.q)
        if doctors:
            queryset = queryset.filter(procedures__doctor_clinics_from_procedure__doctor_clinic__doctor__in=doctors,
                                       procedures__doctor_clinics_from_procedure__doctor_clinic__doctor__enabled=True,
                                       procedures__doctor_clinics_from_procedure__doctor_clinic__doctor__is_live=True)
        if hospitals:
            queryset = queryset.filter(procedures__doctor_clinics_from_procedure__doctor_clinic__hospital__in=hospitals)
        if specializations:
            queryset = queryset.filter(procedures__doctor_clinics_from_procedure__doctor_clinic__doctor__doctorpracticespecializations__specialization__in=specializations)
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
            'doctors': autocomplete.ModelSelect2Multiple(url='doctors-autocomplete', forward=['hospitals', 'specializations', 'procedures', 'procedure_categories']),
            'hospitals': autocomplete.ModelSelect2Multiple(url='hospitals-autocomplete', forward=['doctors', 'specializations', 'procedures', 'procedure_categories']),
            'specializations': autocomplete.ModelSelect2Multiple(url='specializations-autocomplete', forward=['doctors', 'hospitals', 'procedures', 'procedure_categories']),
            'procedures': autocomplete.ModelSelect2Multiple(url='procedures-autocomplete', forward=['doctors', 'hospitals', 'specializations', 'procedure_categories']),
            'procedure_categories': autocomplete.ModelSelect2Multiple(url='procedure-categories-autocomplete', forward=['doctors', 'hospitals', 'specializations', 'procedures'])
        }

    def clean(self):
        super().clean()
        if any(self.errors):
            return
        cleaned_data = self.cleaned_data
        code = cleaned_data.get('code')
        type = cleaned_data.get('type')
        age_start = cleaned_data.get('age_start')
        age_end = cleaned_data.get('age_end')
        lab_network = cleaned_data.get('lab_network')
        lab = cleaned_data.get('lab')
        test = cleaned_data.get('test')
        test_categories = cleaned_data.get('test_categories')
        doctors = cleaned_data.get('doctors')
        hospitals = cleaned_data.get('hospitals')
        specializations = cleaned_data.get('specializations')
        procedures = cleaned_data.get('procedures')
        procedure_categories = cleaned_data.get('procedure_categories')
        if 'code' in self.changed_data and code and Coupon.objects.filter(code=code)[:1]:
            raise forms.ValidationError('Coupon is already there. Please create unique coupon.')
        if age_end and not age_start:
            age_start = 0
        if age_start and not age_end:
            age_end = 100
        if age_start and age_end and age_start > age_end:
            raise forms.ValidationError('Age End cannot be smaller than Age Start.')
        if (lab_network or lab or test or test_categories) and \
                (doctors or hospitals or specializations or procedures or procedure_categories):
            raise forms.ValidationError('Please enter either lab specific data or doctor specific data')
        if (lab_network or lab or test or test_categories) and type != Coupon.LAB:
            raise forms.ValidationError('Type \'Lab\' not selected for lab specific coupon')
        if (doctors or hospitals or specializations or procedures or procedure_categories) and type != Coupon.DOCTOR:
            raise forms.ValidationError('Type \'Doctor\' not selected for doctor specific coupon')


class CouponAdmin(admin.ModelAdmin):

    list_display = (
        'id', 'code', 'is_user_specific', 'type', 'count', 'created_at', 'updated_at')

    autocomplete_fields = ['payment_option']

    search_fields = ['code']
    form = CouponForm


class UserSpecificCouponResource(resources.ModelResource):

    def before_import(self, dataset, using_transactions, dry_run, **kwargs):
        self.user_profiles = {}
        self.processed_already = {}
        import_phone_numbers = []
        import_coupons = []

        if dataset.dict:
            for row in dataset.dict:
                ph_no = str(int(row['phone_number']))
                coupon_id = str(int(row['coupon']))
                import_phone_numbers.append(ph_no)
                import_coupons.append(coupon_id)

                if ph_no not in self.user_profiles:
                    self.user_profiles[ph_no] = []
                self.user_profiles[ph_no].append(row)

            self.coupons = {}
            coupons = UserSpecificCoupon.objects.select_related('coupon').filter(phone_number__in=import_phone_numbers,
                                                                                 coupon_id__in=import_coupons).all()
            for coupon in coupons:
                self.coupons[str(coupon.coupon_id) + ":" + str(coupon.phone_number)] = True

        super().before_import(dataset, using_transactions, dry_run, **kwargs)

    def before_import_row(self, row, **kwargs):
        if row['phone_number']:
            row['phone_number'] = str(int(row['phone_number']))
            row['coupon'] = int(row['coupon'])

            ph_no = row['phone_number']
            user = User.objects.filter(phone_number=ph_no, user_type=User.CONSUMER).first()

            if not user:
                user = User()
                user.phone_number = str(int(ph_no))
                user.user_type = User.CONSUMER
                user.save()

            if row["name"]:
                profile = UserProfile.objects.filter(user=user, phone_number=int(ph_no), name=row.get('name'))
                if not profile.exists():
                    is_default_user = False if UserProfile.objects.filter(user=user, is_default_user=True).count() > 0 else True
                    UserProfile.objects.create(user=user, phone_number=int(ph_no), name=row.get('name'), email=row.get('email', None), is_default_user=is_default_user)

            if ph_no in self.user_profiles:
                row['count'] = len(self.user_profiles[ph_no])
            row['user'] = user.id

        super().before_import_row(row, **kwargs)

    def skip_row(self, instance, original):
        coupon_str = str(instance.coupon_id) + ":" + str(instance.phone_number)
        if coupon_str in self.processed_already:
            return True
        else:
            self.processed_already[coupon_str] = True
            return coupon_str in self.coupons

    class Meta:
        model = UserSpecificCoupon
        fields = ('phone_number', 'coupon', 'id', 'user', 'count')


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
