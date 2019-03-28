from mongoengine import *
import uuid
import datetime


class TimeStampedModel():

    created_at = DateTimeField(default=datetime.datetime.utcnow())
    updated_at = DateTimeField(default=datetime.datetime.utcnow())

    class Meta:
        abstract = True


class TrackingEvent(DynamicDocument, TimeStampedModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = StringField(max_length=50, null=True, blank=True)
    visitor_id = UUIDField(editable=False)
    visit_id = UUIDField(editable=False)

    @classmethod
    def save_event(cls, *args, **kwargs):
        data = kwargs.get('data', None)
        event_name = kwargs.get('event_name', None)
        visit_id = kwargs.get('visit_id', None)
        visitor_id = kwargs.get('visitor_id', None)
        user = kwargs.get('user', None)
        triggered_at = data.get('triggered_at', None)
        if triggered_at:
            if len(str(triggered_at)) >= 13:
                triggered_at = triggered_at/1000
            triggered_at = datetime.datetime.utcfromtimestamp(triggered_at)
        else:
            triggered_at = datetime.datetime.utcnow()
        data.pop('triggered_at', None)
        if event_name and visit_id and visitor_id:
            event = cls(visitor_id=visitor_id, name=event_name, **data, visit_id=visit_id, user=user.id if user else None,
                        created_at=datetime.datetime.utcnow(), updated_at=datetime.datetime.utcnow(), triggered_at=triggered_at)
            event.save()
            return event
        return None


class TrackingVisit(DynamicDocument, TimeStampedModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = StringField(max_length=64, blank=True, null=True)
    data = DictField(blank=True, null=True)
    location = DictField(blank=True, null=True)
    user_agent = StringField(max_length=500, blank=True, null=True)
    visitor_id = UUIDField(editable=False)

class TrackingVisitor(DynamicDocument, TimeStampedModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_info = DictField(null=True, blank=True)
    client_category = StringField(max_length=100, blank=True, null=True)
