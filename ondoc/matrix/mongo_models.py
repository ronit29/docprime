from mongoengine import *
import uuid, datetime, json
from django.conf import settings
from django.utils import timezone

import json

from ondoc.account.mongo_models import TimeStampedModel


class MatrixLog(DynamicDocument, TimeStampedModel):

    id = UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type_id = LongField(null=True, blank=False, editable=False)
    object_id = LongField(null=True, blank=False, editable=False)
    product_type = LongField(null=True, blank=False, editable=False)
    request_payload = StringField()
    request_response = StringField()
    originating_source = StringField(null=True)

    @classmethod
    def create_matrix_logs(cls, obj, request_payload, request_response):
        from django.contrib.contenttypes.models import ContentType
        if not request_response or not request_payload:
            return

        originating_source = None
        object_id = None
        content_type_id = None
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            if content_type:
                content_type_id = content_type.id

            object_id = obj.id

        product_type = None
        if obj:
            if obj.__class__.__name__ == 'OpdAppointment':
                product_type = 1
            elif obj.__class__.__name__ == 'LabAppointment':
                product_type = 2
            elif obj.__class__.__name__ == 'PlusUser':
                product_type = 11
            elif obj.__class__.__name__ == 'UserInsurance':
                product_type = 3

        matrix_log_obj = cls(object_id=object_id, content_type_id=content_type_id, product_type=product_type,
                             request_payload=str(request_payload), request_response=str(request_response),
                             originating_source=originating_source)

        matrix_log_obj.save()

    class Meta:
        db_table = 'matrix_log'
