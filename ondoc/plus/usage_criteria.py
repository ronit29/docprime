from .enums import UsageCriteria, PriceCriteria
from math import floor


class AbstractCriteria(object):
    def __init__(self, plus_obj, plan=None):
        if plus_obj.__class__.__name__ == 'PlusUser':
            self.plus_obj = plus_obj
        elif plus_obj.__class__.__name__ == 'TempPlusUser':
            self.plus_obj = plus_obj
        else:
            self.plus_obj = None
        # self.plus_obj = plus_obj if plus_obj.__class__.__name__ == 'PlusUser' else None
        self.plus_plan = plus_obj.plan if plus_obj.__class__.__name__ in ['PlusUser', 'TempPlusUser'] else plan
        self.utilization = plus_obj.get_utilization if plus_obj.__class__.__name__ in ['PlusUser', 'TempPlusUser'] else {}

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        raise NotImplementedError()

    def validate_booking_entity(self, *args, **kwargs):
        cost = kwargs.get('cost')
        id = kwargs.get('id')
        mrp = kwargs.get('mrp')
        deal_price = kwargs.get('deal_price')
        utilization = kwargs.get('utilization')
        price_engine_price = kwargs.get('price_engine_price')
        calculated_convenience_amount = kwargs.get('calculated_convenience_amount')
        if cost is None or cost < 0:
            return {}

        return self._validate_booking_entity(cost, id, utilization=utilization, mrp=mrp, deal_price=deal_price, price_engine_price=price_engine_price, calculated_convenience_amount=calculated_convenience_amount)

    def _update_utilization(self, utilization, deduction_amount):
        raise NotImplementedError()

    def update_utilization(self, utilization, deduction_amount):
        return self._update_utilization(utilization, deduction_amount)

    def _get_price(self, price_data):
        raise NotImplementedError()

    def get_price(self, price_data):
        return self._get_price(price_data)

    def after_discount_cost(self, discount, cost):
        cost = cost - ((cost/100) * discount)
        cost = floor(cost)
        return cost

    def discounted_cost(self, discount, cost, max_discount, min_discount):
        final_discount = (cost / 100) * discount
        if max_discount and max_discount > 0 and final_discount > max_discount:
            final_discount = max_discount
        if min_discount and min_discount > 0 and final_discount < min_discount:
            final_discount = min_discount
        return final_discount


class ConvenienceAbstractCriteria(object):
    def __init__(self, plus_plan):
        self.plus_plan = plus_plan

    def _get_price(self, price_data):
        raise NotImplementedError()

    def get_price(self, price_data):
        return self._get_price(price_data)


class CorporateAbstractCriteria(object):
    def __init__(self, plus_obj):
        self.plus_obj = plus_obj

    def _get_price(self, price_data):
        raise NotImplementedError()

    def get_price(self, price_data):
        return self._get_price(price_data)


