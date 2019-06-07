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
from ondoc.insurance.models import InsuranceDoctorSpecializations, UserInsurance
from ondoc.subscription_plan.models import UserPlanMapping
from ondoc.doctor.models import OpdAppointment

class CartViewSet(viewsets.GenericViewSet):

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
        enabled_for_cod = False
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
            enabled_for_cod = serialized_data.get('hospital').enabled_for_cod

        elif product_id == Order.LAB_PRODUCT_ID:
            lab_app_serializer = LabAppointmentCreateSerializer(data=valid_data.get('data'), context={'request': request, 'data' : valid_data.get('data')})
            lab_app_serializer.is_valid(raise_exception=True)
            serialized_data = lab_app_serializer.validated_data
            cart_item_id = serialized_data.get('cart_item').id if serialized_data.get('cart_item') else None
            self.update_plan_details(request, serialized_data, valid_data)

        valid_data['data']['is_appointment_insured'], valid_data['data']['insurance_id'], valid_data['data'][
            'insurance_message'] = Cart.check_for_insurance(serialized_data, request)
        valid_data['data']['enabled_for_cod'] = enabled_for_cod
        if valid_data['data']['is_appointment_insured']:
            valid_data['data']['payment_type'] = OpdAppointment.INSURANCE
        if serialized_data.get('cart_item'):
            old_cart_obj = Cart.objects.filter(id=serialized_data.get('cart_item').id).first()
            payment_type = old_cart_obj.data.get('payment_type')
            if payment_type == OpdAppointment.INSURANCE and valid_data['data']['is_appointment_insured'] == False:
                valid_data['data']['payment_type'] = OpdAppointment.PREPAID

        Cart.objects.update_or_create(id=cart_item_id, deleted_at__isnull=True,
                                       product_id=valid_data.get("product_id"), user=user, defaults={"data" : valid_data.get("data")})

        return Response({"status": 1, "message": "Saved in cart"}, status.HTTP_200_OK)

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



    @transaction.non_atomic_requests()
    def list(self, request, *args, **kwargs):
        from ondoc.insurance.models import UserInsurance

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

        for item in cart_items:
            try:
                validated_data = item.validate(request)
                insurance_doctor = validated_data.get('doctor', None)
                cart_data = validated_data.get('cart_item').data
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
                    is_lab_insured, insurance_id, insurance_message = user_insurance.validate_lab_insurance(
                        validated_data, user_insurance)
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
                        validated_data, user_insurance)
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

                price_data = item.get_price_details(validated_data)
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
                    "is_price_zero": True if price_data['fees'] is not None and price_data['fees']==0 else False
                })
            except Exception as e:
                # error = custom_exception_handler(e, None)
                items.append({
                    "id": item.id,
                    "valid": False,
                    "errors": str(e),
                    "product_id": item.product_id,
                    "data": serializers.CartItemSerializer(item, context={"validated_data":None}).data,
                    "actual_data": item.data
                })

        # items = sorted(items, key=lambda x: 0 if x["valid"] else -1)

        return Response({"cart_items" : items, "status": 1})

    def process(self, request, *args, **kwargs):

        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        use_wallet = int(request.query_params.get('use_wallet', 1))
        cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True)
        items_to_process = []
        is_process, error = UserInsurance.validate_cart_items(cart_items, request)
        if is_process:
            for item in cart_items:
                try:
                    item.validate(request)
                    items_to_process.append(item)
                except Exception as e:
                    pass

            resp = Order.create_order(request, items_to_process, use_wallet)
            return Response(resp)
        else:
            error = {"code": "invalid", "message": error}
            return Response(status=400, data={"request_errors": error})


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