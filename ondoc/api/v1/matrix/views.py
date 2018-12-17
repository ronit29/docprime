import logging

from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework import mixins, viewsets, status
logger = logging.getLogger(__name__)
from .serializers import NumberMaskSerializer
from ondoc.authentication import models as auth_models
from ondoc.doctor import models as doctor_model
from ondoc.matrix.tasks import get_masked_number
from django.utils import timezone


class MaskNumberViewSet(viewsets.GenericViewSet):

    def mask_number(self, request):
        serializer = NumberMaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        doctor_obj = data.get('doctor')

        hospital = data.get('hospital')
        spoc_details = hospital.spoc_details.all()
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
                            return Response({'status': 1, 'number': final}, status.HTTP_200_OK)

        doctor_details = doctor_model.DoctorMobile.objects.filter(doctor=doctor_obj).values('is_primary','number','std_code').order_by('-is_primary').first()

        if not doctor_details:
            return Response({'status': 0, 'message': 'No Contact Number found'}, status.HTTP_404_NOT_FOUND)

        final = str(doctor_details.get('number')).lstrip('0')
        if doctor_details.get('std_code'):
            final = '0'+str(doctor_details.get('std_code')).lstrip('0')+str(doctor_details.get('number')).lstrip('0')

        request_data = {
            "ExpiryDate": int(timezone.now().timestamp()),
            "FromNumber": data.get('mobile'),
            "ToNumber": final
        }

        request_response_data = get_masked_number(request_data)
        if not request_response_data:
            return Response({'status': 0, 'message': 'No Contact Number found'}, status.HTTP_404_NOT_FOUND)

        return Response({'status': 1, 'number': request_response_data}, status.HTTP_200_OK)

