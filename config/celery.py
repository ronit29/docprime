from __future__ import absolute_import, unicode_literals
import environ
import celery
from celery.schedules import crontab
import raven
import os
from django.conf import settings
from raven.contrib.celery import register_signal, register_logger_signal
from ondoc.account.tasks import refund_status_update, consumer_refund_update, dump_to_elastic, integrator_order_summary,\
    get_thyrocare_reports, elastic_alias_switch
from celery.schedules import crontab
from ondoc.doctor.tasks import save_avg_rating, update_prices, update_city_search_key, update_doctors_count, \
    update_doctors_search_score, update_all_doctors_seo_urls
from ondoc.account.tasks import update_ben_status_from_pg,update_merchant_payout_pg_status
from ondoc.diagnostic.tasks import update_lab_seo_urls
# from ondoc.doctor.services.update_search_score import DoctorSearchScore
from ondoc.bookinganalytics.tasks import sync_booking_data

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

    broker_url = settings.CELERY_BROKER_URL
    task_default_queue = settings.CELERY_QUEUE
    default_queue = task_default_queue
    default_exchange = task_default_queue
    default_exchange_type = task_default_queue
    default_routing_key = task_default_queue

#app.config_from_object('django.conf:settings', namespace='CELERY')
app.config_from_object(Config)

app.autodiscover_tasks()


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    polling_time = float(settings.PG_REFUND_STATUS_POLL_TIME) * float(60.0)
    sender.add_periodic_task(polling_time, consumer_refund_update.s(), name='Refund and update consumer account balance')

    elastic_sync_cron_schedule = crontab(hour=19, minute=00)
    elastic_sync_post_cron_schedule = crontab(hour=20, minute=00)
    update_ben_status_cron_schedule = crontab(hour=21, minute=00)
    update_merchant_payout_pg_status_cron_schedule = crontab(hour=22, minute=30)

    sender.add_periodic_task(elastic_sync_cron_schedule, dump_to_elastic.s(), name='Sync Elastic')
    sender.add_periodic_task(elastic_sync_post_cron_schedule, elastic_alias_switch.s(), name='Sync Elastic alias')
    sender.add_periodic_task(crontab(hour=18, minute=30), save_avg_rating.s(), name='Update Lab and Doctor Average Rating')
    sender.add_periodic_task(crontab(hour=19, minute=30), update_prices.s(), name='Update Lab and Doctor Prices')
    sender.add_periodic_task(update_ben_status_cron_schedule, update_ben_status_from_pg.s(), name='Update Ben Status from pg ')
    sender.add_periodic_task(update_merchant_payout_pg_status_cron_schedule, update_merchant_payout_pg_status.s(), name='Update Merchant Payout Status from pg ')


    order_summary_time = float(settings.ORDER_SUMMARY_CRON_TIME) * float(60.0)
    sender.add_periodic_task(order_summary_time, integrator_order_summary.s(), name='Get Order Summary From Integrator')

    report_time = float(settings.THYROCARE_REPORT_CRON_TIME) * float(60.0)
    sender.add_periodic_task(report_time, get_thyrocare_reports.s(), name='Get Thyrocare Reports')
    sender.add_periodic_task(crontab(hour=19, minute=30), update_city_search_key.s(), name='Update Hospital City Search Key')
    sender.add_periodic_task(crontab(hour=20, minute=30), update_doctors_count.s(), name='Update Doctors Count')
<<<<<<< HEAD
    sender.add_periodic_task(crontab(hour=21, minute=30), update_doctors_search_score.s(), name='Update Doctors Search Score')
    sender.add_periodic_task(crontab(hour=1, minute=00), update_all_doctors_seo_urls.s(),
                             name='Update Doctors Seo Urls')
    sender.add_periodic_task(crontab(hour=2, minute=00), update_lab_seo_urls.s(),
                             name='Update Labs Seo Urls')
=======
    sender.add_periodic_task(crontab(hour=21, minute=00),  sync_booking_data.s(), name="Sync Booking Data for analytics")
>>>>>>> 7c25f1116d51f933efdc36b5a79e6209fd39eb64

    # doctor_search_score_creation_time = float(settings.CREATE_DOCTOR_SEARCH_SCORE) * float(3600.0)
    # sender.add_periodic_task(doctor_search_score_creation_time, create_search_score.s(), name='Doctor search score updaed')
