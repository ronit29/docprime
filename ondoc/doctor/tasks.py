from __future__ import absolute_import, unicode_literals

from rest_framework import status
import requests
from .models import OpdAppointment
from celery import task


@task(bind=True, max_retries=6)
def ops_alert(self, app_id, countdown_time):
    pass


@task(bind=True)
def doc_appointment_cancel(self, app_id, countdown_time):
    try:
        status = [OpdAppointment.CREATED, OpdAppointment.BOOKED, ]
        opd_obj = OpdAppointment.objects.filter(pk=app_id).first()
        if opd_obj:
            if opd_obj.status in status:
                opd_obj.status = OpdAppointment.CANCELED
                opd_obj.save()
    except Exception as e:
        print(e)
        self.retry([app_id, countdown_time, ], countdown_time=countdown_time)
