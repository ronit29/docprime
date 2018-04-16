from ondoc.doctor.models import Doctor, Specialization, MedicalService
from .serializers import DoctorSerializer, SpecializationSerializer, MedicalServiceSerializer, DoctorApiReformData
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated


class GenericSearchView(APIView):
    """
    List all snippets, or create a new snippet.
    """
    # permission_classes = (IsAuthenticated,)

    def get(self, request, version="v1", format=None):
        search_key = request.GET.get("key", "")

        specializations = Specialization.objects.filter(name__icontains=search_key)
        serialized_specifn = SpecializationSerializer(specializations, many=True)
        
        medical_services = MedicalService.objects.filter(name__icontains=search_key)
        serialized_medical_serv = MedicalServiceSerializer(medical_services, many=True)
        
        resp = {
            "message": "message",
            "result": [{
            "type": "medicalServices",
            "name": "Medical Services",
            "data": serialized_specifn.data
        },{
            "type": "specialization",
            "name": "Specialization",
            "data": serialized_medical_serv.data
        }]}
        return Response(resp)


class DoctorView(APIView):
    """
    List all snippets, or create a new snippet.
    """
    # permission_classes = (IsAuthenticated,)

    def get(self, request, version="v1", format=None):
        doctors = Doctor.objects.all()
        serialized_doctors = DoctorApiReformData(doctors, many=True)
                
        return Response(serialized_doctors.data)
