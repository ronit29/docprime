from __future__ import absolute_import, unicode_literals

from celery import task
from datetime import timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


@task(bind=True)
def doc_app_auto_cancel(self, prev_app_dict):
    from .models import OpdAppointment
    try:
        opd_status = [OpdAppointment.CANCELLED, OpdAppointment.COMPLETED, OpdAppointment.ACCEPTED, ]
        present_app_obj = OpdAppointment.objects.filter(pk=prev_app_dict.get("id")).first()
        if present_app_obj:
            if present_app_obj.status not in opd_status and prev_app_dict.get(
                    "status") == present_app_obj.status and timezone.now() - present_app_obj.updated_at >= timedelta(
                    minutes=10):
                present_app_obj.action_cancelled(refund_flag=1)
    except Exception as e:
        logger.error("Error in Celery auto cancel flow - " + str(e))
