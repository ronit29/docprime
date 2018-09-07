from django.db import models
from ondoc.authentication import models as auth_models
from django.contrib.postgres.fields import JSONField


class Visitor(auth_models.TimeStampedModel):
    device_info = JSONField(null=True, blank=True)

    def __str__(self):
        return '{}'.format(self.id)

    @staticmethod
    def create_visitor():
        visitor = Visitor()
        visitor.save()
        return visitor

    class Meta:
        db_table = 'visitor'


class Visits(auth_models.TimeStampedModel):
    ip_address = models.CharField(max_length=64, blank=True, null=True)
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE)

    def __str__(self):
        return '{}'.format(self.visitor)

    @staticmethod
    def create_visit(visitor_id, ip=None):
        visit = Visits(visitor_id=visitor_id, ip_address=ip)
        visit.save()
        return visit

    class Meta:
        db_table = 'visits'


class VisitorEvents(auth_models.TimeStampedModel):
    name = models.CharField(max_length=50, null=True, blank=True)
    data = JSONField(blank=True, null=True)
    visits = models.ForeignKey(Visits, on_delete=models.CASCADE)

    def __str__(self):
        return '{}'.format(self.name)

    class Meta:
        db_table = 'visitor_events'
