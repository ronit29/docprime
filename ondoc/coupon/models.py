from django.db import models
from django.db.models import F, ExpressionWrapper, DateTimeField

from ondoc.authentication import models as auth_model
from ondoc.common.models import PaymentOptions
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.utils.functional import cached_property
import sys
import datetime
from django.utils.crypto import get_random_string
import logging
logger = logging.getLogger(__name__)


class Coupon(auth_model.TimeStampedModel):
    DOCTOR = 1
    LAB = 2
    ALL = 3
    SUBSCRIPTION_PLAN = 4

    DISCOUNT = 1
    CASHBACK = 2

    TYPE_CHOICES = (("", "Select"), (DOCTOR, "Doctor"), (LAB, "Lab"), (ALL, "All"), (SUBSCRIPTION_PLAN, "SUBSCRIPTION_PLAN"),)
    COUPON_TYPE_CHOICES = ((DISCOUNT, "Discount"), (CASHBACK, "Cashback"),)

    code = models.CharField(max_length=50)
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    percentage_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True, validators=[MaxValueValidator(100), MinValueValidator(0)])
    max_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    flat_discount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    validity = models.PositiveIntegerField(blank=False, null=False)
    start_date = models.DateTimeField(default=None, null=True, blank=True)
    type = models.IntegerField(choices=TYPE_CHOICES)
    age_start = models.PositiveIntegerField(blank=True, null=True, default=None,
                                            validators=[MaxValueValidator(100), MinValueValidator(0)])
    age_end = models.PositiveIntegerField(blank=True, null=True, default=None,
                                          validators=[MaxValueValidator(100), MinValueValidator(0)])
    gender = models.CharField(max_length=1, choices=auth_model.UserProfile.GENDER_CHOICES, default=None, null=True, blank=True)
    cities = models.CharField(max_length=100, default=None, null=True, blank=True)
    count = models.PositiveIntegerField()
    total_count = models.PositiveIntegerField(null=True, blank=True)
    step_count = models.PositiveIntegerField(verbose_name="Valid only at multiples of this appointment number", default=1, validators=[MinValueValidator(1)], blank=True, null=True)
    description = models.CharField(max_length=500, default="")
    heading = models.CharField(max_length=500, default="")
    tnc = models.CharField(max_length=2000, default="")
    lab_network = models.ForeignKey("diagnostic.LabNetwork", on_delete=models.CASCADE, blank=True, null=True)
    lab = models.ForeignKey("diagnostic.Lab", on_delete=models.CASCADE, blank=True, null=True)
    test = models.ManyToManyField("diagnostic.LabTest", blank=True)
    test_categories = models.ManyToManyField("diagnostic.LabTestCategory", blank=True)
    doctors = models.ManyToManyField("doctor.Doctor", blank=True)
    hospitals = models.ManyToManyField("doctor.Hospital", blank=True)
    specializations = models.ManyToManyField("doctor.PracticeSpecialization", blank=True)
    procedures = models.ManyToManyField("procedure.Procedure", blank=True)
    procedure_categories = models.ManyToManyField("procedure.ProcedureCategory", blank=True)
    show_price = models.BooleanField(default=True)
    is_user_specific = models.BooleanField(default=False)
    is_corporate = models.BooleanField(default=False)
    is_visible = models.BooleanField(default=True)
    new_user_constraint = models.BooleanField(default=False)
    coupon_type = models.IntegerField(choices=COUPON_TYPE_CHOICES, default=DISCOUNT)
    payment_option = models.ForeignKey(PaymentOptions, on_delete=models.SET_NULL, blank=True, null=True)
    random_coupon_count = models.PositiveIntegerField(null=True, blank=True)
    plan = models.ManyToManyField("subscription_plan.Plan", blank=True, null=True)
    total_used_count = models.PositiveIntegerField(null=True, blank=True, default=0)

    def save(self, *args, **kwargs):
        if not self.id:
            self.start_date = datetime.datetime.now()
        if self.age_start and not self.age_end:
            self.age_end = 100
        if self.age_end and not self.age_start:
            self.age_start = 0
        return super().save(*args, **kwargs)

    def get_search_coupon_discounted_price(self, deal_price):
        from ondoc.api.v1.utils import CouponsMixin
        mixin_obj = CouponsMixin()
        discount = mixin_obj.get_discount(self, deal_price)
        return max(0, deal_price - discount)

    @classmethod
    def get_search_coupon(cls, user):
        coupon_obj = cls.objects.filter(code="WELCOME").first()
        used_count = 0

        if coupon_obj and user.is_authenticated:
            used_count = coupon_obj.used_coupon_count(user)

        if coupon_obj and used_count >= coupon_obj.count:
            coupon_obj = None

        return coupon_obj

    def used_coupon_count(self, user, cart_item=None):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.cart.models import Cart
        from ondoc.subscription_plan.models import UserPlanMapping

        if not user.is_authenticated:
            return 0


        count = 0
        if str(self.type) == str(self.DOCTOR) or str(self.type) == str(self.ALL):
            count += OpdAppointment.objects.filter(user=user,
                                                   status__in=[OpdAppointment.CREATED, OpdAppointment.BOOKED,
                                                               OpdAppointment.RESCHEDULED_DOCTOR,
                                                               OpdAppointment.RESCHEDULED_PATIENT,
                                                               OpdAppointment.ACCEPTED,
                                                               OpdAppointment.COMPLETED],
                                                   coupon=self).count()
        if str(self.type) == str(self.LAB) or str(self.type) == str(self.ALL):
            count += LabAppointment.objects.filter(user=user,
                                                   status__in=[LabAppointment.CREATED, LabAppointment.BOOKED,
                                                               LabAppointment.RESCHEDULED_LAB,
                                                               LabAppointment.RESCHEDULED_PATIENT,
                                                               LabAppointment.ACCEPTED,
                                                               LabAppointment.COMPLETED],
                                                   coupon=self).count()
        if str(self.type) == str(self.SUBSCRIPTION_PLAN) or str(self.type) == str(self.ALL):
            count += UserPlanMapping.objects.filter(user=user,
                                                   status__in=[UserPlanMapping.BOOKED],
                                                   coupon=self).count()

        count += Cart.objects.filter(user=user, deleted_at__isnull=True, data__coupon_code__contains=self.code).exclude(id=cart_item).count()
        return count

    def random_coupon_used_count(self, user, code, cart_item=None):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.cart.models import Cart
        from ondoc.subscription_plan.models import UserPlanMapping

        if user and not user.is_authenticated:
            return 0

        count = 0
        if str(self.type) == str(self.DOCTOR) or str(self.type) == str(self.ALL):
            qs = OpdAppointment.objects.filter(status__in=[OpdAppointment.CREATED, OpdAppointment.BOOKED,
                                                               OpdAppointment.RESCHEDULED_DOCTOR,
                                                               OpdAppointment.RESCHEDULED_PATIENT,
                                                               OpdAppointment.ACCEPTED,
                                                               OpdAppointment.COMPLETED],
                                                   coupon=self,
                                                   coupon_data__random_coupons__random_coupon_list__contains=[code])
            if user:
                qs = qs.filter(user=user)
            count += qs.count()


        if str(self.type) == str(self.LAB) or str(self.type) == str(self.ALL):
            qs = LabAppointment.objects.filter(status__in=[LabAppointment.CREATED, LabAppointment.BOOKED,
                                                           LabAppointment.RESCHEDULED_LAB,
                                                           LabAppointment.RESCHEDULED_PATIENT,
                                                           LabAppointment.ACCEPTED,
                                                           LabAppointment.COMPLETED],
                                               coupon=self,
                                               coupon_data__random_coupons__random_coupon_list__contains=[code])
            if user:
                qs = qs.filter(user=user)
            count += qs.count()
        if str(self.type) == str(self.SUBSCRIPTION_PLAN) or str(self.type) == str(self.ALL):
            qs = UserPlanMapping.objects.filter(status__in=[UserPlanMapping.BOOKED],
                                                coupon=self,
                                                coupon_data__random_coupons__random_coupon_list__contains=[code])
            if user:
                qs = qs.filter(user=user)
            count += qs.count()

        qs = Cart.objects.filter(deleted_at__isnull=True, data__coupon_code__contains=code).exclude(id=cart_item)
        if user:
            qs = qs.filter(user=user)
        count += qs.count()

        return count

    def total_used_coupon_count(self):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.diagnostic.models import LabAppointment

        count = 0
        if str(self.type) == str(self.DOCTOR) or str(self.type) == str(self.ALL):
            count += OpdAppointment.objects.filter(status__in=[OpdAppointment.CREATED, OpdAppointment.BOOKED,
                                                               OpdAppointment.RESCHEDULED_DOCTOR,
                                                               OpdAppointment.RESCHEDULED_PATIENT,
                                                               OpdAppointment.ACCEPTED,
                                                               OpdAppointment.COMPLETED],
                                                   coupon=self).count()
        if str(self.type) == str(self.LAB) or str(self.type) == str(self.ALL):
            count += LabAppointment.objects.filter(status__in=[LabAppointment.CREATED, LabAppointment.BOOKED,
                                                               LabAppointment.RESCHEDULED_LAB,
                                                               LabAppointment.RESCHEDULED_PATIENT,
                                                               LabAppointment.ACCEPTED,
                                                               LabAppointment.COMPLETED],
                                                   coupon=self).count()
        return count

    @classmethod
    def get_total_deduction(cls, data, deal_price):
        from ondoc.doctor.models import OpdAppointment
        coupon_list = []
        random_coupon_list = []
        discount_coupon_list = []
        cashback_coupon_list = []

        coupon_discount = 0
        coupon_cashback = 0

        if data.get("coupon_code"):
            coupon_obj = RandomGeneratedCoupon.get_coupons(set(data.get("coupon_code")))
            # coupon_obj = cls.objects.filter(code__in=set(data.get("coupon_code")))
            obj = OpdAppointment()

            remaining_deal_price = deal_price
            for coupon in coupon_obj:
                if coupon.coupon_type == coupon.CASHBACK:
                    cashback_coupon_list.append(coupon)
                elif coupon.coupon_type == coupon.DISCOUNT:
                    discount_coupon_list.append(coupon)

            for coupon in discount_coupon_list:
                if remaining_deal_price > 0:
                    if coupon.test.exists() and coupon.type == Coupon.LAB:
                        tests_deal_price = obj.get_applicable_tests_with_total_price(coupon_obj=coupon, test_ids=data['test_ids'], lab=data["lab"]).get("total_price")
                        tests_deal_price = min(remaining_deal_price, tests_deal_price)
                        curr_discount = obj.get_discount(coupon, tests_deal_price)
                    elif coupon.procedures.exists() and coupon.type == Coupon.DOCTOR and data.get("doctor") and data.get("hospital") and data.get("procedures"):
                        procedures_deal_price = obj.get_applicable_procedures_with_total_price(coupon_obj=coupon,
                                                                                       procedures=data['procedures'],
                                                                                       doctor=data["doctor"],
                                                                                       hospital=data["hospital"]).get("total_price")
                        procedures_deal_price = min(remaining_deal_price, procedures_deal_price)
                        curr_discount = obj.get_discount(coupon, procedures_deal_price)
                    else:
                        curr_discount = obj.get_discount(coupon, remaining_deal_price)
                    coupon_discount += curr_discount
                    remaining_deal_price -= curr_discount
                    coupon_list.append(coupon.id)
                    if hasattr(coupon, 'is_random') and coupon.is_random:
                        random_coupon_list.append(coupon.random_coupon_code)


            for coupon in cashback_coupon_list:
                if remaining_deal_price > 0:
                    if coupon.test.exists() and coupon.type == Coupon.LAB:
                        tests_deal_price = obj.get_applicable_tests_with_total_price(coupon_obj=coupon, test_ids=data['test_ids'], lab=data["lab"]).get("total_price")
                        tests_deal_price = min(remaining_deal_price, tests_deal_price)
                        curr_cashback = obj.get_discount(coupon, tests_deal_price)
                    elif coupon.procedures.exists() and coupon.type == Coupon.DOCTOR and data.get("doctor") and data.get("hospital") and data.get("procedures"):
                        procedures_deal_price = obj.get_applicable_procedures_with_total_price(coupon_obj=coupon,
                                                                                       procedures=data['procedures'],
                                                                                       doctor=data["doctor"],
                                                                                       hospital=data["hospital"]).get("total_price")
                        procedures_deal_price = min(remaining_deal_price, procedures_deal_price)
                        curr_cashback = obj.get_discount(coupon, procedures_deal_price)
                    else:
                        curr_cashback = obj.get_discount(coupon, remaining_deal_price)
                    coupon_cashback += curr_cashback
                    remaining_deal_price -= curr_cashback
                    coupon_list.append(coupon.id)
                    if hasattr(coupon, 'is_random') and coupon.is_random:
                        random_coupon_list.append(coupon.random_coupon_code)

        return coupon_discount, coupon_cashback, coupon_list, random_coupon_list

    def __str__(self):
        return self.code

    class Meta:
        db_table = "coupon"


