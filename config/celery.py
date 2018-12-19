from __future__ import absolute_import, unicode_literals
import environ
import celery
import raven
import os
from django.conf import settings
from raven.contrib.celery import register_signal, register_logger_signal
from ondoc.account.tasks import refund_status_update, consumer_refund_update
from urllib.parse import quote

env = environ.Env()

# os.environ.setdefault('DJANGO_SETTINGS_MODULE', env('DJANGO_SETTINGS_MODULE'))
print('environment=='+env('DJANGO_SETTINGS_MODULE'))

if os.environ.get('DJANGO_SETTINGS_MODULE') == 'config.settings.local':

    app = celery.Celery(__name__)



else:
    class Celery(celery.Celery):

        def on_configure(self):
            client = raven.Client(settings.SENTRY_DSN)

            # register a custom filter to filter out duplicate logs
            register_logger_signal(client)

            # hook into the Celery error handler
            register_signal(client)

    app = Celery(__name__)

class Config():


    broker_backend = "SQS"
    broker_transport_options = {'region': 'ap-south-1'}

    broker_url = "sqs://{}:{}@".format(settings.AWS_ACCESS_KEY_ID, quote(settings.AWS_SECRET_ACCESS_KEY, safe=''))

    task_create_missing_queues = False
    task_default_queue = settings.CELERY_TASK_DEFAULT_QUEUE
    default_queue = settings.CELERY_TASK_DEFAULT_QUEUE
    default_exchange = default_queue
    default_exchange_type = default_queue
    default_routing_key = default_queue
    sqs_queue_name = task_default_queue
    queues = {default_queue: {'exchange': default_queue, 'binding_key': default_queue}}
    enable_remote_control = False
    send_events = False
    aws_access_key_id = settings.AWS_ACCESS_KEY_ID
    aws_secret_access_key = settings.AWS_SECRET_ACCESS_KEY


#app.config_from_object('django.conf:settings', namespace='CELERY')
app.config_from_object(Config)
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    polling_time = float(settings.PG_REFUND_STATUS_POLL_TIME) * float(60.0)
    sender.add_periodic_task(polling_time, consumer_refund_update.s(), name='Refund and update consumer account balance')
