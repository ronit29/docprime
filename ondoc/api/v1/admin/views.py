from ondoc.api.v1.auth import serializers
from ondoc.authentication.models import UserSecretKey
from django.contrib.auth import get_user_model
import logging
import jwt
from ondoc.api.v1.admin import serializers
from ondoc.crm.constants import constants

from rest_framework.response import Response
logger = logging.getLogger(__name__)
User = get_user_model()


def userlogin_via_agent(request):
    from django.http import JsonResponse
    from ondoc.authentication.backends import JWTAuthentication
    response = {'login': 0}
    if request.method != 'GET':
        return Response(status=405)

    if request.is_ajax() and (request.user.groups.filter(name=constants['LAB_APPOINTMENT_MANAGEMENT_TEAM']).exists()
                              or request.user.groups.filter(name=constants['OPD_APPOINTMENT_MANAGEMENT_TEAM']).exists()):
        serializer = serializers.AgenctVerificationSerializer(data=request.GET)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        user = User.objects.filter(phone_number=data['phone_number'], user_type=User.CONSUMER).first()
        if not user:
            user = User.objects.create(phone_number=data['phone_number'],
                                              is_phone_number_verified=False,
                                              user_type=User.CONSUMER)


        user_key = UserSecretKey.objects.get_or_create(user=user)
        payload = JWTAuthentication.appointment_agent_payload_handler(request, user)
        token = jwt.encode(payload, user_key[0].key)

        response = {
            "login": 1,
            "agent_id": request.user.id,
            "token": str(token, 'utf-8'),
            "expiration_time": payload['exp'],
            "refresh": False
        }
    return JsonResponse(response)
