from __future__ import absolute_import, unicode_literals

from rest_framework import status
import requests
from celery import task

import datetime
import logging

logger = logging.getLogger(__name__)


@task(bind=True)
def lab_app_auto_cancel(self, prev_app_dict):
    from ondoc.diagnostic.models import LabAppointment
    try:
        updated_status_instance = LabAppointment.objects.filter(pk=prev_app_dict['id']).first()
        new_status = updated_status_instance.status
        if new_status not in [LabAppointment.ACCEPTED, LabAppointment.CANCELED, LabAppointment.COMPLETED]:
            if prev_app_dict['status'] == new_status and datetime.datetime.now() - updated_status_instance.updated_at >= datetime.timedelta(minutes=10):
                updated_status_instance.action_cancelled(refund_flag=1)

    except Exception as e:
        logger.error("Error in Celery auto cancel flow - " + str(e))
        self.retry((prev_app_dict, ))
