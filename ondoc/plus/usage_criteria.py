from .enums import UsageCriteria
from math import floor


class AbstractCriteria(object):
    def __init__(self, plus_obj):
        self.plus_obj = plus_obj
        self.plus_plan = plus_obj.plan
        self.utilization = plus_obj.get_utilization

    def _validate_booking_entity(self, cost, id):
        raise NotImplementedError()

    def validate_booking_entity(self, *args, **kwargs):
        cost = kwargs.get('cost')
        id = kwargs.get('id')
        if not cost:
            return {}

        return self._validate_booking_entity(cost, id)

    def after_discount_cost(self, discount, cost):
        cost = cost - ((cost/100) * discount)
        cost = floor(cost)
        return cost

    def discounted_cost(self, discount, cost):
        return ((cost/100) * discount)


class DoctorAmountCount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        available_amount = self.utilization.get('doctor_amount_available', 0)
        available_count = self.utilization.get('available_doctor_count', 0)
        if available_count <= 0 and available_amount <= 0:
            return resp

        if available_count > 0:
            vip_amount_deducted = cost
            amount_to_be_paid = 0
            is_covered = True
        elif available_count <= 0 and available_amount > 0:
            if available_amount > cost:
                vip_amount_deducted = cost
                amount_to_be_paid = 0
                is_covered = True
            else:
                vip_amount_deducted = available_amount
                amount_to_be_paid = cost - available_amount
                is_covered = True

        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered

        return resp


class DoctorCountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self,cost, id):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        available_count = self.utilization.get('available_doctor_count')
        if available_count <= 0:
            return resp

        doctor_discount = self.utilization.get('doctor_discount')

        discounted_cost = self.discounted_cost(doctor_discount, cost)
        after_discounted_cost = cost - discounted_cost
        vip_amount_deducted = discounted_cost
        amount_to_be_paid = after_discounted_cost
        is_covered = True

        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered

        return resp


class DoctorAmountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        available_amount = self.utilization.get('doctor_amount_available')
        if available_amount <= 0:
            return resp

        doctor_discount = self.utilization.get('doctor_discount')

        discounted_cost = self.discounted_cost(doctor_discount, cost)
        after_discounted_cost = cost - discounted_cost

        if discounted_cost <= available_amount:
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = after_discounted_cost
            is_covered = True
        elif 0 < available_amount < discounted_cost:
            vip_amount_deducted = available_amount
            amount_to_be_paid = cost - available_amount
            is_covered = True

        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered

        return resp


class LabtestAmountCount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        pass


class LabtestCountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        pass


class LabtestAmountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        available_amount = self.utilization.get('available_labtest_amount')
        if available_amount <= 0:
            return resp

        lab_test_discount = self.utilization.get('lab_discount')

        discounted_cost = self.discounted_cost(lab_test_discount, cost)
        after_discounted_cost =cost - discounted_cost

        if discounted_cost <= available_amount:
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = after_discounted_cost
            is_covered = True
        elif 0 < available_amount < discounted_cost:
            vip_amount_deducted = available_amount
            amount_to_be_paid = cost - available_amount
            is_covered = True

        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered

        return resp


class PackageAmountCount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        pass


class PackageCountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        pass


class PackageAmountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _validate_booking_entity(self, cost, id):
        pass


usage_criteria_class_mapping = {
    'DOCTOR': {
        'AMOUNT_COUNT': DoctorAmountCount,
        'COUNT_DISCOUNT': DoctorCountDiscount,
        'AMOUNT_DISCOUNT': DoctorAmountDiscount
    },
    'LABTEST': {
        'AMOUNT_COUNT': LabtestAmountCount,
        'COUNT_DISCOUNT': LabtestCountDiscount,
        'AMOUNT_DISCOUNT': LabtestAmountDiscount
    },
    'PACKAGE': {
        'AMOUNT_COUNT': PackageAmountCount,
        'COUNT_DISCOUNT': PackageCountDiscount,
        'AMOUNT_DISCOUNT': PackageAmountDiscount
    }
}


def get_class_reference(plus_membership_obj, entity):
    if not plus_membership_obj:
        return None

    usage_criteria = plus_membership_obj.plan.plan_criteria
    if entity not in ['DOCTOR', 'LABTEST', 'PACKAGE'] or usage_criteria not in UsageCriteria.availabilities():
        return None

    class_reference = usage_criteria_class_mapping[entity][usage_criteria]
    return class_reference(plus_membership_obj)



