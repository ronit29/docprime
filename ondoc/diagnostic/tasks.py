from __future__ import absolute_import, unicode_literals

from celery import task

import datetime
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@task(bind=True)
def lab_app_auto_cancel(self, prev_app_dict):
    from ondoc.diagnostic.models import LabAppointment
    try:
        updated_status_instance = LabAppointment.objects.filter(pk=prev_app_dict['id']).first()
        new_status = updated_status_instance.status
        if new_status not in [LabAppointment.ACCEPTED, LabAppointment.CANCELLED, LabAppointment.COMPLETED]:
            if prev_app_dict['status'] == new_status and int(prev_app_dict.get("updated_at")) == int(updated_status_instance.updated_at.timestamp()):
                updated_status_instance.cancellation_type = LabAppointment.AUTO_CANCELLED
                updated_status_instance.action_cancelled(refund_flag=1)

    except Exception as e:
        logger.error("Error in Celery auto cancel flow - " + str(e))
