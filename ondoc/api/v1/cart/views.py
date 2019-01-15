from rest_framework import viewsets, status
from ondoc.api.v1.cart import serializers
from rest_framework.response import Response
from ondoc.account.models import Order
from ondoc.cart.models import Cart
from ondoc.api.v1.diagnostic.serializers import LabAppointmentCreateSerializer
from ondoc.api.v1.doctor.serializers import CreateAppointmentSerializer
from ondoc.diagnostic.models import LabAppointment
from ondoc.doctor.models import OpdAppointment


class CartViewSet(viewsets.GenericViewSet):

    def add(self, request, *args, **kwargs):

        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        data = dict(request.data)
        serializer = serializers.CartCreateSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        valid_data = serializer.validated_data

        product_id = valid_data.get('product_id')
        if product_id == Order.DOCTOR_PRODUCT_ID:
            opd_app_serializer = CreateAppointmentSerializer(data=valid_data.get('data'), context={'request': request})
            opd_app_serializer.is_valid(raise_exception=True)
        elif product_id == Order.LAB_PRODUCT_ID:
            lab_app_serializer = LabAppointmentCreateSerializer(data=valid_data.get('data'), context={'request': request})
            lab_app_serializer.is_valid(raise_exception=True)

        Cart.objects.create(product_id=valid_data.get("product_id"),
                                   user = user,
                                   data = valid_data.get("data"))

        return Response({"status": 1, "message": "Saved in cart"}, status.HTTP_200_OK)


    def list(self, request, *args, **kwargs):

        user = request.user
        if not user.is_authenticated:
            return Response({"status": 0}, status.HTTP_401_UNAUTHORIZED)

        cart_items = Cart.objects.filter(user=user)
        items = []
        for item in cart_items:

            if item.product_id == Order.DOCTOR_PRODUCT_ID:
                opd_app_serializer = CreateAppointmentSerializer(data=item.data, context={'request': request})
                opd_app_serializer.is_valid(raise_exception=True)
                validated_data = opd_app_serializer.validated_data
                price_data = OpdAppointment.get_price_details(validated_data)
            elif item.product_id == Order.LAB_PRODUCT_ID:
                lab_app_serializer = LabAppointmentCreateSerializer(data=item.data, context={'request': request})
                lab_app_serializer.is_valid(raise_exception=True)
                validated_data = lab_app_serializer.validated_data
                price_data = LabAppointment.get_price_details(validated_data)

            items.append({
                "product_id" : item.product_id,
                "data" : item.data,
                "deal_price" : price_data["deal_price"],
                "mrp" : price_data["mrp"],
                "coupon_discount" : price_data["coupon_discount"],
                "coupon_cashback" : price_data["coupon_cashback"]
            })

        return Response({"cart_items" : items, "status": 1})