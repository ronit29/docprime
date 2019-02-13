from django.db import models
from django.contrib.postgres.fields import JSONField
import uuid
from ondoc.authentication import models as auth_models
from django.contrib.postgres.fields import JSONField
from django.conf import settings


class TrackingVisitor(auth_models.TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    device_info = JSONField(null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.id)

    @staticmethod
    def create_visitor():
        visitor = TrackingVisitor()
        visitor.save()
        return visitor

    class Meta:
        db_table = 'tracking_visitor'


class TrackingVisit(auth_models.TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ip_address = models.CharField(max_length=64, blank=True, null=True)
    visitor = models.ForeignKey(TrackingVisitor, on_delete=models.CASCADE)
    data = JSONField(blank=True, null=True)
    location = JSONField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True, null=True)

    def __str__(self):
        return '{}'.format(self.visitor)

    @staticmethod
    def create_visit(visitor_id, ip=None):
        visit = TrackingVisit(visitor_id=visitor_id, ip_address=ip)
        visit.save()
        return visit

    class Meta:
        db_table = 'tracking_visit'


class TrackingEvent(auth_models.TimeStampedModel):
    DoctorAppointmentBooked = 'DoctorAppointmentBooked'
    LabAppointmentBooked = 'LabAppointmentBooked'

    ACTION_EVENTS = {
        DoctorAppointmentBooked : 'doctor-appointment-booked',
        LabAppointmentBooked : 'lab-appointment-booked',
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, null=True, blank=True)
    data = JSONField(blank=True, null=True)
    visit = models.ForeignKey(TrackingVisit, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,  on_delete=models.SET_NULL, default=None,
                                blank=True, null=True)
    triggered_at = models.DateTimeField(null=True, blank=True)

    @classmethod
    def save_event(cls, *args, **kwargs):
        data = kwargs.get('data', None)
        event_name = kwargs.get('event_name', None)
        visit_id = kwargs.get('visit_id', None)
        user = kwargs.get('user', None)
        triggered_at = kwargs.get('triggered_at', None)
        if event_name and data and visit_id and user:
            event = cls(name=event_name, data=data, visit_id=visit_id, user=user, triggered_at=triggered_at)
            event.save()
            return event
        return None

    @classmethod
    def build_event_data(cls, user, action, *args, **kwargs):
        if action not in cls.ACTION_EVENTS:
            return None

        event_data = {
            'Category': 'ConsumerApp', 'Action': action, 'CustomerID': user.id,
            'leadid': kwargs.get("appointmentId", None), 'event': cls.ACTION_EVENTS[action]
        }

        return event_data

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        db_table = 'tracking_event'


class ServerHitMonitor(auth_models.TimeStampedModel):

    url = models.TextField(null=True)
    agent = models.TextField(null=True)
    data = JSONField(null=True)
    refferar = models.CharField(max_length=5000, default=None, null=True)
    ip_address = models.CharField(max_length=5000, null=True, default=None)
    type = models.CharField(max_length=50, null=True, default=None)


    class Meta:
        db_table = 'server_hit_monitor'
