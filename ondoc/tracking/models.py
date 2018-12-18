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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, null=True, blank=True)
    data = JSONField(blank=True, null=True)
    visit = models.ForeignKey(TrackingVisit, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,  on_delete=models.SET_NULL, default=None,
                                blank=True, null=True)

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
