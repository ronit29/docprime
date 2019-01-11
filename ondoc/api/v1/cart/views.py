from rest_framework import viewsets, status
from ondoc.cart.models import Cart
from ondoc.api.v1.cart import serializers
from rest_framework.response import Response

class CartViewSet(viewsets.GenericViewSet):

    def create(self, request, *args, **kwargs):
        data = dict(request.data)
        serializer = serializers.CartCreateSerializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        input_data = serializer.validated_data
        Cart.objects.create(product_id=input_data.get("product_id"),
                                   user = input_data.get("user"),
                                   data = input_data.get("data"))

        return Response("Data saved in Cart",status.HTTP_200_OK)

    def list(self, request, *args, **kwargs):

        if request.user.is_authenticated:
            user = request.user
