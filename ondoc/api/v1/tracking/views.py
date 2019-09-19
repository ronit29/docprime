from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
import logging



logger = logging.getLogger(__name__)
from rest_framework.response import Response
from rest_framework import status
from . import serializers
from rest_framework.viewsets import GenericViewSet
from rest_framework import status
import json
from django.http import JsonResponse
import datetime, pytz
from ondoc.api.v1.utils import get_time_delta_in_minutes, aware_time_zone
from ipware import get_client_ip
from uuid import UUID
from django.conf import settings
from django.db import IntegrityError
from django.db import transaction
from mongoengine.errors import NotUniqueError
from copy import deepcopy

#from django.utils import timezone


class EventCreateViewSet(GenericViewSet):

    @transaction.non_atomic_requests
    def create(self, request):
        from ondoc.tracking.models import TrackingSaveLogs

        visitor_id, visit_id = self.get_visit(request)
        resp = {}
        data = request.data

        if data and isinstance(data, dict):
            try:
                with transaction.atomic():
                    TrackingSaveLogs.objects.create(data=data)
            except Exception as e:
                logger.error(str(e))

            data = deepcopy(data)
            data.pop('visitor_info', None)

            error_message = ""
            if not visitor_id or not visit_id:
                error_message = "Couldn't save event, Couldn't create visit/visitor - " + str(visit_id) + " / " + str(
                    visitor_id)
                # raise Exception(error_message)
                resp['error'] = error_message

            event_name = data.get('event', None) or data.get('Action', None)

            if not event_name:
                error_message = "Couldn't save anonymous event - " + str(data) + " For visit/visitor - " + str(
                    visit_id) + " / " + str(visitor_id)
                # raise Exception(error_message)
                resp['error'] = error_message

            userAgent = data.get('userAgent', None)
            data.pop('userAgent', None)
            triggered_at = data.get('triggered_at', None)
            tz = pytz.timezone(settings.TIME_ZONE)
            data.pop('created_at', None)

            if triggered_at:
                if len(str(triggered_at)) >= 13:
                    triggered_at = triggered_at / 1000
                triggered_at = datetime.datetime.fromtimestamp(triggered_at, tz)

            try:
                user = None
                if request.user.is_authenticated:
                    user = request.user

                track_models.TrackingEvent.save_event(event_name=event_name, data=data, visit_id=visit_id, user=user,
                                                      triggered_at=triggered_at)
                if settings.MONGO_STORE:
                    track_mongo_models.TrackingEvent.save_event(visitor_id=visitor_id, event_name=event_name, data=data,
                                                                visit_id=visit_id, user=user, triggered_at=triggered_at)

                if not "error" in resp:
                    resp['success'] = "Event Saved Successfully!"

            except Exception as e:
                # logger.error("Error saving event - " + str(e))
                resp['error'] = "Error Processing Event Data!"

        else:
            error_message = "Couldn't save event without data - " + str(data) + " For visit/visitor - " + str(visit_id) + " / " + str(visitor_id)
            # raise Exception(error_message)
            resp['error'] = error_message

        if not "error" in resp:
            self.modify_visit(event_name, visit_id, visitor_id, data, userAgent, track_models.TrackingVisit, track_models.TrackingVisitor)
            if settings.MONGO_STORE:
                self.modify_visit(event_name, visit_id, visitor_id, data, userAgent, track_mongo_models.TrackingVisit, track_mongo_models.TrackingVisitor)

        if "error" in resp:
            return Response(status=status.HTTP_400_BAD_REQUEST, data=resp)
        else:
            return Response(status=status.HTTP_200_OK, data=resp)

    @transaction.non_atomic_requests
    def modify_visit(self, event_name, visit_id, visitor_id, data, userAgent, VISIT_MODEL, VISITOR_MODEL):
        visit = VISIT_MODEL.objects.get(id=visit_id)
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
            modify_visitor = False
            visitor = VISITOR_MODEL.objects.get(id=visitor_id)
            if not visitor.device_info:
                ud = {}
                ud['Device'] = data.get('Device')
                ud['Mobile'] = data.get('Mobile')
                ud['platform'] = data.get('platform')
                visitor.device_info = ud
                modify_visitor = True
            if not visitor.client_category:
                visitor.client_category = data.get('Category', "")
                modify_visitor = True
            if modify_visitor:
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

    @transaction.non_atomic_requests
    def get_visit(self, request):
        data = None
        #cookie = request.get_signed_cookie('visit', None)
        visit_id = None
        visitor_id = None

        if 'visitor_info' in request.data:
            data = request.data.get('visitor_info')
        client_ip, is_routable = get_client_ip(request)
        if data:
            visit_id = data.get('visit_id')
            visitor_id = data.get('visitor_id')

            if visitor_id:
                ex_visitor = track_models.TrackingVisitor.objects.filter(id=visitor_id).first()
                if not ex_visitor:
                    try:
                        with transaction.atomic():
                            ex_visitor = track_models.TrackingVisitor(id=visitor_id)
                            ex_visitor.save()
                    except IntegrityError as e:
                        ex_visitor = track_models.TrackingVisitor.objects.filter(id=visitor_id).first()

                if settings.MONGO_STORE:
                    mongo_visitor = track_mongo_models.TrackingVisitor.objects.filter(id=visitor_id).first()
                    if not mongo_visitor:
                        try:
                            with transaction.atomic():
                                track_mongo_models.TrackingVisitor.objects.create(id=visitor_id,
                                                                                  created_at=ex_visitor.created_at, updated_at=ex_visitor.updated_at)
                        except NotUniqueError as e:
                            pass

            if visit_id:
                ex_visit = track_models.TrackingVisit.objects.filter(id=visit_id).first()
                if not ex_visit:
                    try:
                        with transaction.atomic():
                            ex_visit = track_models.TrackingVisit(id=visit_id, visitor_id=visitor_id, ip_address=client_ip)
                            ex_visit.save()
                    except IntegrityError as e:
                        ex_visit = track_models.TrackingVisit.objects.filter(id=visit_id).first()

                if settings.MONGO_STORE:
                    mongo_visit = track_mongo_models.TrackingVisit.objects.filter(id=visit_id).first()
                    if not mongo_visit:
                        try:
                            with transaction.atomic():
                                track_mongo_models.TrackingVisit.objects.create(id=visit_id, visitor_id=visitor_id, ip_address=client_ip,
                                                                                created_at=ex_visit.created_at, updated_at=ex_visit.updated_at)
                        except NotUniqueError as e:
                            pass

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
