from ondoc.tracking import models as track_models
from rest_framework.response import Response
from rest_framework import status
from . import serializers
from rest_framework.viewsets import GenericViewSet
from rest_framework import status
import json

class EventCreateViewSet(GenericViewSet):

    def create(self, request):
        resp = {}
        if request.data and isinstance(request.data, dict):
            event_name = request.data.get('event')
            if event_name:
                visit_id = request.session.get('visit_id')
                if visit_id:
                    try:
                        event = track_models.VisitorEvents(name=event_name, data=request.data, visits_id=visit_id)
                        event.save()
                    except Exception:
                        resp['error'] = "Error Processing Event Data!"
                    resp['success'] = "Response Saved Successfully!"
            else:
                resp['error'] = "Event name not Found!"
        else:
            return Response({"error": "Invalid Data"}, status=status.HTTP_400_BAD_REQUEST)
        return Response(resp)



