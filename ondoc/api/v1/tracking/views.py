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
        data = request.data
        del data['visitor_info']
        if data and isinstance(data, dict):
            event_name = data.get('event')
            if event_name:
                try:
                    user = None
                    if request.user.is_authenticated:
                        user = request.user
                    event = track_models.TrackingEvent(name=event_name, data=data, visit_id=visit_id, user=user)
                    event.save()
                    resp['success'] = "Event Saved Successfully!"
                except Exception as e:
                    resp['error'] = "Error Processing Event Data!"

                if event_name=='utm-events':
                    visit = track_models.TrackingVisit.objects.get(pk=visit_id)
                    if not visit.data:
                        ud = {}
                        ud['utm_campaign'] = data.get('utm_campaign')
                        ud['utm_medium'] = data.get('utm_medium')
                        ud['utm_source'] = data.get('utm_source')
                        ud['utm_term'] = data.get('utm_term')
                        visit.data = ud
                        visit.save()
                elif event_name=='visitor-info':
                    visitor = track_models.TrackingVisitor.objects.get(pk=visitor_id)
                    if not visitor.device_info:
                        ud = {}
                        ud['Device'] = data.get('device')
                        ud['Mobile'] = data.get('mobile')
                        ud['platform'] = data.get('platform')
                        visitor.device_info = ud
                        visitor.save()

            else:
                resp['error'] = "Event name not Found!"
        else:
            resp['error'] = "Invalid Data"

        #cookie = self.get_cookie(visitor_id, visit_id)
        response = JsonResponse(resp)
        #response.set_signed_cookie('visit', value=cookie, max_age=365*24*60*60, path='/')
        return response

    def get_visit(self, request):

        #cookie = request.get_signed_cookie('visit', None)
        visit_id = None
        visitor_id = None

        data=request.data.get('visitor_info')
        client_ip, is_routable = get_client_ip(request)
        if data:
            visit_id = data.get('visit_id')
            visitor_id = data.get('visitor_id')
            if visitor_id:
                track_models.TrackingVisitor.objects.get_or_create(id=visitor_id)
            if visit_id:
                track_models.TrackingVisit.objects.get_or_create(id=visit_id,
                    defaults={'visitor_id': visitor_id, 'ip_address': client_ip})

        return (visitor_id, visit_id)

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
            # if not get_time_diff:
            #     print('error')
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
