from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view

from ondoc.authentication.serializers import UserAuthSerializer

@api_view(['GET', 'POST', ])
def register_user(request, format='json'):
    data = request.GET
    serializer = UserAuthSerializer(data=data,context={'user_type': 3})
    if serializer.is_valid(raise_exception=True):
        user = serializer.save()
        if user:
            json = serializer.data
            return Response(json, status=status.HTTP_201_CREATED)

    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


def generate_otp(request):
    pass


def verify_otp(request):
    pass
