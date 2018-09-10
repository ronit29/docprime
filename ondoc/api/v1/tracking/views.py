from ondoc.tracking import models as track_models
from rest_framework.response import Response
from rest_framework import status
from . import serializers
from rest_framework.viewsets import GenericViewSet
from rest_framework import status
import json
from django.http import JsonResponse
import datetime
from ondoc.api.v1.utils import get_time_delta_in_minutes, aware_time_zone
from ipware import get_client_ip
from uuid import UUID

#from django.utils import timezone


class EventCreateViewSet(GenericViewSet):

    def create(self, request):
        visitor_id, visit_id = self.get_visit(request)
        resp = {}
        if request.data and isinstance(request.data, dict):
            event_name = request.data.get('event')
            if event_name:
                try:
                    user = None
                    if request.user.is_authenticated:
                        user = request.user
                    event = track_models.TrackingEvent(name=event_name, data=request.data, visit_id=visit_id, user=user)
                    event.save()
                    resp['success'] = "Event Saved Successfully!"
                except Exception:
                    resp['error'] = "Error Processing Event Data!"
            else:
                resp['error'] = "Event name not Found!"
        else:
            resp['error'] = "Invalid Data"

        cookie = self.get_cookie(visitor_id, visit_id)    
        response = JsonResponse(resp)
        response.set_signed_cookie('visit', value=cookie, max_age=365*24*60*60, path='/')
        return response

    def get_visit(self, request):

        cookie = request.get_signed_cookie('visit', None)
        visitor_id = None
        visit_id = None
        last_visit_time = None
        visit_expired = False

        if cookie:
            cookie = json.loads(cookie)

            visitor_id = cookie.get('visitor_id', None)
            visit_id = cookie.get('visit_id', None)
            last_visit_time = cookie.get('last_visit_time', None)

        if not visitor_id:
            print('visitor not found')
            visitor = track_models.TrackingVisitor.create_visitor()
            visitor_id = visitor.id

        if last_visit_time:
            get_time_diff = get_time_delta_in_minutes(last_visit_time)
            if int(get_time_diff) > 30:
                visit_expired = True
        else:
            visit_expired = True

        if not visit_id or visit_expired:
            client_ip, is_routable = get_client_ip(request)
            visit = track_models.TrackingVisit.create_visit(visitor_id, client_ip)
            visit_id = visit.id

        return (visitor_id, visit_id)


    def get_cookie(self, visitor_id, visit_id):

        last_visit_time = datetime.datetime.now()
        new_cookie = dict()
        new_cookie['visitor_id'] = visitor_id
        new_cookie['visit_id'] = visit_id
        new_cookie['last_visit_time'] = datetime.datetime.strftime(last_visit_time, '%Y-%m-%d %H:%M:%S')

        new_cookie = json.dumps(new_cookie, cls=UUIDEncoder)
        return new_cookie

class UUIDEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            # if the obj is uuid, we simply return the value of uuid
            return obj.hex
        return json.JSONEncoder.default(self, obj)