class UserSpecificCoupon(auth_model.TimeStampedModel):

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, null=False, related_name="user_specific_coupon")
    phone_number = models.CharField(max_length=10, blank=False, null=False)
    user = models.ForeignKey(auth_model.User, on_delete=models.SET_NULL, null=True, blank=True)
    count = models.PositiveIntegerField(default=1)

    def save(self, *args, **kwargs):
        try:
            '''
            Set User for a given phone number if not assigned explicitly.
            '''
            if self.phone_number and not self.user:
                user = auth_model.User.objects.filter(phone_number=self.phone_number, user_type=auth_model.User.CONSUMER).first()
                if user:
                    self.user = user
        except Exception as e:
            logger.error(str(e))

        super().save(*args, **kwargs)

    def __str__(self):
        return self.coupon.code

    class Meta:
        db_table = "user_specific_coupon"


class RandomGeneratedCoupon(auth_model.TimeStampedModel):

    random_coupon = models.CharField(max_length=50)
    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="random_generated_coupon")
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE, null=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)
    validity = models.PositiveIntegerField(null=True, blank=True)

    @classmethod
    def get_coupons(cls, coupon_codes):
        coupon_obj = None

        expression = F('sent_at') + datetime.timedelta(days=1) * F('validity')
        annotate_expression = ExpressionWrapper(expression, DateTimeField())
        random_coupons = cls.objects.annotate(last_date=annotate_expression)\
                                                                .filter(random_coupon__in=coupon_codes,
                                                                         sent_at__isnull=False,
                                                                         consumed_at__isnull=True,
                                                                         last_date__gte=datetime.datetime.now()
                                                                ).all()

        if random_coupons:
            c_list = ','.join(["'" + str(c) + "'" for c in coupon_codes])
            coupon_obj = Coupon.objects\
                .prefetch_related('random_generated_coupon')\
                .annotate(is_random=models.Value(True, models.BooleanField()),
                          random_count=models.Value(1, models.IntegerField()))\
                .filter(id__in=random_coupons.values_list('coupon', flat=True)) \
                .extra(select={'random_coupon_code': 'SELECT random_coupon FROM random_generated_coupon where coupon_id = coupon.id AND random_coupon IN ('+c_list+')'})

        if not coupon_obj:
            coupon_obj = Coupon.objects \
                .prefetch_related('random_generated_coupon')\
                .annotate(is_random=models.Value(False, models.BooleanField()),
                          random_count=models.Value(0, models.IntegerField()),
                          random_coupon_code=models.Value("", models.CharField()))\
                .filter(code__in=coupon_codes)

        return coupon_obj

    def __str__(self):
        return self.random_coupon

    class Meta:
        db_table = "random_generated_coupon"




