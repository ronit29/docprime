from mongoengine import *
import uuid, datetime, json
from django.conf import settings
from django.utils import timezone


class TimeStampedModel():

    created_at = DateTimeField(default=datetime.datetime.utcnow())
    updated_at = DateTimeField(default=datetime.datetime.utcnow())

    class Meta:
        abstract = True


class PgLogs(DynamicDocument, TimeStampedModel):
    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = LongField(null=True, blank=True, editable=False)
    pg_transaction_id = LongField(null=True, blank=True, editable=False)
    response = DictField(blank=True, null=True)

    @classmethod
    def save_pg_response(cls, order_id, txn_id, response=None, request=None):
        if request and not isinstance(request, dict):
            request = json.loads(request)
        if response and not isinstance(response, dict):
            response = json.loads(response)
        if settings.MONGO_STORE:
            PgLogs.objects.create(pg_transaction_id=txn_id,
                                  order_id=order_id,
                                  response=response,
                                  request=request,
                                  created_at=timezone.localtime(),
                                  updated_at=timezone.localtime())