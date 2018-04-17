from ondoc.doctor.models import Doctor, Specialization, MedicalService, DoctorHospital, Symptoms
from .serializers import DoctorSerializer, SpecializationSerializer, MedicalServiceSerializer, \
                        DoctorApiReformData, DoctorHospitalSerializer, SymptomsSerializer
from .services import ReformScheduleService
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

        symptoms = Symptoms.objects.filter(name__icontains=search_key)
        serialized_symptoms = SymptomsSerializer(symptoms, many=True)
        
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
        },{
            "type": "symptoms",
            "name": "Symptoms",
            "data": serialized_symptoms.data
        }]}
        return Response(resp)


class DoctorAvailability(APIView):
    """
    Explicitly extracts a doctor's schedule with more details.
    """
    # permission_classes = (IsAuthenticated,)

    def get(self, request, version="v1", format=None):
        doctor_id = request.GET.get("id", None)

        try:
            schedule = DoctorHospital.objects.filter(doctor_id = doctor_id).select_related('doctor',
             'hospital')
        except Doctor.DoesNotExist as e:
            raise Exception('No doctor with specified id found')

        serialized_schedule = DoctorHospitalSerializer(schedule, many=True)
        schedule_obj = ReformScheduleService(schedule = serialized_schedule.data, days = 10)

        return Response(schedule_obj.get_data())


class DoctorView(APIView):
    """
    Lists all the doctors and their schedule.
    """
    # permission_classes = (IsAuthenticated,)

    def get(self, request, version="v1", format=None):
        doctors = Doctor.objects.prefetch_related('qualificationSpecialization', 'profile_img',
            'availability', 'pastExperience', 'availability__hospital', 'qualificationSpecialization__qualification'
            , 'qualificationSpecialization__specialization').all()
        serialized_doctors = DoctorApiReformData(doctors, many=True)
                
        return Response(serialized_doctors.data)
