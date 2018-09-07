from django.db import models
from ondoc.authentication import models as auth_models
from django.contrib.postgres.fields import JSONField


class Visitor(auth_models.TimeStampedModel):
    device_info = models.BigIntegerField(null=True, default=None, blank=True)

    def __str__(self):
        return '{}'.format(self.device_info)

    def save(self, *args, **kwargs):
        self.device_info = self.get_device_info()
        super(Visitor, self).save(*args, **kwargs)

    def get_device_info(self):
        from ondoc.api.v1.utils import RawSql
        device_info = None
        query = '''select nextval('device_info_seq') as inc'''
        seq = RawSql(query).fetch_all()
        if seq:
            device_info = seq[0]['inc'] if seq[0]['inc'] else None
        return device_info

    @staticmethod
    def create_visitor():
        visitor = Visitor()
        visitor.save()
        return visitor

    class Meta:
        db_table = 'visitor'


class Visits(auth_models.TimeStampedModel):
    visitor = models.ForeignKey(Visitor, on_delete=models.CASCADE)

    def __str__(self):
        return '{}'.format(self.visitor)

    @staticmethod
    def create_visit(visitor_id):
        visit = Visits(visitor_id=visitor_id)
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
