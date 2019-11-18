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
def save_visit_to_mongo(self, data):
    try:
        visitor_id = data.get('visitor_id', '')
        event_name = data.get('event_name', '')
        event_data = data.get('event_data', '')
        visit_id = data.get('visit_id', '')
        user = data.get('user', None)
        triggered_at = data.get('triggered_at', '')

        track_mongo_models.TrackingEvent.save_event(visitor_id=visitor_id, event_name=event_name, data=event_data,
                                                    visit_id=visit_id, user=user, triggered_at=triggered_at)
    except Exception as e:
        logger.error("Error in Celery. Failed to save visit to mongo- " + str(e))
        countdown_time = (2 ** self.request.retries) * 60 * 10
        self.retry([data], countdown=countdown_time)


@task(bind=True, max_retries=2)
def modify_visit_to_mongo(self, data):
    try:
        event_name = data.get('event_name', '')
        visit_id = data.get('visit_id', '')
        visitor_id = data.get('visitor_id', '')
        event_data = data.get('event_data', '')
        user_agent = data.get('user_agent', '')

        visit = track_models.TrackingVisit.objects.get(id=visit_id)
        modify_visit = False
        if event_name == 'utm-events':
            if not visit.data:
                ud = {}
                ud['utm_campaign'] = event_data.get('utm_campaign')
                ud['utm_medium'] = event_data.get('utm_medium')
                ud['utm_source'] = event_data.get('utm_source')
                ud['utm_term'] = event_data.get('utm_term')
                ud['source'] = event_data.get('source')
                ud['referrer'] = event_data.get('referrer')
                visit.data = ud
                modify_visit = True
        elif event_name == 'visitor-info':
            modify_visitor = False
            visitor = track_models.TrackingVisitor.objects.get(id=visitor_id)
            if not visitor.device_info:
                ud = {}
                ud['Device'] = event_data.get('Device')
                ud['Mobile'] = event_data.get('Mobile')
                ud['platform'] = event_data.get('platform')
                visitor.device_info = ud
                modify_visitor = True
            if not visitor.client_category:
                visitor.client_category = event_data.get('Category', "")
                modify_visitor = True
            if modify_visitor:
                visitor.save()
        elif event_name == "change-location":
            if not visit.location:
                visit.location = event_data.get('location', {})
                modify_visit = True

        if not visit.user_agent and user_agent:
            visit.user_agent = user_agent
            modify_visit = True

        if modify_visit:
            visit.save()

    except Exception as e:
        logger.error("Error in Celery. Failed to modify visit to mongo- " + str(e))
        countdown_time = (2 ** self.request.retries) * 60 * 10
        self.retry([data], countdown=countdown_time)


def create_visit_to_mongo(self, data):
    client_ip = data.get('client_ip', '')
    is_routable = data.get('is_routable', '')
    req_data = data.get('req_data')

    resp = {}
    try:
        visitor_id, visit_id = self.get_visit(client_ip, is_routable, req_data)

        data = request.data

        if data and isinstance(data, dict):
            # try:
            #     with transaction.atomic():
            #         TrackingSaveLogs.objects.create(data=data)
            # except Exception as e:
            #     logger.error(str(e))

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

                # track_models.TrackingEvent.save_event(event_name=event_name, data=data, visit_id=visit_id,
                #                                       user=user,
                #                                       triggered_at=triggered_at)
                if settings.MONGO_STORE:
                    # track_mongo_models.TrackingEvent.save_event(
                    #                                  visitor_id=visitor_id, event_name=event_name, data=data,
                    #                                  visit_id=visit_id, user=user, triggered_at=triggered_at)

                    save_visit_to_mongo.apply_async(({'visitor_id': visitor_id, 'event_name': event_name, 'event_data': data,
                                                      'visit_id': visit_id, 'user': user, 'triggered_at': triggered_at},), countdown=5, queue=settings.RABBITMQ_LOGS_QUEUE)

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
            # self.modify_visit(event_name, visit_id, visitor_id, data, userAgent, track_models.TrackingVisit, track_models.TrackingVisitor)
            if settings.MONGO_STORE:
                # self.modify_visit(event_name, visit_id, visitor_id, data, userAgent, track_mongo_models.TrackingVisit, track_mongo_models.TrackingVisitor)
                modify_visit_to_mongo.apply_async(({'event_name': event_name, 'visit_id': visit_id, 'visitor_id': visitor_id, 'event_data': data, 'user_agent': userAgent},), countdown=5, queue=settings.RABBITMQ_LOGS_QUEUE)
    except Exception as e:
        # logger.info("Error saving event - " + str(e))
        resp['error'] = "Error Processing Event Data!"

    # if "error" in resp:
    #     return Response(status=status.HTTP_400_BAD_REQUEST, data=resp)
    # else:
    #     return Response(status=status.HTTP_200_OK, data=resp)


def get_visit(self, client_ip, is_routable, req_data):
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





