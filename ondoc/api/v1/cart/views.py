from rest_framework import viewsets, status
from ondoc.api.v1.cart import serializers
from rest_framework.response import Response
from ondoc.account.models import Order
from ondoc.api.v1.utils import custom_exception_handler
from ondoc.cart.models import Cart
from ondoc.api.v1.diagnostic.serializers import LabAppointmentCreateSerializer
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
from django.db import transaction

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
            lab_app_serializer = LabAppointmentCreateSerializer(data=valid_data.get('data'), context={'request': request, 'data' : valid_data.get('data')})
            lab_app_serializer.is_valid(raise_exception=True)
            serialized_data = lab_app_serializer.validated_data
            cart_item_id = serialized_data.get('cart_item').id if serialized_data.get('cart_item') else None

        data['data']['is_appointment_insured'], data['data']['insurance_id'], data['data'][
            'insurance_message'] = Cart.check_for_insurance(serialized_data, request)

        if data['data']['is_appointment_insured']:
            data['data']['payment_type'] = OpdAppointment.INSURANCE
        if serialized_data.get('cart_item'):
            old_cart_obj = Cart.objects.filter(id=serialized_data.get('cart_item').id).first()
            payment_type = old_cart_obj.data.get('payment_type')
            if payment_type == OpdAppointment.INSURANCE and data['data']['is_appointment_insured'] == False:
                data['data']['payment_type'] = OpdAppointment.PREPAID

        Cart.objects.update_or_create(id=cart_item_id, deleted_at__isnull=True,
                                       product_id=valid_data.get("product_id"), user=user, defaults={"data" : valid_data.get("data")})

        return Response({"status": 1, "message": "Saved in cart"}, status.HTTP_200_OK)

    @transaction.non_atomic_requests()
    def list(self, request, *args, **kwargs):
        from ondoc.insurance.models import UserInsurance

        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        cart_items = Cart.objects.filter(user=user, deleted_at__isnull=True).order_by("-updated_at")
        items = []

        for item in cart_items:
            try:
                validated_data = item.validate(request)
                # user_insurance = UserInsurance.objects.filter(user=user).last()
                # if user_insurance:
                    # item.data['is_appointment_insured'], item.data['insurance_id'], item.data['insurance_message'] = user_insurance.validate_insurance(validated_data)
                item.data['is_appointment_insured'], item.data['insurance_id'], item.data[
                        'insurance_message'] = Cart.check_for_insurance(validated_data, request)
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
                    "consultation" : price_data.get("consultation", None)
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
        for item in cart_items:
            try:
                item.validate(request)
                items_to_process.append(item)
            except Exception as e:
                pass

        resp = Order.create_order(request, items_to_process, use_wallet)

        return Response(resp)

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