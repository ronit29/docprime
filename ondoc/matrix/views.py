from rest_framework.viewsets import GenericViewSet
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from ondoc.doctor.models import Doctor, DoctorMobile
from ondoc.diagnostic.models import Lab
from ondoc.authentication.models import StaffProfile
from ondoc.api.v1.utils import IsMatrixUser


class MatrixLead(GenericViewSet):
    LAB = 'lab'
    DOCTOR = 'doctor'
    MALE = 'm'
    FEMALE = 'f'
    OTHER = 'o'
    SUB_TYPES = (
        (LAB, 'lab'),
        (DOCTOR, 'doctor'),
    )
    GENDER_TYPES = (
        (MALE, 'm'),
        (FEMALE, 'f'),
        (OTHER, 'o'),
    )
    queryset = Doctor.objects.none()
    permission_classes = (IsMatrixUser,)

    def create(self, request, *args, **kwargs):

        from .serializers import MatrixLeadDataSerializer
        response = {"status": "error"}
        serializer = MatrixLeadDataSerializer(data=request.data)
        is_valid = serializer.is_valid(raise_exception=False)

        if not is_valid:
            response['message'] = 'Invalid Request'
            response['errors'] = serializer.errors
            return Response(status = status.HTTP_400_BAD_REQUEST, data=response)

        data = serializer.validated_data
        staff_profile = StaffProfile.objects.filter(employee_id__iexact=data.get('agent_employee_id'))

        if not staff_profile.exists():
            return Response(status=status.HTTP_400_BAD_REQUEST, data={'status': 'error', 'message': 'StaffProfile Not Found'})

        staff_profile = staff_profile.first()



        if data.get('sub_product') == MatrixLead.DOCTOR:
            existing_doctor = Doctor.objects.filter(matrix_lead_id=data.get('matrix_lead_id'))
            if existing_doctor.exists():
                create_lead = existing_doctor.first()
            else:
                doctor_data = {"name": data.get('name'),
                              'gender': data.get('gender'),
                              'created_by': staff_profile.user,
                              'onboarding_status': Doctor.NOT_ONBOARDED,
                              'assigned_to': staff_profile.user,
                              'matrix_reference_id': data.get('matrix_reference_id'),
                              'matrix_lead_id': data.get('matrix_lead_id'),
                }
                if data.get('gender') is None:
                    doctor_data.pop('gender', None)
                create_lead = Doctor.objects.create(**doctor_data)
                if data.get('phone_number'):
                    DoctorMobile.objects.create(doctor=create_lead, number=data.get('phone_number'), is_primary=False)
            change_url = "/admin/doctor/doctor/%s/change/"%(create_lead.id)

        elif data.get('sub_product') == MatrixLead.LAB:
            existing_lab = Lab.objects.filter(matrix_lead_id=data.get('matrix_lead_id'))
            if existing_lab.exists():
                create_lead = existing_lab.first()

            else:
                create_lead = Lab.objects.create(name=data.get('name'), city=data.get('city'), assigned_to=staff_profile.user,
                                             onboarding_status=Lab.NOT_ONBOARDED, created_by=staff_profile.user,
                                            primary_mobile=data.get('phone_number'), matrix_lead_id = data.get('matrix_lead_id'), matrix_reference_id = data.get('matrix_reference_id'))
            change_url = "/admin/diagnostic/lab/%s/change/"% (create_lead.id)

        if create_lead:
            response['status'] = 'success'
            response['id'] = create_lead.id
            response['url'] = change_url
            response['message'] = 'Lead Created Successfully'

        return Response(response)
