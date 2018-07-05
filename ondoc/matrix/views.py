from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from ondoc.doctor.models import Doctor
from ondoc.diagnostic.models import Lab
from ondoc.authentication.models import StaffProfile
from ondoc.api.v1.utils import IsMatrixUser


class MatrixLead(GenericViewSet):
    LAB = 'lab'
    DOCTOR = 'doctor'
    SUB_TYPES = (
        (LAB, 'lab'),
        (DOCTOR, 'doctor'),
    )
    queryset = Doctor.objects.none()
    permission_classes = (IsMatrixUser,)

    def create(self, request, *args, **kwargs):

       from .serializers import MatrixLeadDataSerializer
       response = {"status": "Error"}
       serializer = MatrixLeadDataSerializer(data=request.data)
       serializer.is_valid(raise_exception=True)
       data = serializer.validated_data
       staff_profile = StaffProfile.objects.filter(employee_id__iexact=data.get('agent_employee_id'))

       if not staff_profile.exists():
           return Response(status=status.HTTP_400_BAD_REQUEST, data={'status': 'Error', 'message': 'StaffProfile Not Found'})

       staff_profile = staff_profile.first()

       if data.get('sub_product') == MatrixLead.DOCTOR:
           create_lead = Doctor.objects.create(name=data.get('name'), gender=data.get('gender'), created_by=staff_profile.user,
                                               onboarding_status=Doctor.NOT_ONBOARDED, assigned_to=staff_profile.user)
           change_url = "/admin/doctor/doctor/%s/change/"%(create_lead.id)
       elif data.get('sub_product') == MatrixLead.LAB:
           create_lead = Lab.objects.create(name=data.get('name'), city=data.get('city'), assigned_to=staff_profile.user,
                                             onboarding_status=Lab.NOT_ONBOARDED, created_by=staff_profile.user)
           change_url = "/admin/diagnostic/lab/%s/change/"% (create_lead.id)

       if create_lead:
           response['status'] = 'Success'
           response['id'] = create_lead.id
           response['url'] = change_url

       return Response(response)






