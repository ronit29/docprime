from __future__ import absolute_import, unicode_literals
import environ
import celery
import raven
import os
from django.conf import settings
from raven.contrib.celery import register_signal, register_logger_signal
from ondoc.account.tasks import refund_status_update, consumer_refund_update


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


app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    polling_time = 10
    # polling_time = float(settings.PG_REFUND_STATUS_POLL_TIME) * float(60.0)
    sender.add_periodic_task(polling_time, consumer_refund_update.s(), name='Refund and update consumer account balance')
    # sender.add_periodic_task(polling_time, refund_status_update.s(), name='Check for refund status')

