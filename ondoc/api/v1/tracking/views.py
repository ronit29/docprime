from ondoc.tracking import models as track_models
import logging
logger = logging.getLogger(__name__)
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
        data.pop('visitor_info', None)
        if data and isinstance(data, dict):
            event_name = data.get('event')
            if event_name:
                userAgent = data.get('userAgent', None)
                data.pop('userAgent', None)
                triggered_at = data.get('triggered_at', None)
                data.pop('created_at', None)
                if triggered_at:
                    triggered_at = datetime.datetime.fromtimestamp(triggered_at)
                try:
                    user = None
                    if request.user.is_authenticated:
                        user = request.user

                    event = track_models.TrackingEvent.save_event(event_name=event_name, data=data, visit_id=visit_id, user=user, triggered_at=triggered_at)
                    event.save()
                    resp['success'] = "Event Saved Successfully!"
                except Exception as e:
                    resp['error'] = "Error Processing Event Data!"

                visit = track_models.TrackingVisit.objects.get(pk=visit_id)
                modify_visit = False
                if event_name == 'utm-events':
                    if not visit.data:
                        ud = {}
                        ud['utm_campaign'] = data.get('utm_campaign')
                        ud['utm_medium'] = data.get('utm_medium')
                        ud['utm_source'] = data.get('utm_source')
                        ud['utm_term'] = data.get('utm_term')
                        ud['source'] = data.get('source')
                        ud['referrer'] = data.get('referrer')
                        visit.data = ud
                        modify_visit = True
                elif event_name == 'visitor-info':
                    visitor = track_models.TrackingVisitor.objects.get(pk=visitor_id)
                    if not visitor.device_info:
                        ud = {}
                        ud['Device'] = data.get('device')
                        ud['Mobile'] = data.get('mobile')
                        ud['platform'] = data.get('platform')
                        visitor.device_info = ud
                        visitor.save()
                elif event_name == "change-location":
                    if not visit.location:
                        visit.location = data.get('location', {})
                        modify_visit = True

                if not visit.user_agent and userAgent:
                    visit.user_agent = userAgent
                    modify_visit = True

                if modify_visit:
                    visit.save()

            else:
                resp['error'] = "Event name not Found!"
        else:
            resp['error'] = "Invalid Data"

        #cookie = self.get_cookie(visitor_id, visit_id)
        # response = JsonResponse(resp)
        #response.set_signed_cookie('visit', value=cookie, max_age=365*24*60*60, path='/')
        # return response
        if "error" in resp:
            return Response(status=status.HTTP_400_BAD_REQUEST, data=resp)
        else:
            return Response(status=status.HTTP_200_OK, data=resp)


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


class ServerHitMonitor(GenericViewSet):

    def create(self, request):
        resp = {}
        data = request.data
        if data and isinstance(data, dict):
            url = data.get('url', None)
            refferar = data.get('refferar', None)
            ip_address = data.get('ip', None)
            type = data.get('type', None)
            agent = data.get('agent',None)
            if not agent:
                agent = request.META.get('HTTP_USER_AGENT')

            data = data.get('data', {})
            if url:
                server_hit = track_models.ServerHitMonitor(url=url, refferar=refferar, ip_address=ip_address, type=type,
                                                           agent=agent, data=data)
                server_hit.save()
                resp['success'] = 'Server hit persisted successfully'
        else:
            resp['error'] = 'Invalid Data format.'
            logger.error("Not able to persist the server hit.")
        return Response(status=status.HTTP_201_CREATED, data=resp)
