from datetime import timezone
import dateutil
from rest_framework import viewsets, status
from ondoc.api.v1.cart import serializers
from rest_framework.response import Response
from ondoc.account.models import Order
from ondoc.api.v1.utils import custom_exception_handler
from ondoc.cart.models import Cart
from ondoc.api.v1.diagnostic.serializers import LabAppointmentCreateSerializer
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
from django.db import transaction
from django.conf import settings
import copy

from ondoc.common.models import SearchCriteria
from ondoc.diagnostic.models import LabAppointment

from ondoc.coupon.models import Coupon
from ondoc.diagnostic.models import LabTest
from ondoc.insurance.models import InsuranceDoctorSpecializations, UserInsurance
from ondoc.subscription_plan.models import UserPlanMapping
from ondoc.doctor.models import OpdAppointment

# Cart view.
class CartViewSet(viewsets.GenericViewSet):

    # Api for add items to cart.
    def add(self, request, *args, **kwargs):
        from ondoc.doctor.models import OpdAppointment
        from ondoc.insurance.models import UserInsurance

        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        data = dict(request.data)

        serializer = serializers.CartCreateSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data
        serialized_data = None

        product_id = valid_data.get('product_id')
        multiple_appointments = False
        if product_id == Order.DOCTOR_PRODUCT_ID:
            opd_app_serializer = CreateAppointmentSerializer(data=valid_data.get('data'), context={'request': request, 'data' : valid_data.get('data')})
            opd_app_serializer.is_valid(raise_exception=True)
            serialized_data = opd_app_serializer.validated_data
            cart_item_id = serialized_data.get('cart_item').id if serialized_data.get('cart_item') else None
            if not OpdAppointment.can_book_for_free(request, serialized_data, cart_item_id):
                return Response({'request_errors': {"code": "invalid",
                                                    "message": "Only {} active free bookings allowed per customer".format(
                                                        OpdAppointment.MAX_FREE_BOOKINGS_ALLOWED)}},
                                status.HTTP_400_BAD_REQUEST)
        elif product_id == Order.LAB_PRODUCT_ID:
            lab_app_serializer = LabAppointmentCreateSerializer(data=valid_data.get('data'), context={'request': request, 'data': valid_data.get('data')})
            lab_app_serializer.is_valid(raise_exception=True)
            serialized_data = lab_app_serializer.validated_data
            cart_item_id = serialized_data.get('cart_item').id if serialized_data.get('cart_item') else None
            self.update_plan_details(request, serialized_data, valid_data)

            if serialized_data.get('multi_timings_enabled'):
                if serialized_data.get('selected_timings_type') == 'separate':
                    multiple_appointments = True

        booked_by = 'agent' if hasattr(request, 'agent') else 'user'
        valid_data['data']['is_appointment_insured'], valid_data['data']['insurance_id'], valid_data['data'][
            'insurance_message'] = Cart.check_for_insurance(serialized_data, user=user, booked_by=booked_by)

        plus_user = user.active_plus_user
        vip_data_dict = {
            "is_vip_member": False,
            "cover_under_vip": False,
            "plus_user_id": None,
            "vip_amount": 0,
            "is_gold_member": False,
            "vip_convenience_amount": 0
        }
        if plus_user:

            vip_data_dict = plus_user.validate_cart_items(serialized_data, request)
        valid_data['data']['cover_under_vip'] = vip_data_dict.get('cover_under_vip', False)
        valid_data['data']['plus_user_id'] = vip_data_dict.get('plus_user_id', None)
        valid_data['data']['is_vip_member'] = vip_data_dict.get('is_vip_member', False)
        valid_data['data']['vip_amount'] = vip_data_dict.get('vip_amount')
        valid_data['data']['amount_to_be_paid'] = vip_data_dict.get('vip_amount')
        valid_data['data']['is_gold_member'] = vip_data_dict.get('is_gold_member')
        valid_data['data']['vip_convenience_amount'] = vip_data_dict.get('vip_convenience_amount')
        valid_data['data']['payment_type'] = vip_data_dict.get('payment_type', OpdAppointment.PREPAID)

        if plus_user and plus_user.plan and not plus_user.plan.is_gold:
            cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True)
            for cart in cart_items:
                if not cart.data.get('payment_type') == valid_data['data']['payment_type']:
                    return Response({"status": 0, "message": "Please remove other appointments from cart to add"},
                                    status.HTTP_400_BAD_REQUEST)

        if valid_data['data']['is_appointment_insured']:
            valid_data['data']['payment_type'] = OpdAppointment.INSURANCE
        if serialized_data.get('cart_item'):
            old_cart_obj = Cart.objects.filter(id=serialized_data.get('cart_item').id).first()
            payment_type = old_cart_obj.data.get('payment_type', OpdAppointment.PREPAID)
            if payment_type == OpdAppointment.INSURANCE and valid_data['data']['is_appointment_insured'] == False:
                valid_data['data']['payment_type'] = OpdAppointment.PREPAID

        cart_items = []
        if multiple_appointments:
            pathology_data = None
            all_tests = []
            for test_timing in serialized_data.get('test_timings'):
                all_tests.append(test_timing.get('test'))
            coupon_applicable_on_tests = Coupon.check_coupon_tests_applicability(request, serialized_data.get('coupon_obj'),
                                                                                 serialized_data.get('profile'), all_tests)
            coupon_applicable_on_tests = set(coupon_applicable_on_tests)
            pathology_coupon_applied = False

            request_data = data.get('data')
            for test_timing in serialized_data.get('test_timings'):
                test_type = test_timing.get('type')
                datetime_ist = dateutil.parser.parse(str(test_timing.get('start_date')))
                data_start_date = datetime_ist.astimezone(tz=timezone.utc).isoformat()

                if test_type == LabTest.PATHOLOGY:
                    if not pathology_data:
                        pathology_data = copy.deepcopy(request_data)
                        pathology_data['test_ids'] = []
                        pathology_data['start_date'] = data_start_date
                        pathology_data['start_time'] = test_timing['start_time']
                        pathology_data['is_home_pickup'] = test_timing['is_home_pickup']
                    pathology_data['test_ids'].append(test_timing['test'].id)
                    if not pathology_coupon_applied:
                        if test_timing['test'] in coupon_applicable_on_tests:
                            pathology_coupon_applied = True
                elif test_type == LabTest.RADIOLOGY:
                    new_data = copy.deepcopy(request_data)
                    new_data.pop('coupon_code', None) if not test_timing['test'] in coupon_applicable_on_tests else None;
                    new_data['start_date'] = data_start_date
                    new_data['start_time'] = test_timing['start_time']
                    new_data['is_home_pickup'] = test_timing['is_home_pickup']
                    new_data['test_ids'] = [test_timing['test'].id]
                    cart_item = Cart.add_items_to_cart(request, serialized_data, new_data, product_id)
                    if cart_item:
                        cart_items.append(cart_item)

            if pathology_data:
                if not pathology_coupon_applied:
                    pathology_data.pop('coupon_code', None)
                cart_item = Cart.add_items_to_cart(request, serialized_data, pathology_data, product_id)
                if cart_item:
                    cart_items.append(cart_item)
        else:
            test_timings = serialized_data.get('test_timings')
            if test_timings:
                datetime_ist = dateutil.parser.parse(str(test_timings[0].get('start_date')))
                data_start_date = datetime_ist.astimezone(tz=timezone.utc).isoformat()
                new_data = copy.deepcopy(data.get('data'))
                new_data['start_date'] = data_start_date
                new_data['start_time'] = test_timings[0]['start_time']
                new_data['is_home_pickup'] = test_timings[0]['is_home_pickup']
            else:
                new_data = copy.deepcopy(data.get('data'))
            cart_item = Cart.add_items_to_cart(request, serialized_data, new_data, product_id)
            if cart_item:
                cart_items.append(cart_item)

        return Response({"status": 1, "message": "Saved in cart"}, status.HTTP_200_OK)

    # update plan for Care product.
    @staticmethod
    def update_plan_details(request, serialized_data, valid_data):
        from ondoc.doctor.models import OpdAppointment
        user = request.user
        active_plan_mapping = UserPlanMapping.get_active_plans(user).first()
        user_plan_id = None
        included_in_user_plan = False
        test_included_in_user_plan = UserPlanMapping.get_free_tests(request)
        selected_test_id = [temp_test.id for temp_test in serialized_data.get('test_ids', [])]
        if sorted(selected_test_id) == sorted(test_included_in_user_plan):
            if active_plan_mapping:
                user_plan_id = active_plan_mapping.id
                included_in_user_plan = True
                valid_data.get('data').update(
                    {'included_in_user_plan': included_in_user_plan, 'user_plan': user_plan_id})
                valid_data.get('data')['payment_type'] = OpdAppointment.PLAN

        if not included_in_user_plan:
            valid_data.get('data').update(
                {'included_in_user_plan': included_in_user_plan, 'user_plan': user_plan_id})

        if serialized_data.get('cart_item'):
            old_cart_obj = Cart.objects.filter(id=serialized_data.get('cart_item').id).first()
            payment_type = old_cart_obj.data.get('payment_type')
            if payment_type == OpdAppointment.PLAN and valid_data.get('data')['included_in_user_plan'] == False:
                valid_data.get('data')['payment_type'] = OpdAppointment.PREPAID

    # Api for list of items in the cart.
    @transaction.non_atomic_requests()
    def list(self, request, *args, **kwargs):
        from ondoc.insurance.models import UserInsurance

        search_criteria = SearchCriteria.objects.filter(search_key='is_gold').first()
        hosp_is_gold = False
        if search_criteria:
            hosp_is_gold = search_criteria.search_value

        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True).order_by("-updated_at")
        items = []

        gyno_count = 0
        onco_count = 0

        user_insurance = UserInsurance.get_user_insurance(request.user)
        specialization_count_dict = None
        if user_insurance and user_insurance.is_valid():

            specialization_count_dict = InsuranceDoctorSpecializations.get_already_booked_specialization_appointments(user, user_insurance)
            gyno_count = specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST, {}).get('count', 0)
            onco_count = specialization_count_dict.get(InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST, {}).get('count', 0)

            # if not specialization_count_dict:
            #     return is_insured, insurance_id, insurance_message


        plus_user_obj = user.active_plus_user
        utilization = plus_user_obj.get_utilization if plus_user_obj else {}
        deep_utilization = copy.deepcopy(utilization)

        for item in cart_items:
            try:
                validated_data = item.validate(request)
                insurance_doctor = validated_data.get('doctor', None)
                cart_data = validated_data.get('cart_item').data
                if cart_data.get('cover_under_vip'):
                    plus_user = user.active_plus_user
                    if not plus_user:
                        raise Exception('Member is no more VIP')
                    vip_dict = plus_user.validate_plus_appointment(validated_data, utilization=deep_utilization)
                    if not vip_dict.get('cover_under_vip'):
                        raise Exception('Appointment no more cover under VIP')

                    if vip_dict.get('cover_under_vip'):
                        if plus_user and plus_user.plan.is_gold:
                            validated_data['payment_type'] = 6
                        elif plus_user and not plus_user.plan.is_gold:
                            validated_data['payment_type'] = 5

                    item.data['amount_to_be_paid'] = vip_dict['amount_to_be_paid']
                    item.data['vip_amount'] = vip_dict['amount_to_be_paid']
                    item.data['vip_convenience_amount'] = vip_dict['vip_convenience_amount']
                    # cart_data['amount_to_be_paid'] = vip_dict['amount_to_be_paid']
                    # cart_data['amount_to_be_paid'] = vip_dict['amount_to_be_paid']
                    # validated_data.save()
                if not cart_data.get('is_appointment_insured'):
                    item.data['is_appointment_insured'] = False
                    item.data['insurance_id'] = None
                    item.data['insurance_message'] = ""
                    # item.data['payment_type'] = OpdAppointment.PREPAID
                if cart_data.get('is_appointment_insured') and (not user_insurance or not user_insurance.is_valid()):
                    item.data['is_appointment_insured'] = False
                    item.data['insurance_id'] = None
                    item.data['insurance_message'] = ""
                    item.data['payment_type'] = OpdAppointment.PREPAID
                    raise Exception('Insurance expired.')
                if not insurance_doctor and cart_data.get('is_appointment_insured') and user_insurance and user_insurance.is_valid():
                    # is_lab_insured, insurance_id, insurance_message = user_insurance.validate_insurance(
                    #     validated_data)
                    insurance_dict = user_insurance.validate_insurance(
                        validated_data)
                    is_lab_insured = insurance_dict.get('is_insured', False)
                    insurance_id = insurance_dict.get('insurance_id', None)
                    insurance_message = insurance_dict.get('insurance_message', '')
                    if is_lab_insured:
                        item.data['is_appointment_insured'] = True
                        item.data['insurance_id'] = insurance_id
                        item.data['insurance_message'] = ""
                        item.data['payment_type'] = OpdAppointment.INSURANCE
                    else:
                        item.data['is_appointment_insured'] = False
                        item.data['insurance_id'] = None
                        item.data['insurance_message'] = ""
                        item.data['payment_type'] = OpdAppointment.PREPAID
                        raise Exception('Appointment is no more covered in Insurance.')

                if insurance_doctor and cart_data.get('is_appointment_insured') and user_insurance and user_insurance.is_valid():
                    is_doctor_insured, insurance_id, insurance_message = user_insurance.validate_doctor_insurance(
                        validated_data)
                    if not is_doctor_insured:
                        item.data['is_appointment_insured'] = False
                        item.data['insurance_id'] = None
                        item.data['insurance_message'] = ""
                        item.data['payment_type'] = OpdAppointment.PREPAID
                        raise Exception('Appointment is no more covered in Insurance.')

                        # item.data['payment_type'] = OpdAppointment.PREPAID
                    if not specialization_count_dict:
                        item.data['is_appointment_insured'] = True
                        item.data['insurance_id'] = insurance_id
                        item.data['insurance_message'] = ""
                        item.data['payment_type'] = OpdAppointment.INSURANCE
                    if specialization_count_dict and is_doctor_insured:
                        doctor_specilization_tuple = InsuranceDoctorSpecializations.get_doctor_insurance_specializations(
                            insurance_doctor)
                        if not doctor_specilization_tuple:
                            item.data['is_appointment_insured'] = True
                            item.data['insurance_id'] = insurance_id
                            item.data['insurance_message'] = ""
                            item.data['payment_type'] = OpdAppointment.INSURANCE
                        if doctor_specilization_tuple:
                            res, specialization = doctor_specilization_tuple[0], doctor_specilization_tuple[1]

                            if specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST and item.data.get(
                                    'is_appointment_insured'):
                                gyno_count = gyno_count + 1
                            if specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST and item.data.get(
                                    'is_appointment_insured'):
                                onco_count = onco_count + 1

                            if gyno_count > int(
                                    settings.INSURANCE_GYNECOLOGIST_LIMIT) and specialization == InsuranceDoctorSpecializations.SpecializationMapping.GYNOCOLOGIST:
                                item.data['is_appointment_insured'] = False
                                item.data['insurance_id'] = None
                                item.data['insurance_message'] = "Gynecologist limit exceeded of limit {}".format(
                                    settings.INSURANCE_GYNECOLOGIST_LIMIT)

                                raise Exception('Gynecologist limit exceeded.')
                                # if cart_data.get('is_appointment_insured'):
                                #     item.data['payment_type'] = OpdAppointment.PREPAID
                                # item.data['payment_type'] = OpdAppointment.PREPAID

                            if onco_count > int(
                                    settings.INSURANCE_ONCOLOGIST_LIMIT) and specialization == InsuranceDoctorSpecializations.SpecializationMapping.ONCOLOGIST:
                                item.data['is_appointment_insured'] = False
                                item.data['insurance_id'] = None
                                item.data['insurance_message'] = "Oncologist limit exceeded of limit {}".format(
                                    settings.INSURANCE_ONCOLOGIST_LIMIT)

                                raise Exception('Oncology limit exceeded.')
                                # if cart_data.get('is_appointment_insured'):
                                #     item.data['payment_type'] = OpdAppointment.PREPAID
                                # item.data['payment_type'] = OpdAppointment.PREPAID

                price_data = item.get_price_details(validated_data, plus_user_obj)
                items.append({
                    "id" : item.id,
                    "valid": True,
                    "errors" : None,
                    "product_id" : item.product_id,
                    "data": serializers.CartItemSerializer(item, context={"validated_data":validated_data}).data,
                    "actual_data" : item.data,
                    "deal_price" : price_data["deal_price"],
                    "mrp" : price_data["mrp"],
                    "coupon_discount" : price_data["coupon_discount"],
                    "coupon_cashback" : price_data["coupon_cashback"],
                    "home_pickup_charges" : price_data.get("home_pickup_charges", 0),
                    "consultation" : price_data.get("consultation", None),
                    "cod_deal_price": price_data.get("consultation", {}).get('cod_deal_price'),
                    "is_enabled_for_cod" : price_data.get("consultation", {}).get('is_enabled_for_cod'),
                    "is_price_zero": True if price_data['fees'] is not None and price_data['fees']==0 else False,
                    'is_gold': hosp_is_gold
                })
            except Exception as e:
                # error = custom_exception_handler(e, None)
                items.append({
                    "id": item.id,
                    "valid": False,
                    "errors": str(e),
                    "product_id": item.product_id,
                    "data": serializers.CartItemSerializer(item, context={"validated_data":None}).data,
                    "actual_data": item.data,
                    "consultation": None,
                })

        # items = sorted(items, key=lambda x: 0 if x["valid"] else -1)

        return Response({"cart_items" : items, "status": 1})

    # process cart for purchase.
    def process(self, request, *args, **kwargs):

        user = request.user
        plus_user = user.active_plus_user

        if plus_user and plus_user.plan and not plus_user.plan.is_gold:
            cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True)
            import itertools
            for item1, item2 in itertools.combinations(cart_items, 2):
                if(item1.data.get('payment_type') != item2.data.get('payment_type')):
                    return Response({"status": 0, "message": "Please remove other appointments from cart to add"},
                                    status.HTTP_400_BAD_REQUEST)

        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        if user.onhold_insurance:
            return Response(data={"error": "Your documents from the last claim are under verification.Please write to customercare@docprime.com for more information"}, status=status.HTTP_400_BAD_REQUEST)

        use_wallet = int(request.query_params.get('use_wallet', 1))
        cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True)
        items_to_process = []
        total_mrp = 0
        total_count = 0
        is_process, error = UserInsurance.validate_cart_items(cart_items, request)
        if is_process:
            deep_utilization = copy.deepcopy(plus_user.get_utilization) if plus_user else {}
            for item in cart_items:
                try:
                    validated_data = item.validate(request)
                    if plus_user and item.data.get('cover_under_vip'):
                        vip_dict = plus_user.validate_plus_appointment(validated_data, utilization=deep_utilization)
                        if vip_dict.get('cover_under_vip'):
                            items_to_process.append(item)
                            # price_data = OpdAppointment.get_price_details(
                            #     validated_data) if 'doctor' in validated_data else LabAppointment.get_price_details(
                            #     validated_data)

                            # if 'doctor' in validated_data:
                            #     total_mrp = total_mrp + int(price_data.get('mrp', 0))
                            #     if total_mrp <= utilization.get('doctor_amount_available'):
                            # else:
                            #     tests = validated_data.get('test_ids')
                            #     package_available_ids = utilization.get('allowed_package_ids')
                            #     package_available_count = utilization.get('available_package_count')
                            #     package_available_amount = utilization.get('available_package_amount')
                            #     for test in tests:
                            #         if test.is_package and test.id in package_available_ids and package_available_count and package_available_count > 0:
                            #             total_count = total_count + 1
                            #             if total_count <= package_available_count:
                            #                 items_to_process.append(item)
                            #         elif test.is_package and package_available_amount and package_available_amount > 0:
                            #             utilization['available_package_amount'] = package_available_amount - (price_data.get('mrp') + price_data.get('home_pickup_charges'))
                            #             total_mrp = total_mrp + price_data.get('mrp') + price_data.get('home_pickup_charges')
                            #             if total_mrp <= package_available_amount:
                            #                 items_to_process.append(item)
                        else:
                            raise Exception('Item is no more cover under VIP')
                    else:
                        # item.validate(request)
                        items_to_process.append(item)
                except Exception as e:
                    pass

            resp = Order.create_order(request, items_to_process, use_wallet)
            return Response(resp)
        else:
            error = {"code": "invalid", "message": error}
            return Response(status=400, data={"request_errors": error})

    # remove item from the cart.
    def remove(self, request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        data = dict(request.data)

        cart_item = Cart.objects.filter(user=user, id=data.get('id', None)).first()
        if not cart_item:
            return Response({"status": 0}, status.HTTP_404_NOT_FOUND)

        cart_item.mark_delete()

        return Response({"status": 1, "message": "Removed from cart"}, status.HTTP_200_OK)
