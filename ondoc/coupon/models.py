from django.db import models
from ondoc.authentication import models as auth_model
from ondoc.common.models import PaymentOptions
from django.core.validators import MaxValueValidator, MinValueValidator
import datetime
from django.utils.crypto import get_random_string
import logging

from ondoc.corporate_booking.models import CorporateDeal

logger = logging.getLogger(__name__)


class Coupon(auth_model.TimeStampedModel):
    DOCTOR = 1
    LAB = 2
    ALL = 3

    DISCOUNT = 1
    CASHBACK = 2

    TYPE_CHOICES = (("", "Select"), (DOCTOR, "Doctor"), (LAB, "Lab"), (ALL, "All"),)
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
    corporate_deal = models.ForeignKey(CorporateDeal, on_delete=models.SET_NULL, null=True, blank=True)

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

        count += Cart.objects.filter(user=user, deleted_at__isnull=True, data__coupon_code__contains=self.code).exclude(id=cart_item).count()
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
        discount_coupon_list = []
        cashback_coupon_list = []

        coupon_discount = 0
        coupon_cashback = 0

        if data.get("coupon_code"):
            coupon_obj = cls.objects.filter(code__in=set(data.get("coupon_code")))
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

        return coupon_discount, coupon_cashback, coupon_list

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
    user = models.ForeignKey(auth_model.User, on_delete=models.CASCADE)
    sent_at = models.DateTimeField(default=None, null=True, blank=True)
    consumed_at = models.DateTimeField(default=None, null=True, blank=True)
    validity = models.PositiveIntegerField(default=None)

    def __str__(self):
        return self.random_coupon

    class Meta:
        db_table = "random_generated_coupon"

