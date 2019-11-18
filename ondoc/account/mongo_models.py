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
    PAYOUT_PROCESS = 6
    PAYOUT_SETTLEMENT_DETAIL = 7
    CHAT_ORDER_REQUEST = 8
    CHAT_CONSULTATION_CANCEL = 9
    ECONSULT_ORDER_REQUEST = 10
    REFUND_REQUEST_RESPONSE = 11
    RESPONSE_TO_CHAT = 12
    ACK_TO_PG = 13

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order_id = LongField(null=True, blank=True, editable=False)
    pg_transaction_id = LongField(null=True, blank=True, editable=False)
    user_id = LongField(null=True, blank=True, editable=False)
    logs = ListField()

    @classmethod
    def save_pg_response(cls, log_type=0, order_id=None, txn_id=None, response=None, request=None, user_id=None):
        if settings.MONGO_STORE:
            pg_log = None
            if order_id:
                pg_log = PgLogs.objects.filter(order_id=order_id).first()
            if not pg_log:
                pg_log = PgLogs(order_id=order_id,
                                pg_transaction_id=txn_id,
                                user_id=user_id,
                                created_at=timezone.localtime(),
                                updated_at=timezone.localtime())
            if request:
                if not isinstance(request, dict):
                    request = json.loads(request)
                request['log_type'] = log_type
                request['type'] = "REQUEST"
                request['created_at'] = timezone.localtime()
                pg_log.logs.append(request)
            if response:
                if not isinstance(response, dict):
                    response = json.loads(response)
                response['log_type'] = log_type
                response['type'] = "RESPONSE"
                response['created_at'] = timezone.localtime()
                pg_log.logs.append(response)

            pg_log.save()
