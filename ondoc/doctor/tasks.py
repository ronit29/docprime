
from __future__ import absolute_import, unicode_literals

from django.db import transaction
from celery import task
import logging

from ondoc.api.v1.utils import RawSql

logger = logging.getLogger(__name__)


@task(bind=True)
@transaction.atomic
def doc_app_auto_cancel(self, prev_app_dict):
    from .models import OpdAppointment
    try:
        opd_status = [OpdAppointment.CANCELLED, OpdAppointment.COMPLETED, OpdAppointment.ACCEPTED, ]
        present_app_obj = OpdAppointment.objects.filter(pk=prev_app_dict.get("id")).first()
        if present_app_obj:
            if present_app_obj.status not in opd_status and prev_app_dict.get(
                    "status") == present_app_obj.status and int(prev_app_dict.get("updated_at")) == int(present_app_obj.updated_at.timestamp()):
                present_app_obj.cancellation_type = OpdAppointment.AUTO_CANCELLED
                present_app_obj.action_cancelled(refund_flag=1)
            else:
                logger.error("Error in Celery - Condition not satisfied for - " + str(prev_app_dict.get("id")) + " with prev status - " + str(prev_app_dict.get("status")) + " and present status - "+ str(present_app_obj.status) + " and prev updated time - "+ str(prev_app_dict.get("updated_at")) + " and present updated time - " + str(present_app_obj.updated_at))
        else:
            logger.error("Error in Celery - No opd appointment for - " + str(prev_app_dict.get("id")))
    except Exception as e:
        logger.error("Error in Celery auto cancel flow - " + str(e))

@task(bind=True)
def create_doctor_score():
    RawSql('''select d.search_score, ss.final_score as doctor_score from search_score ss inner join doctor d on 
                  ss.doctor_id = d.id''', []).execute()

    return "success"

@task(bind=True)
def delete_search_score():
    RawSql('''delete from search_score''', []).execute()
    return "success"