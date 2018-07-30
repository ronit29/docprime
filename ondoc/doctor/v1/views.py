from rest_framework import status
from django.db.models import Q
from ondoc.doctor.models import Doctor, Specialization, MedicalService, DoctorHospital, Symptoms, OpdAppointment, Hospital, OpdAppointment, DoctorLeave
from .serializers import DoctorSerializer, SpecializationSerializer, MedicalServiceSerializer, \
                        DoctorApiReformData, DoctorHospitalSerializer, SymptomsSerializer, DoctorProfileSerializer, OpdAppointmentSerializer, HospitalSerializer, DoctorLeaveSerializer
from .services import ReformScheduleService
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import TokenAuthentication
from rest_framework.pagination import PageNumberPagination

from django.db.models import Prefetch
from datetime import datetime


class BasePagination(PageNumberPagination):
    def get_paginated_response(self, data, keyword = "results"):
        return Response({
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link()
            },
            'total_results': self.page.paginator.count,
            'total_pages': self.page.paginator.num_pages,
            keyword: data
        })


class DoctorPagination(BasePagination):
    def get_paginated_response(self, data):
        return super().get_paginated_response(data, keyword = "doctors")


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
        paginator = DoctorPagination()
        doctors = Doctor.objects.prefetch_related('qualificationSpecialization', 'profile_img',
            'availability', 'pastExperience', 'availability__hospital', 'qualificationSpecialization__qualification'
            , 'qualificationSpecialization__specialization').all()
        
        page = paginator.paginate_queryset(doctors, request)
        serialized_doctors = DoctorApiReformData(page, many=True)

        return paginator.get_paginated_response(serialized_doctors.data)


class DoctorProfile(APIView):
    """
    Return Detailed doctor profile
    """

    authentication_classes = (TokenAuthentication, )
    permission_classes = (IsAuthenticated,)

    def get(self, request, version="v1", format=None):

        try:
            doctor_profile = Doctor.objects.filter(user=request.user).prefetch_related(Prefetch('availability', queryset=DoctorHospital.objects.distinct('hospital_id').order_by('hospital_id','fees')))

            # count all upcoming/accepted appointments
            doctor_appointments = OpdAppointment.objects.filter(doctor=doctor_profile[0],status=2).count()

        except Doctor.DoesNotExist as e:
            raise Exception('No doctor linked with the logged in User')

        serialized_doctor = DoctorProfileSerializer(doctor_profile[0])

        return Response({
            "profile" : serialized_doctor.data,
            "doctor_appointments" : doctor_appointments
        })


