from __future__ import absolute_import, unicode_literals


from ondoc.account.models import Order

from rest_framework import status
from django.conf import settings
from celery import task
import requests
import json
import logging
import datetime
from ondoc.authentication.models import Address
from ondoc.api.v1.utils import resolve_address
from django.contrib.contenttypes.models import ContentType
logger = logging.getLogger(__name__)

@task(bind=True, max_retries=3)
def push_lab_appointment_to_integrator(self, data):
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping
    from ondoc.integrations import service
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            # logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise Exception("Appointment id not found, could not push to Matrix")

        appointment = LabAppointment.objects.filter(pk=appointment_id).first()
        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        lab = appointment.lab
        lab_tests = appointment.tests.all()
        lab_network = lab.network

        if not lab or not lab_tests or not lab_network:
            logger.error("[ERROR] Cant find lab, lab_network or lab_test")

        lab_network_content_type = ContentType.objects.get_for_model(lab_network)

        integrator_mapping = None

        tests = list()
        packages = list()
        for test in lab_tests:
            if test.is_package:
                packages.append(test)
            else:
                tests.append(test)

        if tests and packages[0]:
            integrator_mapping = IntegratorProfileMapping.objects.filter(content_type=lab_network_content_type, object_id=lab_network.id, test=packages[0])
        elif packages and tests[0]:
            integrator_mapping = IntegratorMapping.objects.filter(content_type=lab_network_content_type, object_id=lab_network.id, test=tests[0])
        else:
            logger.error('[ERROR]')

        integrator_obj = service.create_integrator_obj(integrator_mapping.integrator_class_name)
        integrator_response = integrator_obj.post_order(appointment, tests=tests, packages=packages)

        if not integrator_response:
            countdown_time = 1 * 60
            print(countdown_time)
            self.retry([data], countdown=countdown_time)


    except Exception as e:
        logger.error(str(e))
