from __future__ import absolute_import, unicode_literals
from celery import task
import logging

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=3)
def push_lab_appointment_to_integrator(self, data):
    from django.contrib.contenttypes.models import ContentType
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.integrations.models import IntegratorMapping, IntegratorProfileMapping, IntegratorResponse
    from ondoc.integrations import service
    try:
        appointment_id = data.get('appointment_id', None)
        if not appointment_id:
            raise Exception("Appointment id not found, could not push to Matrix")

        appointment = LabAppointment.objects.filter(pk=appointment_id).first()

        if not appointment:
            raise Exception("Appointment could not found against id - " + str(appointment_id))

        if appointment.status == LabAppointment.BOOKED:
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

            if not tests and not packages:
                raise Exception('[ERROR] Could not find any test and packages for the appointment id %d' % appointment.id)

            if packages:
                integrator_mapping = IntegratorProfileMapping.objects.filter(content_type=lab_network_content_type, object_id=lab_network.id, package=packages[0]).first()
            elif tests:
                integrator_mapping = IntegratorMapping.objects.filter(content_type=lab_network_content_type, object_id=lab_network.id, test=tests[0]).first()

            integrator_obj = service.create_integrator_obj(integrator_mapping.integrator_class_name)
            integrator_response = integrator_obj.post_order(appointment, tests=tests, packages=packages)

            if not integrator_response:
                countdown_time = 1 * 60
                print(countdown_time)
                self.retry([data], countdown=countdown_time)

            # save integrator response
            resp_data = integrator_response
            IntegratorResponse.objects.create(lead_id=resp_data['ORDERRESPONSE']['PostOrderDataResponse'][0]['LEAD_ID'],
                                              dp_order_id=resp_data['ORDER_NO'], integrator_order_id=resp_data['REF_ORDERID'],
                                              content_object=appointment, response_data=resp_data,
                                              integrator_class_name=integrator_mapping.integrator_class_name)

        elif appointment.status == LabAppointment.CANCELLED:
            saved_response = IntegratorResponse.objects.filter(object_id=appointment.id).first()
            if not saved_response:
                logger.error("[ERROR] Cant find integrator response for appointment id " + str(appointment.id))

            integrator_obj = service.create_integrator_obj(saved_response.integrator_class_name)
            response = integrator_obj.cancel_integrator_order(appointment, saved_response)

            if not response:
                countdown_time = 1 * 60
                print(countdown_time)
                self.retry([data], countdown=countdown_time)

    except Exception as e:
        logger.error(str(e))



@task()
def integrator_order_summary():
    from ondoc.integrations.models import IntegratorResponse
    IntegratorResponse.get_order_summary()