class DoctorAppointments(APIView):
    """
    Return Appointments for a doctor
    """

    def get(self, request, version="v1", format=None):

        doctor_id = 2
        response = {
            "appointments" : []
        }

        appointments = OpdAppointment.objects.filter(doctor=doctor_id)
        appointmentsData = OpdAppointmentSerializer(appointments, many=True).data

        response['appointments'] = appointmentsData

        return Response(response)

    def put(self, request, version="v1", format=None):

        # TODO : Authenticate this request so only the assigned doctor or the patient
        #        is able to change the status of the appointment id.

        appointment_id = request.data['appointment_id']
        status = request.data['status']
        
        try:
            selected_appointment = OpdAppointment.objects.get(id=appointment_id)
            selected_appointment.status = status
            selected_appointment.save()
            
        except OpdAppointment.DoesNotExist:
            return Response('No Appointment found with the ID provided',status=404)
        except Exception as e:
            return Response(str(e),status=500)

        return Response({
            "message" : "Appointment modified"
        })

    def post(self, request, version="v1", format='json'):

        # TODO : Authenticate this request so only the assigned doctor or the patient
        #        is able to change the status of the appointment id
        try:
            request_data = request.data
            request_data['doctor'] = Doctor.objects.get(id=request.data['doctor_id'])
            request_data['hospital'] = Hospital.objects.get(id=request.data['hospital_id'])
            request_data['profile'] = UserProfile.objects.get(id=request.data['profile_id'])
            request_data['time_slot_start'] = datetime.utcfromtimestamp(request_data['time_slot_start'] / 1000)
            request_data['time_slot_end'] = datetime.utcfromtimestamp(request_data['time_slot_end'] / 1000)
            time_slot_start = request_data['time_slot_start']
            time_slot_end = request_data['time_slot_end']
            day = time_slot_start.weekday()
            start_hour = time_slot_start.hour
            end_hour = time_slot_end.hour

            doctorHospitals = DoctorHospital.objects.filter(Q(doctor=request_data['doctor']) &
                                                            Q(hospital=request_data['hospital'])
                                                            & Q(day= day)& Q(start__lte=start_hour)&Q(end__gte=end_hour))

            serialized_schedule = DoctorHospitalSerializer(doctorHospitals, many=True)
            if not serialized_schedule.data[0]:
                return Response("Doctor Hospital not found", status=status.HTTP_404_NOT_FOUND)
            fees = serialized_schedule.data[0]['fees']
            request_data['fees']=fees
            opd_appointment_serializer = OpdAppointmentSerializer(data=request_data,context=request_data)

        except Doctor.DoesNotExist:
            return Response('No Doctor found with the ID provided',status=404)
        except Hospital.DoesNotExist:
            return Response('No Hospital found with the ID provided', status=404)
        except UserProfile.DoesNotExist:
            return Response('No UserProfile found with the ID provided', status=404)
        except DoctorHospital.DoesNotExist:
            return Response('No DoctorHospital found with the ID provided', status=404)

        if opd_appointment_serializer.is_valid(raise_exception=True):
            opd_appointment = opd_appointment_serializer.save()
            return Response("Successfully Created", status=200)
        else:
            return Response(opd_appointment_serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DoctorHospitalAvailability(APIView):

    # authentication_classes = (TokenAuthentication, )
    # permission_classes = (IsAuthenticated,)

    def get(self, request, version="v1", format=None):

        doctor_id = request.GET.get("doctor_id", 2)
        hospital_id = request.GET.get("hospital_id", 1)
    
        schedule = DoctorHospital.objects.filter(doctor_id=doctor_id, hospital_id=hospital_id)
        serialized_schedule = DoctorHospitalSerializer(schedule, many=True)
        return Response(serialized_schedule.data)

    def post(self, request, version="v1", format='json'):

        request_data = request.data

        doctor = Doctor.objects.get(id=request_data['doctor_id'])
        hospital = Hospital.objects.get(id=request_data['hospital_id'])

        doctor_hospital_serializer = DoctorHospitalSerializer(data=request_data,context={'doctor':doctor, 'hospital':hospital})

        if doctor_hospital_serializer.is_valid(raise_exception=True):

            doctor_hospital_serializer.save()
            return Response("Successfully Created", status=200)
            
        else:
            return Response(doctor_hospital_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, version="v1", format='json'):

        request_data = request.data

        availability = DoctorHospital.objects.get(id=request_data['id'])

        availability.start = request_data.get('start', availability.start)
        availability.end = request_data.get('end', availability.end)
        availability.day = request_data.get('day', availability.day)
        availability.fees = request_data.get('fees', availability.fees)

        availability.save()

        return Response("Successfully Modified", status=200)


class DoctorBlockCalendar(APIView):
    """
    Return Leaves for a doctor
    """

    def get(self, request, version="v1", format=None):
        if request.GET.get("doctor_id") is not None:
            doctor_id = request.GET.get("doctor_id")
            leaves = DoctorLeave.objects.filter(doctor_id=doctor_id)
            serialized_leaves = DoctorLeaveSerializer(leaves, many=True)
            return Response(serialized_leaves.data)
        elif request.GET.get("leave_id") is not None:
            leave_id = request.GET.get("leave_id")
            leave = DoctorLeave.objects.get(id=leave_id)
            serialized_leave = DoctorLeaveSerializer(leave, many=False)
            return Response(serialized_leave.data)

    def post(self, request, version="v1", format='json'):
        request_data = request.data
        doctor = Doctor.objects.get(id=request_data['doctor_id'])
        doctor_leave_serializer = DoctorLeaveSerializer(data=request_data, context={'doctor': doctor})
        if doctor_leave_serializer.is_valid(raise_exception=True):
            doctor_leave_serializer.save()
            return Response("Successfully Created", status=200)
        else:
            return Response(doctor_leave_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, version="v1", format='json'):

        request_data = request.data
        leave = DoctorLeave.objects.get(id=request_data['id'])
        leave.start_date = request_data.get('start_date', leave.start_date)
        leave.end_date = request_data.get('end_date', leave.end_date)
        leave.start_time = request_data.get('start_time', leave.start_time)
        leave.end_time = request_data.get('end_time', leave.end_time)
        leave.save()

        return Response("Successfully Modified", status=200)


