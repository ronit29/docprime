from mongoengine import *
import uuid

class TrackingEvent(DynamicDocument):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = StringField(max_length=50, null=True, blank=True)

class TrackingVisit(DynamicDocument):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

class TrackingVisitor(DynamicDocument):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
