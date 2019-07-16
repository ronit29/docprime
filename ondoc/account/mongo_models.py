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
    pg_transaction_id = LongField(null=True, blank=True, editable=False)
    response = DictField(blank=True, null=True)

    @classmethod
    def save_pg_response(cls, txn_id, response):
        if not isinstance(response, dict):
            response = json.loads(response)
        if settings.MONGO_STORE:
            PgLogs.objects.create(pg_transaction_id=txn_id,
                                  response=response,
                                  created_at=timezone.localtime(),
                                  updated_at=timezone.localtime())