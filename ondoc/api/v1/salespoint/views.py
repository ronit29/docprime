from rest_framework import viewsets, status

from ondoc.authentication.backends import SalespointAuthentication
from ondoc.diagnostic.models import LabAppointment
from rest_framework.response import Response


class SalespointAppointmentViewSet(viewsets.GenericViewSet):
    authentication_classes = (SalespointAuthentication,)

    def update_status(self, request):
        data = request.data
        appointment_id = data.get('appointment_id', None)
        status = data.get('status_id', None)

        if appointment_id and status:
            if status not in [6, 7]:
                return Response({"error": True, "message": "Not a valid status."})

            appointment_obj = LabAppointment.objects.filter(id=appointment_id).first()
            if appointment_obj and appointment_obj.booked_by_spo():
                if appointment_obj.status not in [6, 7]:
                    appointment_obj.status = status
                    appointment_obj.save()
                    return Response({"error": False, "message": "Appointment status changed successfully."})
                else:
                    return Response({"error": True, "message": "Cancelled or Completed appointment cannot be saved."})

            return Response({"error": True, "message": "Appointment not found."})
        else:
            return Response({"error": True, "message": "Parameters missing."})

    def status_list(self, request):
        status_list = LabAppointment.STATUS_CHOICES
        resp_status = list()
        for status in status_list:
            status_dict = {'id': status[0], 'status': status[1]}
            resp_status.append(status_dict)

        return Response({'status_master': resp_status})

