from mongoengine import *
import uuid
import datetime

class TrackingEvent(DynamicDocument):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = StringField(max_length=50, null=True, blank=True)

    @classmethod
    def save_event(cls, *args, **kwargs):
        data = kwargs.get('data', None)
        event_name = kwargs.get('event_name', None)
        visit_id = kwargs.get('visit_id', None)
        visitor_id = kwargs.get('visitor_id', None)
        user = kwargs.get('user', None)
        triggered_at = kwargs.get('triggered_at', datetime.datetime.utcnow())
        if event_name and visit_id and visitor_id:
            event = cls(visitor_id=visitor_id, name=event_name, data=data, visit_id=visit_id, user=user, triggered_at=triggered_at)
            event.save()
            return event
        return None


class TrackingVisit(DynamicDocument):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = StringField(max_length=64, blank=True, null=True)
    data = DictField(blank=True, null=True)
    location = DictField(blank=True, null=True)
    user_agent = StringField(max_length=500, blank=True, null=True)

class TrackingVisitor(DynamicDocument):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_info = DictField(null=True, blank=True)
