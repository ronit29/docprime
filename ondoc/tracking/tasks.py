from __future__ import absolute_import, unicode_literals
from celery import task
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
import logging
from rest_framework import status
import datetime, pytz
from django.conf import settings
from copy import deepcopy
from rest_framework.response import Response
from django.db import transaction
from mongoengine.errors import NotUniqueError
from ipware import get_client_ip

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=2)
def create_visit_to_mongo(self, data):
    from ondoc.authentication.models import User

    client_ip = data.get('client_ip', '')
    is_routable = data.get('is_routable', '')
    req_data = data.get('req_data', '')
    user_id = data.get('user_id', None)

    resp = {}
    try:
        visitor_id, visit_id = get_visit(client_ip, is_routable, req_data)

        if req_data and isinstance(req_data, dict):
            req_data = deepcopy(req_data)
            req_data.pop('visitor_info', None)

            error_message = ""
            if not visitor_id or not visit_id:
                error_message = "Couldn't save event, Couldn't create visit/visitor - " + str(visit_id) + " / " + str(
                    visitor_id)
                resp['error'] = error_message

            event_name = req_data.get('event', None) or req_data.get('Action', None)

            if not event_name:
                error_message = "Couldn't save anonymous event - " + str(data) + " For visit/visitor - " + str(
                    visit_id) + " / " + str(visitor_id)
                resp['error'] = error_message

            userAgent = req_data.get('userAgent', None)
            req_data.pop('userAgent', None)
            triggered_at = req_data.get('triggered_at', None)
            tz = pytz.timezone(settings.TIME_ZONE)
            req_data.pop('created_at', None)

            if triggered_at:
                if len(str(triggered_at)) >= 13:
                    triggered_at = triggered_at / 1000
                triggered_at = datetime.datetime.fromtimestamp(triggered_at, tz)

            try:
                if user_id:
                    user = User.objects.filter(id=user_id).first()
                else:
                    user = None

                if settings.MONGO_STORE:
                    track_mongo_models.TrackingEvent.save_event(visitor_id=visitor_id, event_name=event_name, data=req_data,
                                                                visit_id=visit_id, user=user, triggered_at=triggered_at)

                if not "error" in resp:
                    resp['success'] = "Event Saved Successfully!"
            except Exception as e:
                resp['error'] = "Error Processing Event Data!"
                print(e)
        else:
            error_message = "Couldn't save event without data - " + str(data) + " For visit/visitor - " + str(visit_id) + " / " + str(visitor_id)
            resp['error'] = error_message

        if not "error" in resp:
            if settings.MONGO_STORE:
                modify_visit(event_name, visit_id, visitor_id, data, userAgent, track_mongo_models.TrackingVisit, track_mongo_models.TrackingVisitor)
    except Exception as e:
        resp['error'] = "Error Processing Event Data!"
        print(e)
        print(resp)
        countdown_time = (2 ** self.request.retries) * 60 * 10
        self.retry([data], countdown=countdown_time)


def get_visit(client_ip, is_routable, req_data):
    data = None
    visit_id = None
    visitor_id = None

    if 'visitor_info' in req_data:
        data = req_data.get('visitor_info')
    client_ip, is_routable = client_ip, is_routable
    if data:
        visit_id = data.get('visit_id')
        visitor_id = data.get('visitor_id')

        if visitor_id:
            if settings.MONGO_STORE:
                mongo_visitor = track_mongo_models.TrackingVisitor.objects.filter(id=visitor_id).first()
                if not mongo_visitor:
                    try:
                        with transaction.atomic():
                            track_mongo_models.TrackingVisitor.objects.create(id=visitor_id)
                    except NotUniqueError as e:
                        pass

        if visit_id:
            if settings.MONGO_STORE:
                mongo_visit = track_mongo_models.TrackingVisit.objects.filter(id=visit_id).first()
                if not mongo_visit:
                    try:
                        with transaction.atomic():
                            track_mongo_models.TrackingVisit.objects.create(id=visit_id, visitor_id=visitor_id, ip_address=client_ip)
                    except NotUniqueError as e:
                        pass

    return visitor_id, visit_id


def modify_visit(event_name, visit_id, visitor_id, data, userAgent, VISIT_MODEL, VISITOR_MODEL):
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