class CouponRecommender():

    def __init__(self, user, profile, type, product_id, coupon_code, cart_item_id):
        self.user = user
        self.type = type
        self.profile = profile
        self.product_id = product_id
        self.coupon_code = coupon_code
        self.user_cart_counts = dict()
        self.coupon_properties = dict()
        self.payment_option_filter = None
        self.cart_item_id = cart_item_id

    @cached_property
    def all_applicable_coupons(self):
        from ondoc.diagnostic.models import LabAppointment
        from ondoc.doctor.models import OpdAppointment
        from ondoc.cart.models import Cart

        user = self.user
        search_type = self.type
        profile = self.profile
        product_id = self.product_id
        coupon_code = self.coupon_code
        user_cart_counts = self.user_cart_counts
        types = [Coupon.ALL]
        cart_item_id = self.cart_item_id if self.cart_item_id else None

        if not user.is_authenticated:
            user = None

        if search_type == 'doctor':
            types.append(Coupon.DOCTOR)
        elif search_type == 'lab':
            types.append(Coupon.LAB)
        else:
            types.append(Coupon.DOCTOR)
            types.append(Coupon.LAB)

        user_opd_booked = Prefetch('opd_appointment_coupon',
                                   queryset=OpdAppointment.objects.filter(user=user)
                                                                  .exclude(status__in=[OpdAppointment.CANCELLED]),
                                                                           to_attr='user_opd_booked')

        user_lab_booked = Prefetch('lab_appointment_coupon',
                                   queryset=LabAppointment.objects.filter(user=user)
                                                                  .exclude(status__in=[LabAppointment.CANCELLED]),
                                                                           to_attr='user_lab_booked')

        all_coupons = Coupon.objects.filter(type__in=types)

        if coupon_code:
            all_coupons = RandomGeneratedCoupon.get_coupons([coupon_code])
        else:
            all_coupons = all_coupons.filter(is_visible=True)

        all_coupons = all_coupons.prefetch_related('user_specific_coupon', 'test', 'test_categories', 'hospitals',
                                                  'doctors', 'specializations', 'procedures',
                                                  'lab', 'test', user_opd_booked, user_lab_booked)

        if user and user.is_authenticated:
            all_coupons = all_coupons.filter(Q(is_user_specific=False) \
                                             | (Q(is_user_specific=True) & Q(user_specific_coupon__user=user)))

            is_first_time_user = OpdAppointment().is_user_first_time(user)
            if not is_first_time_user:
                all_coupons = all_coupons.filter(Q(new_user_constraint=False))

            if profile:
                if profile.gender:
                    all_coupons = all_coupons.filter(Q(gender__isnull=True) | Q(gender=profile.gender))
                else:
                    all_coupons = all_coupons.filter(gender__isnull=True)

                user_age = profile.get_age()
                if user_age:
                    all_coupons = all_coupons.filter(Q(age_start__isnull=True, age_end__isnull=True)
                                             | Q(age_start__lte=user_age, age_end__gte=user_age))
                else:
                    all_coupons = all_coupons.filter(age_start__isnull=True, age_end__isnull=True)
            else:
                all_coupons = all_coupons.filter(gender__isnull=True)
                all_coupons = all_coupons.filter(age_start__isnull=True, age_end__isnull=True)

            cart_items = None
            self.payment_option_filter = Cart.get_pg_if_pgcoupon(user, cart_items)
            user_cart_purchase_items = user.cart_item.filter(deleted_at__isnull=True).exclude(id=cart_item_id)

            for item in user_cart_purchase_items:
                if item.data and item.data.get('coupon_code'):
                    cart_code = item.data.get('coupon_code')[0]
                    if not cart_code in user_cart_counts:
                        user_cart_counts[cart_code] = 0
                    user_cart_counts[cart_code] += 1
        else:
            all_coupons = all_coupons.filter(Q(is_user_specific=False))

        if product_id:
            all_coupons = all_coupons.filter(is_corporate=False)

        all_coupons = list(set(all_coupons))

        return all_coupons

    def applicable_coupons(self, **filters):
        coupons = self.all_applicable_coupons
        user = self.user
        user_cart_counts = self.user_cart_counts
        search_type = self.type
        deal_price = filters.get('deal_price')
        tests = filters.get('tests')
        lab = filters.get('lab')
        hospital = filters.get('hospital')
        doctor_id = filters.get('doctor_id')
        doctor_specializations_ids = filters.get('doctor_specializations_ids', [])
        procedures_ids = filters.get('procedures_ids')
        show_all = filters.get('show_all', False)

        if deal_price:
            coupons = list(filter(lambda x: x.min_order_amount == None or x.min_order_amount <= deal_price, coupons))

        if search_type == 'doctor' or search_type == 'lab':
            if tests:
                tests_ids = []
                test_categories_ids = []
                categories_check = False
                for test in tests:
                    test_categories = []
                    test_id = getattr(test, 'id') if hasattr(test, 'id') else test.get('id')
                    if test_id:
                        tests_ids.append(test_id)

                    if hasattr(test, 'categories'):
                        categories = getattr(test, 'categories').all()
                        test_categories = list(map(lambda x: x.id, categories))
                        categories_check = True
                    if test_categories:
                        test_categories_ids = test_categories_ids + test_categories
                    else:
                        if not categories_check and test.get('categories'):
                            test_categories_ids.append(test.get('categories'))

                tests_ids = set(tests_ids)
                test_categories_ids = set(test_categories_ids)

                # check test in coupon
                for coupon in coupons:
                    keep_coupon = False
                    if len(coupon.test.all()) == 0:
                        keep_coupon = True
                    else:
                        if tests_ids:
                            coupon_test_ids = list(map(lambda x: x.id, coupon.test.all()))
                            for coupon_test_id in coupon_test_ids:
                                if coupon_test_id in tests_ids:
                                    keep_coupon = True
                                    break

                    if not keep_coupon:
                        coupons.remove(coupon)

                # check test categories in coupon
                for coupon in coupons:
                    keep_coupon = False
                    if len(coupon.test_categories.all()) == 0:
                        keep_coupon = True
                    else:
                        if test_categories_ids:
                            coupon_test_categories_ids = list(map(lambda x: x.id, coupon.test_categories.all()))
                            for coupon_test_categories_id in coupon_test_categories_ids:
                                if coupon_test_categories_id in test_categories_ids:
                                    keep_coupon = True
                                    break

                    if not keep_coupon:
                        coupons.remove(coupon)
            else:
                coupons = list(filter(lambda x: len(x.test.all()) == 0, coupons))
                coupons = list(filter(lambda x: len(x.test_categories.all()) == 0, coupons))

            if lab and lab.get('city'):
                coupons = list(filter(lambda x: x.cities == None or lab.get('city') in x.cities, coupons))
            else:
                coupons = list(filter(lambda x: x.cities == None, coupons))

            if hospital:
                hospital_id = getattr(hospital, 'id') if hasattr(hospital, 'id') else hospital.get('id')
                hospital_city = getattr(hospital, 'city') if hasattr(hospital, 'city') else hospital.get('city')
                coupons = list(
                    filter(lambda x: len(x.hospitals.all()) == 0 or hospital_id in list(map(lambda y: y.id, x.hospitals.all())), coupons))
                coupons = list(filter(lambda x: x.cities == None or hospital_city in x.cities, coupons))
            else:
                coupons = list(filter(lambda x: len(x.hospitals.all()) == 0, coupons))
                coupons = list(filter(lambda x: x.cities == None, coupons))

            if doctor_id:
                coupons = list(filter(lambda x: len(x.doctors.all()) == 0 or doctor_id in list(map(lambda y: y.id, x.doctors.all())), coupons))
                for coupon in coupons:
                    keep_coupon = False
                    if len(coupon.specializations.all()) == 0:
                        keep_coupon = True
                    else:
                        if doctor_specializations_ids:
                            coupon_specializations_ids = list(map(lambda x: x.id, coupon.specializations.all()))
                            for coupon_specializations_id in coupon_specializations_ids:
                                if coupon_specializations_id in doctor_specializations_ids:
                                    keep_coupon = True
                                    break

                    if not keep_coupon:
                        coupons.remove(coupon)
            else:
                coupons = list(filter(lambda x: len(x.doctors.all()) == 0, coupons))
                coupons = list(filter(lambda x: len(x.specializations.all()) == 0, coupons))


            if procedures_ids:
                pass
                # add filters here
                # coupons = coupons.filter(Q(procedures__isnull=True) | Q(procedures__in=procedures))
                # procedure_categories = set(procedures.values_list('categories', flat=True))
                # coupons = coupons.filter(
                #     Q(procedure_categories__isnull=True) | Q(procedure_categories__in=procedure_categories))
            else:
                coupons = list(filter(lambda x: len(x.procedures.all()) == 0, coupons))
                coupons = list(filter(lambda x: len(x.procedure_categories.all()) == 0, coupons))

        for coupon in coupons:
            coupon_properties = self.coupon_properties[coupon.code] = dict()
            remove_coupon = False
            if coupon.total_count and coupon.total_used_count >= coupon.total_count:
                remove_coupon = True

            used_coupon_count = 0
            if not remove_coupon and coupon.count:
                used_coupon_count = len(coupon.user_opd_booked) + len(coupon.user_lab_booked)
                if user_cart_counts.get(coupon.code):
                    used_coupon_count += user_cart_counts.get(coupon.code)

                if used_coupon_count >= coupon.count:
                    remove_coupon = True and not show_all
                    coupon_properties['valid'] = False
                    coupon_properties['invalidating_message'] = "Coupon can only be used " + str(coupon.count) + " times per user."
                coupon_properties['used_count'] = used_coupon_count

            if not remove_coupon and coupon.payment_option and self.payment_option_filter:
                if coupon.payment_option.id != self.payment_option_filter.id:
                    remove_coupon = True and not show_all
                    coupon_properties['valid'] = False
                    coupon_properties['invalidating_message'] = '2 payment gateway coupons cannot be used in the same transaction.'

            # TODO - old code
            # if ((user_opd_completed + user_lab_completed + 1) % coupon.step_count != 0 ):
            #     allowed = False

            # todo - move to cached condition with queryset
            if not remove_coupon and coupon.start_date and (coupon.start_date > timezone.now() \
                                                            or (coupon.start_date + datetime.timedelta(days=coupon.validity)) < timezone.now()):
                remove_coupon = True

            if not remove_coupon and coupon.is_user_specific and user:
                # todo - check if it will query to db
                if coupon.user_specific_coupon.exists():
                    user_specefic = coupon.user_specific_coupon.filter(user=user).first()
                    if user_specefic and (len(coupon.user_opd_booked)+len(coupon.user_lab_booked)) >= user_specefic.count:
                        remove_coupon = True

            if not remove_coupon and coupon.lab and lab and lab.get('id') and coupon.lab.id != lab.get('id'):
                remove_coupon = True

            if not remove_coupon and coupon.lab_network and lab and lab.get('network_id') and coupon.lab_network.id != lab.get('network_id'):
                remove_coupon = True

            if remove_coupon:
                coupons = list(filter(lambda x: x.id != coupon.id, coupons))

            # TODO add cart_item_id
            cart_item_id = None
            is_random_generated = False
            random_coupon_code = None
            if hasattr(coupon, 'is_random') and coupon.is_random:
                is_random_generated = True
                random_coupon_code = coupon.random_coupon_code
                random_count = coupon.random_coupon_used_count(user, coupon.random_coupon_code, cart_item_id)
                if random_count > 0:
                    coupon_properties['valid'] = False

            coupon_properties['is_random_generated'] = is_random_generated
            coupon_properties['random_coupon_code'] = random_coupon_code


        applicable_coupons = list(set(coupons))

        if applicable_coupons:
            from ondoc.api.v1.utils import CouponsMixin

            def compare_coupon(coupon):
                obj = CouponsMixin()
                deal_price = filters.get('deal_price')
                deal_price = deal_price if deal_price is not None else sys.maxsize
                discount = obj.get_discount(coupon, deal_price)
                return (1 if coupon.is_corporate else 0, discount)

            def filter_coupon(coupon):
                obj = CouponsMixin()
                deal_price = filters.get('deal_price')
                if deal_price:
                    discount = obj.get_discount(coupon, deal_price)
                    return discount > 0
                return True

            # sort coupons on discount granted
            applicable_coupons = sorted(applicable_coupons, key=compare_coupon, reverse=True)
            # filter if no discount is offered
            applicable_coupons = list(filter(filter_coupon, applicable_coupons))

            # def remove_coupon_data(c):
            #     c.pop('coupon')
            #     if c.get("payment_option"):
            #         c["payment_option"]["image"] = request.build_absolute_uri(c["payment_option"]["image"].url)
            #     return c
            # applicable_coupons = list(map(remove_coupon_data, applicable_coupons))

        return applicable_coupons

    def best_coupon(self, **filters):
        best_coupon = Coupon.objects.none()
        applicable_coupons = self.applicable_coupons(**filters)

        if applicable_coupons:
            def remove_invalid_coupon(coupon):
                coupon_property = self.get_coupon_properties(coupon.code)
                if coupon_property:
                    return coupon_property.get('valid', True)
                return True
            applicable_coupons = list(filter(remove_invalid_coupon, applicable_coupons))

            applicable_coupons = list(filter(lambda x: x.coupon_type == Coupon.DISCOUNT, applicable_coupons))

            best_coupon = applicable_coupons[0]

        return best_coupon

    def get_coupon_properties(self, code):
        coupon_property = None
        if code:
            coupon_property = self.coupon_properties[code]
        return coupon_property