class DoctorAmountCount(AbstractCriteria):

    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):

        utilization['doctor_amount_available'] = int(utilization['doctor_amount_available']) - int(deducted_amount)
        utilization['available_doctor_count'] = int(utilization['available_doctor_count']) - 1

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        from ondoc.plus.models import PlusPlans

        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost, 'convenience_charge': 0}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('doctor_amount_available', 0)
        available_count = vip_utilization.get('available_doctor_count', 0)
        total_doctor_count = vip_utilization.get('total_doctor_count_limit', 0)
        mrp = kwargs.get('mrp', 0)
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        # min_price_engine = get_min_convenience_reference(self.plus_obj, "DOCTOR")
        # min_price = min_price_engine.get_price(price_data)
        # max_price_engine = get_max_convenience_reference(self.plus_obj, "DOCTOR")
        # max_price = max_price_engine.get_price(price_data)
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get('calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and total_cost >= deal_price:
            return resp

        if not total_doctor_count and not available_amount and available_count:
            return resp

        if (total_doctor_count <= 0 and available_amount > 0) or (total_doctor_count > 0 and available_count > 0
                                                                  and available_amount > 0):
            if plan.is_corporate:
                corporate_cost_engine = get_corporate_price_reference(self.plus_obj, "DOCTOR")
                if not corporate_cost_engine:
                    return resp
                cost = corporate_cost_engine.get_price(price_data)
                upper_limit = int(plan.corporate_doctor_upper_limit)
                if upper_limit < cost:
                    return resp
                if available_amount >= cost:
                    vip_amount_deducted = cost
                    amount_to_be_paid = 0
                    is_covered = True
                else:
                    vip_amount_deducted = int(available_amount)
                    amount_to_be_paid = int(cost - available_amount)
                    is_covered = True
            else:
                if not plan.is_gold:
                    if available_amount >= cost:
                        vip_amount_deducted = cost
                        amount_to_be_paid = 0
                        is_covered = True
                    else:
                        vip_amount_deducted = int(available_amount)
                        amount_to_be_paid = int(cost - available_amount)
                        is_covered = True
                else:
                    difference_amount = int(mrp - cost)
                    if available_amount >= difference_amount:
                        vip_amount_deducted = difference_amount
                        amount_to_be_paid = cost
                        is_covered = True
                    else:
                        vip_amount_deducted = int(available_amount)
                        amount_to_be_paid = cost + (int(difference_amount) - int(available_amount))
                        is_covered = True
        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered
        resp['convenience_charge'] = convenience_charge

        return resp


class DoctorCountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['available_doctor_count'] = utilization['available_doctor_count'] - 1

    def _validate_booking_entity(self,cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization

        available_count = vip_utilization.get('available_doctor_count')
        if available_count <= 0:
            return resp

        doctor_discount = vip_utilization.get('doctor_discount')
        max_discount = vip_utilization.get('doctor_max_discounted_amount')
        min_discount = vip_utilization.get('doctor_min_discounted_amount')

        discounted_cost = self.discounted_cost(doctor_discount, cost, max_discount, min_discount)
        after_discounted_cost = cost - discounted_cost
        vip_amount_deducted = discounted_cost
        amount_to_be_paid = after_discounted_cost
        is_covered = True

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered

        return resp


class DoctorAmountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['doctor_amount_available'] = utilization['doctor_amount_available'] - deducted_amount

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('doctor_amount_available')
        if available_amount <= 0:
            return resp

        doctor_discount = vip_utilization.get('doctor_discount')
        max_discount = vip_utilization.get('doctor_max_discounted_amount')
        min_discount = vip_utilization.get('doctor_min_discounted_amount')

        discounted_cost = self.discounted_cost(doctor_discount, cost, max_discount, min_discount)
        after_discounted_cost = cost - discounted_cost

        if discounted_cost <= available_amount:
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = after_discounted_cost
            is_covered = True
        elif 0 < available_amount < discounted_cost:
            vip_amount_deducted = available_amount
            amount_to_be_paid = cost - available_amount
            is_covered = True

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered

        return resp


class LabtestAmountCount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):

        utilization['available_labtest_amount'] = utilization['available_labtest_amount'] - deducted_amount
        utilization['available_labtest_count'] = utilization['available_labtest_count'] - 1

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        from ondoc.plus.models import PlusPlans

        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        vip_amount_deducted = 0
        cost = int(cost)
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        total_count_left = vip_utilization.get('available_labtest_count')
        total_amount_left = vip_utilization.get('available_labtest_amount')
        total_count = vip_utilization.get('total_labtest_count_limit')
        total_amount = vip_utilization.get('total_labtest_amount_limit')
        mrp = kwargs.get('mrp', 0)
        is_covered = False
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_engine_price = int(kwargs.get('price_engine_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        # min_price_engine = get_min_convenience_reference(self.plus_obj, "LABTEST")
        # min_price = min_price_engine.get_price(price_data)
        # max_price_engine = get_max_convenience_reference(self.plus_obj, "LABTEST")
        # max_price = max_price_engine.get_price(price_data)
        # convenience_charge = plan.get_convenience_charge(max_price, min_price, "LABTEST")
        # convenience_charge = plan.get_convenience_charge(cost, "LABTEST")
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get('calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and (price_engine_price + convenience_charge) >= deal_price:
            return resp

        if not total_count_left and not total_amount_left:
            return resp

        if (total_count <= 0 and total_amount_left > 0) or (total_count > 0 and total_count_left > 0 and total_amount_left > 0):
            is_covered = True
            if plan.is_corporate:
                corporate_cost_engine = get_corporate_price_reference(self.plus_obj, "LABTEST")
                if not corporate_cost_engine:
                    return resp
                cost = corporate_cost_engine.get_price(price_data)
                upper_limit = int(plan.corporate_lab_upper_limit)
                if upper_limit < cost:
                    return resp
                if total_amount_left >= cost:
                    vip_amount_deducted = cost
                    amount_to_be_paid = 0
                    is_covered = True
                else:
                    vip_amount_deducted = int(total_amount_left)
                    amount_to_be_paid = int(cost - total_amount_left)
                    is_covered = True
            else:
                if not plan.is_gold:
                    if cost <= total_amount_left:
                        vip_amount_deducted = cost
                        amount_to_be_paid = 0
                    elif 0 < total_amount_left < cost:
                        vip_amount_deducted = total_amount_left
                        amount_to_be_paid = cost - total_amount_left
                else:
                    difference_amount = mrp - cost
                    if difference_amount <= total_amount_left:
                        vip_amount_deducted = difference_amount
                        amount_to_be_paid = cost
                    elif 0 < total_amount_left < difference_amount:
                        vip_amount_deducted = total_amount_left
                        amount_to_be_paid = cost + (difference_amount - total_amount_left)

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        return resp


class LabtestCountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['available_labtest_count'] = utilization['available_labtest_count'] - 1

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization

        available_labtest_count = vip_utilization.get('available_labtest_count')
        lab_test_discount = vip_utilization.get('lab_discount')
        max_discount = vip_utilization.get('lab_max_discounted_amount')
        min_discount = vip_utilization.get('lab_min_discounted_amount')

        if available_labtest_count > 0:
            discounted_cost = self.discounted_cost(lab_test_discount, cost, max_discount, min_discount)
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = cost - discounted_cost
            is_covered = True

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        return resp


class LabtestAmountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['available_labtest_amount'] = utilization['available_labtest_amount'] - deducted_amount

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('available_labtest_amount')
        if available_amount <= 0:
            return resp

        lab_test_discount = vip_utilization.get('lab_discount')
        max_discount = vip_utilization.get('lab_max_discounted_amount')
        min_discount = vip_utilization.get('lab_min_discounted_amount')

        discounted_cost = self.discounted_cost(lab_test_discount, cost, max_discount, min_discount)
        after_discounted_cost =cost - discounted_cost

        if discounted_cost <= available_amount:
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = after_discounted_cost
            is_covered = True
        elif 0 < available_amount < discounted_cost:
            vip_amount_deducted = available_amount
            amount_to_be_paid = cost - available_amount
            is_covered = True

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered

        return resp


class PackageAmountCount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['available_package_amount'] = utilization['available_package_amount'] - deducted_amount
        utilization['available_package_count'] = utilization['available_package_count'] - 1

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        from ondoc.plus.models import PlusPlans

        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        mrp = kwargs.get('mrp', 0)
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        price_engine_price = int(kwargs.get('price_engine_price', 0))
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get('calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and (price_engine_price + convenience_charge) >= deal_price:
            return resp
        if plan.is_corporate:
            return resp

        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization

        available_package_amount = vip_utilization.get('available_package_amount')
        available_package_count = vip_utilization.get('available_package_count')
        allowed_package_ids = vip_utilization.get('allowed_package_ids')
        total_count = vip_utilization.get('total_package_count_limit')

        if not available_package_count and not available_package_amount:
            return resp

        # if available_package_amount <= 0 or available_package_count <= 0:
        #     return resp

        if (total_count <= 0 and available_package_amount > 0) or (total_count > 0 and available_package_count > 0 and available_package_amount > 0):

            if not plan.is_gold:
                if allowed_package_ids:
                    if id in allowed_package_ids:
                        is_covered = True
                        if cost <= available_package_amount:
                            vip_amount_deducted = cost
                            amount_to_be_paid = 0
                        elif 0 < available_package_amount < cost:
                            vip_amount_deducted = available_package_amount
                            amount_to_be_paid = cost - available_package_amount
                    else:
                        return resp
                else:
                    is_covered = True
                    if cost <= available_package_amount:
                        vip_amount_deducted = cost
                        amount_to_be_paid = 0
                    elif 0 < available_package_amount < cost:
                        vip_amount_deducted = available_package_amount
                        amount_to_be_paid = cost - available_package_amount
            else:
                difference_amount = int(mrp - cost)
                if allowed_package_ids:
                    if id in allowed_package_ids:
                        is_covered = True
                        if cost <= available_package_amount:
                            vip_amount_deducted = difference_amount
                            amount_to_be_paid = cost
                        elif 0 < available_package_amount < cost:
                            vip_amount_deducted = available_package_amount
                            amount_to_be_paid = cost + (difference_amount - available_package_amount)
                    else:
                        return resp
                else:
                    is_covered = True
                    if cost <= available_package_amount:
                        vip_amount_deducted = difference_amount
                        amount_to_be_paid = cost
                    elif 0 < available_package_amount < cost:
                        vip_amount_deducted = available_package_amount
                        amount_to_be_paid = cost + (difference_amount - available_package_amount)

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        return resp


class PackageCountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['available_package_count'] = utilization['available_package_count'] - 1

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization

        available_package_discount = vip_utilization.get('package_discount')
        available_package_count = vip_utilization.get('available_package_count')
        allowed_package_ids = vip_utilization.get('allowed_package_ids')
        max_discount = vip_utilization.get('package_max_discounted_amount')
        min_discount = vip_utilization.get('package_min_discounted_amount')

        if not available_package_count or not available_package_discount:
            return resp

        if available_package_count > 0:
            if allowed_package_ids:
                if id in allowed_package_ids:
                    discounted_cost = self.discounted_cost(available_package_discount, cost, max_discount, min_discount)
                    vip_amount_deducted = discounted_cost
                    amount_to_be_paid = cost - discounted_cost
                    is_covered = True

                else:
                    return resp
            else:
                discounted_cost = self.discounted_cost(available_package_discount, cost, max_discount, min_discount)
                vip_amount_deducted = discounted_cost
                amount_to_be_paid = cost - discounted_cost
                is_covered = True

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        return resp


class PackageAmountDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        utilization['available_package_amount'] = utilization['available_package_amount'] - deducted_amount

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('available_package_amount')
        if available_amount <= 0:
            return resp

        package_discount = vip_utilization.get('package_discount')
        max_discount = vip_utilization.get('package_max_discounted_amount')
        min_discount = vip_utilization.get('package_min_discounted_amount')

        discounted_cost = self.discounted_cost(package_discount, cost, max_discount, min_discount)
        after_discounted_cost = cost - discounted_cost

        if discounted_cost <= available_amount:
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = after_discounted_cost
            is_covered = True
        elif 0 < available_amount < discounted_cost:
            vip_amount_deducted = available_amount
            amount_to_be_paid = cost - available_amount
            is_covered = True

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered

        return resp


class PackageTotalWorth(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        # utilization['available_package_amount'] = utilization['available_package_amount'] - deducted_amount
        utilization['available_total_worth'] = int(utilization['available_total_worth']) - int(deducted_amount)

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization

        available_package_amount = vip_utilization.get('available_total_worth')
        allowed_package_ids = vip_utilization.get('allowed_package_ids')
        is_package_cover = vip_utilization.get('is_package_cover')

        if not available_package_amount or available_package_amount <= 0 or not is_package_cover:
            return resp

        if allowed_package_ids:
            if id in allowed_package_ids:
                is_covered = True
                if cost <= available_package_amount:
                    vip_amount_deducted = cost
                    amount_to_be_paid = 0
                elif 0 < available_package_amount < cost:
                    vip_amount_deducted = available_package_amount
                    amount_to_be_paid = cost - available_package_amount
            else:
                return resp
        else:
            is_covered = True
            if cost <= available_package_amount:
                vip_amount_deducted = cost
                amount_to_be_paid = 0
            elif 0 < available_package_amount < cost:
                vip_amount_deducted = available_package_amount
                amount_to_be_paid = cost - available_package_amount

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        return resp


class DoctorTotalWorth(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):

        utilization['available_total_worth'] = int(utilization['available_total_worth']) - int(deducted_amount)

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost, 'convenience_charge': 0}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('available_total_worth', 0)
        mrp = kwargs.get('mrp', 0)
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get(
            'calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and total_cost >= deal_price:
            return resp

        if not available_amount or available_amount <= 0:
            return resp

        if plan.is_corporate:
            corporate_cost_engine = get_corporate_price_reference(self.plus_obj, "DOCTOR")
            if not corporate_cost_engine:
                return resp
            cost = corporate_cost_engine.get_price(price_data)
            upper_limit = int(plan.corporate_doctor_upper_limit)
            if upper_limit < cost:
                return resp
            if available_amount >= cost:
                vip_amount_deducted = cost
                amount_to_be_paid = 0
                is_covered = True
            else:
                vip_amount_deducted = int(available_amount)
                amount_to_be_paid = int(cost - available_amount)
                is_covered = True
        else:
            if not plan.is_gold:
                if available_amount >= cost:
                    vip_amount_deducted = cost
                    amount_to_be_paid = 0
                    is_covered = True
                else:
                    vip_amount_deducted = int(available_amount)
                    amount_to_be_paid = int(cost - available_amount)
                    is_covered = True
            else:
                difference_amount = int(mrp - cost)
                if available_amount >= difference_amount:
                    vip_amount_deducted = difference_amount
                    amount_to_be_paid = cost
                    is_covered = True
                else:
                    vip_amount_deducted = int(available_amount)
                    amount_to_be_paid = cost + (int(difference_amount) - int(available_amount))
                    is_covered = True
        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered
        resp['convenience_charge'] = convenience_charge
        return resp


class LabtestTotalWorth(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):

        utilization['available_total_worth'] = utilization['available_total_worth'] - deducted_amount

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        vip_amount_deducted = 0
        cost = int(cost)
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        total_amount_left = vip_utilization.get('available_total_worth')
        mrp = kwargs.get('mrp', 0)
        is_covered = False
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get(
            'calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and total_cost >= deal_price:
            return resp

        if not total_amount_left or total_amount_left <= 0:
            return resp

        is_covered = True
        if plan.is_corporate:
            corporate_cost_engine = get_corporate_price_reference(self.plus_obj, "LABTEST")
            if not corporate_cost_engine:
                return resp
            cost = corporate_cost_engine.get_price(price_data)
            upper_limit = int(plan.corporate_lab_upper_limit)
            if upper_limit < cost:
                return resp
            if total_amount_left >= cost:
                vip_amount_deducted = cost
                amount_to_be_paid = 0
                is_covered = True
            else:
                vip_amount_deducted = int(total_amount_left)
                amount_to_be_paid = int(cost - total_amount_left)
                is_covered = True
        else:
            if not plan.is_gold:
                if cost <= total_amount_left:
                    vip_amount_deducted = cost
                    amount_to_be_paid = 0
                elif 0 < total_amount_left < cost:
                    vip_amount_deducted = total_amount_left
                    amount_to_be_paid = cost - total_amount_left
            else:
                difference_amount = mrp - cost
                if difference_amount <= total_amount_left:
                    vip_amount_deducted = difference_amount
                    amount_to_be_paid = cost
                elif 0 < total_amount_left < difference_amount:
                    vip_amount_deducted = total_amount_left
                    amount_to_be_paid = cost + (difference_amount - total_amount_left)

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        return resp


class PackageTotalWorthWithDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):
        # utilization['available_package_amount'] = utilization['available_package_amount'] - deducted_amount
        utilization['available_total_worth'] = int(utilization['available_total_worth']) - int(deducted_amount)

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization

        available_amount = vip_utilization.get('available_total_worth')
        allowed_package_ids = vip_utilization.get('allowed_package_ids')
        is_package_cover = vip_utilization.get('is_package_cover')

        if not available_amount or available_amount <= 0 or not is_package_cover:
            return resp

        package_discount = vip_utilization.get('package_discount')
        max_discount = vip_utilization.get('package_max_discounted_amount')
        min_discount = vip_utilization.get('package_min_discounted_amount')

        discounted_cost = self.discounted_cost(package_discount, cost, max_discount, min_discount)
        after_discounted_cost = cost - discounted_cost

        if allowed_package_ids:
            if id in allowed_package_ids:
                if discounted_cost <= available_amount:
                    vip_amount_deducted = discounted_cost
                    amount_to_be_paid = after_discounted_cost
                    is_covered = True
                elif 0 < available_amount < discounted_cost:
                    vip_amount_deducted = available_amount
                    amount_to_be_paid = cost - available_amount
                    is_covered = True
            else:
                return resp
        else:
            if discounted_cost <= available_amount:
                vip_amount_deducted = discounted_cost
                amount_to_be_paid = after_discounted_cost
                is_covered = True
            elif 0 < available_amount < discounted_cost:
                vip_amount_deducted = available_amount
                amount_to_be_paid = cost - available_amount
                is_covered = True
        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered

        return resp


class DoctorTotalWorthWithDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):

        utilization['available_total_worth'] = int(utilization['available_total_worth']) - int(deducted_amount)

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost, 'convenience_charge': 0}
        is_covered = False
        vip_amount_deducted = 0
        amount_to_be_paid = cost

        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('available_total_worth', 0)
        mrp = kwargs.get('mrp', 0)
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get(
            'calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and total_cost >= deal_price:
            return resp

        if not available_amount or available_amount <= 0:
            return resp

        doctor_discount = vip_utilization.get('doctor_discount')
        max_discount = vip_utilization.get('doctor_max_discounted_amount')
        min_discount = vip_utilization.get('doctor_min_discounted_amount')

        discounted_cost = self.discounted_cost(doctor_discount, cost, max_discount, min_discount)
        after_discounted_cost = cost - discounted_cost

        if plan.is_corporate:
            corporate_cost_engine = get_corporate_price_reference(self.plus_obj, "DOCTOR")
            if not corporate_cost_engine:
                return resp
            cost = corporate_cost_engine.get_price(price_data)
            upper_limit = int(plan.corporate_doctor_upper_limit)
            if upper_limit < cost:
                return resp
            if discounted_cost <= available_amount:
                vip_amount_deducted = discounted_cost
                amount_to_be_paid = after_discounted_cost
                is_covered = True
            elif 0 < available_amount < discounted_cost:
                vip_amount_deducted = available_amount
                amount_to_be_paid = cost - available_amount
                is_covered = True
        else:
            if not plan.is_gold:
                if discounted_cost <= available_amount:
                    vip_amount_deducted = discounted_cost
                    amount_to_be_paid = after_discounted_cost
                    is_covered = True
                elif 0 < available_amount < discounted_cost:
                    vip_amount_deducted = available_amount
                    amount_to_be_paid = cost - available_amount
                    is_covered = True
            else:
                difference_amount = int(mrp - cost)
                if available_amount >= difference_amount:
                    vip_amount_deducted = difference_amount
                    amount_to_be_paid = cost
                    is_covered = True
                else:
                    vip_amount_deducted = int(available_amount)
                    amount_to_be_paid = cost + (int(difference_amount) - int(available_amount))
                    is_covered = True

        resp['vip_amount_deducted'] = vip_amount_deducted
        resp['amount_to_be_paid'] = amount_to_be_paid
        resp['is_covered'] = is_covered
        resp['convenience_charge'] = convenience_charge
        return resp


class LabtestTotalWorthWithDiscount(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _update_utilization(self, utilization, deducted_amount):

        utilization['available_total_worth'] = utilization['available_total_worth'] - deducted_amount

    def _validate_booking_entity(self, cost, id, *args, **kwargs):
        resp = {'vip_amount_deducted': 0, 'is_covered': False, 'amount_to_be_paid': cost}
        vip_amount_deducted = 0
        cost = int(cost)
        amount_to_be_paid = cost
        vip_utilization = kwargs.get('utilization') if kwargs.get('utilization') else self.utilization
        available_amount = vip_utilization.get('available_total_worth')
        mrp = kwargs.get('mrp', 0)
        is_covered = False
        plan = self.plus_obj.plan
        deal_price = int(kwargs.get('deal_price', 0))
        price_data = {"mrp": mrp, "deal_price": deal_price, "fees": cost, "cod_deal_price": deal_price}
        convenience_charge = kwargs.get('calculated_convenience_amount', 0) if kwargs.get(
            'calculated_convenience_amount') else 0
        total_cost = cost + convenience_charge
        if plan.is_gold and total_cost >= deal_price:
            return resp

        if not available_amount or available_amount <= 0:
            return resp

        lab_test_discount = vip_utilization.get('lab_discount')
        max_discount = vip_utilization.get('lab_max_discounted_amount')
        min_discount = vip_utilization.get('lab_min_discounted_amount')

        discounted_cost = self.discounted_cost(lab_test_discount, cost, max_discount, min_discount)
        after_discounted_cost = cost - discounted_cost

        if discounted_cost <= available_amount:
            vip_amount_deducted = discounted_cost
            amount_to_be_paid = after_discounted_cost
            is_covered = True
        elif 0 < available_amount < discounted_cost:
            vip_amount_deducted = available_amount
            amount_to_be_paid = cost - available_amount
            is_covered = True

        is_covered = True
        if plan.is_corporate:
            corporate_cost_engine = get_corporate_price_reference(self.plus_obj, "LABTEST")
            if not corporate_cost_engine:
                return resp
            cost = corporate_cost_engine.get_price(price_data)
            upper_limit = int(plan.corporate_lab_upper_limit)
            if upper_limit < cost:
                return resp
            if discounted_cost <= available_amount:
                vip_amount_deducted = discounted_cost
                amount_to_be_paid = after_discounted_cost
                is_covered = True
            elif 0 < available_amount < discounted_cost:
                vip_amount_deducted = available_amount
                amount_to_be_paid = cost - available_amount
                is_covered = True
        else:
            if not plan.is_gold:
                if discounted_cost <= available_amount:
                    vip_amount_deducted = discounted_cost
                    amount_to_be_paid = after_discounted_cost
                    is_covered = True
                elif 0 < available_amount < discounted_cost:
                    vip_amount_deducted = available_amount
                    amount_to_be_paid = cost - available_amount
                    is_covered = True
            else:
                difference_amount = mrp - cost
                if difference_amount <= available_amount:
                    vip_amount_deducted = difference_amount
                    amount_to_be_paid = cost
                elif 0 < available_amount < difference_amount:
                    vip_amount_deducted = available_amount
                    amount_to_be_paid = cost + (difference_amount - available_amount)

        resp['vip_amount_deducted'] = int(vip_amount_deducted)
        resp['amount_to_be_paid'] = int(amount_to_be_paid)
        resp['is_covered'] = is_covered
        resp['convenience_charge'] = convenience_charge
        return resp


usage_criteria_class_mapping = {
    'DOCTOR': {
        'AMOUNT_COUNT': DoctorAmountCount,
        'COUNT_DISCOUNT': DoctorCountDiscount,
        'AMOUNT_DISCOUNT': DoctorAmountDiscount,
        'TOTAL_WORTH': DoctorTotalWorth,
        'TOTAL_WORTH_WITH_DISCOUNT': DoctorTotalWorthWithDiscount
    },
    'LABTEST': {
        'AMOUNT_COUNT': LabtestAmountCount,
        'COUNT_DISCOUNT': LabtestCountDiscount,
        'AMOUNT_DISCOUNT': LabtestAmountDiscount,
        'TOTAL_WORTH': LabtestTotalWorth,
        'TOTAL_WORTH_WITH_DISCOUNT': LabtestTotalWorthWithDiscount
    },
    'PACKAGE': {
        'AMOUNT_COUNT': PackageAmountCount,
        'COUNT_DISCOUNT': PackageCountDiscount,
        'AMOUNT_DISCOUNT': PackageAmountDiscount,
        'TOTAL_WORTH': PackageTotalWorth,
        'TOTAL_WORTH_WITH_DISCOUNT': PackageTotalWorthWithDiscount
    }
}


class DoctorMrp(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('mrp', 0)


class DoctorDealPrice(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class DoctorAgreedPrice(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('fees', 0)


class DoctorCodDealPrice(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('cod_deal_price', 0)


class LabtestMrp(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('mrp', 0)


class LabtestDealPrice(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class LabtestAgreedPrice(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('fees', 0)


class LabtestCodDealPrice(AbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class ConvenienceDoctorMrp(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('mrp', 0)


class ConvenienceDoctorDealPrice(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class ConvenienceDoctorAgreedPrice(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('fees', 0)


class ConvenienceDoctorCodDealPrice(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('cod_deal_price', 0)


class ConvenienceLabtestMrp(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('mrp', 0)


class ConvenienceLabtestDealPrice(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class ConvenienceLabtestAgreedPrice(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('fees', 0)


class ConvenienceLabtestCodDealPrice(ConvenienceAbstractCriteria):
    def __init__(self, plus_plan):
        super().__init__(plus_plan)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class CorporateDoctorMrp(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('mrp', 0)


class CorporateDoctorDealPrice(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class CorporateDoctorAgreedPrice(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('fees', 0)


class CorporateDoctorCodDealPrice(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('cod_deal_price', 0)


class CorporateLabtestMrp(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('mrp', 0)


class CorporateLabtestDealPrice(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


class CorporateLabtestAgreedPrice(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('fees', 0)


class CorporateLabtestCodDealPrice(CorporateAbstractCriteria):
    def __init__(self, plus_obj):
        super().__init__(plus_obj)

    def _get_price(self, price_data):
        if not price_data:
            return None
        return price_data.get('deal_price', 0)


price_criteria_class_mapping = {
    'DOCTOR': {
        'MRP': DoctorMrp,
        'DEAL_PRICE': DoctorDealPrice,
        'AGREED_PRICE': DoctorAgreedPrice,
        'COD_DEAL_PRICE': DoctorCodDealPrice
    },
    'LABTEST': {
        'MRP': LabtestMrp,
        'DEAL_PRICE': LabtestDealPrice,
        'AGREED_PRICE': LabtestAgreedPrice,
        'COD_DEAL_PRICE': LabtestCodDealPrice
    }
}

convenience_price_criteria_class_mapping = {
    'DOCTOR': {
        'MRP': ConvenienceDoctorMrp,
        'DEAL_PRICE': ConvenienceDoctorDealPrice,
        'AGREED_PRICE': ConvenienceDoctorAgreedPrice,
        'COD_DEAL_PRICE': ConvenienceDoctorCodDealPrice
    },
    'LABTEST': {
        'MRP': ConvenienceLabtestMrp,
        'DEAL_PRICE': ConvenienceLabtestDealPrice,
        'AGREED_PRICE': ConvenienceLabtestAgreedPrice,
        'COD_DEAL_PRICE': ConvenienceLabtestCodDealPrice
    }
}

corporate_price_criteria_class_mapping = {
    'DOCTOR': {
        'MRP': CorporateDoctorMrp,
        'DEAL_PRICE': CorporateDoctorDealPrice,
        'AGREED_PRICE': CorporateDoctorAgreedPrice,
        'COD_DEAL_PRICE': CorporateDoctorCodDealPrice
    },
    'LABTEST': {
        'MRP': CorporateLabtestMrp,
        'DEAL_PRICE': CorporateLabtestDealPrice,
        'AGREED_PRICE': CorporateLabtestAgreedPrice,
        'COD_DEAL_PRICE': CorporateLabtestCodDealPrice
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


def get_price_reference(obj, entity):
    if not obj:
        return None

    if obj.__class__.__name__ not in ['PlusUser', 'PlusPlans', 'TempPlusUser']:
        return None

    price_criteria = obj.plan.price_criteria if obj.__class__.__name__ in ['PlusUser', 'TempPlusUser'] else obj.price_criteria
    if entity not in ['DOCTOR', 'LABTEST'] or price_criteria not in PriceCriteria.availabilities():
        return None

    class_reference = price_criteria_class_mapping[entity][price_criteria]
    return class_reference(obj)


def get_corporate_price_reference(obj, entity):
    if not obj:
        return None

    if obj.__class__.__name__ not in ['PlusUser']:
        return None

    price_criteria = obj.plan.corporate_upper_limit_criteria if obj.__class__.__name__ in ['PlusUser'] else obj.corporate_upper_limit_criteria
    if entity not in ['DOCTOR', 'LABTEST'] or price_criteria not in PriceCriteria.availabilities():
        return None
    class_reference = corporate_price_criteria_class_mapping[entity][price_criteria]
    return class_reference(obj)


def get_max_convenience_reference(plan, entity):
    if not plan:
        return None

    price_criteria = plan.convenience_max_price_reference
    if entity not in ['DOCTOR', 'LABTEST'] or price_criteria not in PriceCriteria.availabilities():
        return None

    class_reference = convenience_price_criteria_class_mapping[entity][price_criteria]
    return class_reference(plan)


def get_min_convenience_reference(plan, entity):
    if not plan:
        return None

    price_criteria = plan.convenience_min_price_reference
    if entity not in ['DOCTOR', 'LABTEST'] or price_criteria not in PriceCriteria.availabilities():
        return None

    class_reference = convenience_price_criteria_class_mapping[entity][price_criteria]
    return class_reference(plan)





