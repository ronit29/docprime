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
    UNKNOWN = 0
    TXN_REQUEST = 1
    TXN_RESPONSE = 2
    TXN_CAPTURED = 3
    TXN_RELEASED = 4
    DUMMY_TXN = 5

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = LongField(null=True, blank=True, editable=False)
    pg_transaction_id = LongField(null=True, blank=True, editable=False)
    response = DictField(blank=True, null=True)
    log_type = IntField(null=True, blank=True)

    @classmethod
    def save_pg_response(cls, log_type=0, order_id=None, txn_id=None, response=None, request=None):
        if request and not isinstance(request, dict):
            request = json.loads(request)
        if response and not isinstance(response, dict):
            response = json.loads(response)
        if settings.MONGO_STORE:
            PgLogs.objects.create(log_type=log_type,
                                  pg_transaction_id=txn_id,
                                  order_id=order_id,
                                  response=response,
                                  request=request,
                                  created_at=timezone.localtime(),
                                  updated_at=timezone.localtime())