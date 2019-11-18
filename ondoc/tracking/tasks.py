from __future__ import absolute_import, unicode_literals
from celery import task
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
import logging

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





