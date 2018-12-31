import logging

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import mixins, viewsets, status
logger = logging.getLogger(__name__)
from .serializers import NumberMaskSerializer
from ondoc.authentication import models as auth_models
from ondoc.doctor import models as doctor_model
from django.utils import timezone
import requests
import json
from django.conf import settings


class MaskNumberViewSet(viewsets.GenericViewSet):

    def mask_number(self, request):
        serializer = NumberMaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        doctor_obj = data.get('doctor')

        hospital = data.get('hospital')
        spoc_details = hospital.spoc_details.all()

        request_data = {
            "ExpirationDate": int((timezone.now() + timezone.timedelta(days=2)).timestamp()),
            "FromNumber": data.get('mobile') if str(data.get('mobile')).startswith('0') else "0%d" % data.get('mobile')
        }


        if hospital and hospital.is_live and len(spoc_details)>0:
            for type in [auth_models.SPOCDetails.SPOC, auth_models.SPOCDetails.MANAGER, auth_models.SPOCDetails.OTHER, auth_models.SPOCDetails.OWNER]:
                for spoc in spoc_details:
                    if spoc.contact_type == type:
                        final = None
                        if spoc.std_code:
                            final = '0' + str(spoc.std_code).lstrip('0') + str(spoc.number).lstrip('0')
                        else:
                            final = '0' + str(spoc.number).lstrip('0')
                        if final:
                            request_data["ToNumber"] = final if final.startswith('0') else "0%s" % final

                            request_response_data = self.get_masked_number(request_data)
                            if not request_response_data:
                                return Response({'status': 0, 'message': 'No Contact Number found'},
                                                status.HTTP_404_NOT_FOUND)
                            return Response({'status': 1, 'number': request_response_data}, status.HTTP_200_OK)

        doctor_details = doctor_model.DoctorMobile.objects.filter(doctor=doctor_obj).values('is_primary','number','std_code').order_by('-is_primary').first()

        if not doctor_details:
            return Response({'status': 0, 'message': 'No Contact Number found'}, status.HTTP_404_NOT_FOUND)

        final = str(doctor_details.get('number')).lstrip('0')
        if doctor_details.get('std_code'):
            final = '0'+str(doctor_details.get('std_code')).lstrip('0')+str(doctor_details.get('number')).lstrip('0')

        request_data["ToNumber"] = final if final.startswith('0') else "0%s" % final

        request_response_data = self.get_masked_number(request_data)
        if not request_response_data:
            return Response({'status': 0, 'message': 'No Contact Number found'}, status.HTTP_404_NOT_FOUND)

        return Response({'status': 1, 'number': request_response_data}, status.HTTP_200_OK)

    def get_masked_number(self, data):
        try:
            url = settings.MATRIX_NUMBER_MASKING
            response = requests.post(url, data=json.dumps(data), headers={'Content-Type': 'application/json'})

            if response.status_code != status.HTTP_200_OK or not response.ok:
                logger.info("[ERROR] Could not mask the number from matrix system")
                logger.error("[ERROR] %s", response.reason)
                return None
            else:
                resp_data = response.json()
                return resp_data

        except Exception as e:
            logger.error("[ERROR] Could not mask the number from matrix system ", str(e))
            return None