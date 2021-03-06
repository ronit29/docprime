from __future__ import absolute_import, unicode_literals

from celery import task
import logging
from django.conf import settings

# from ondoc.doctor.models import OpdAppointment
# from ondoc.common.models import SyncBookingAnalytics
from django.db.models import F

logger = logging.getLogger(__name__)


@task()
def sync_booking_data():
    from ondoc.common.models import MatrixMappedCity
    from ondoc.common.models import MatrixMappedState
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    from ondoc.common.models import SyncBookingAnalytics
    from ondoc.corporate_booking.models import CorporateDeal


    try:
        cities = MatrixMappedCity.objects.filter(synced_analytics__isnull=True)
        for city in cities:
            city.sync_with_booking_analytics()
            print('City-id : {} has been synced'.format(city.id))

        states = MatrixMappedState.objects.filter(synced_analytics__isnull=True)
        for state in states:
            state.sync_with_booking_analytics()
            print('State-id : {} has been synced'.format(state.id))

        opd_apps = OpdAppointment.objects.filter(synced_analytics__isnull=True)
        for app in opd_apps:
            app.sync_with_booking_analytics()
            print('OpdAppointment-id : {} has been synced'.format(app.id))

        lab_apps = LabAppointment.objects.filter(synced_analytics__isnull=True)
        for app in lab_apps:
            app.sync_with_booking_analytics()
            print('lab-id : {} has been synced'.format(app.id))

        corp_deals = CorporateDeal.objects.filter(synced_analytics__isnull=True)
        for deal in corp_deals:
            deal.sync_with_booking_analytics()
            print('deal-id : {} has been synced'.format(deal.id))

        to_be_updated = SyncBookingAnalytics.objects.exclude(synced_at=F('last_updated_at'))
        for obj in to_be_updated:
            row = obj.content_object
            row.sync_with_booking_analytics()
            print('obj-id : {} content-type : {} has been synced'.format(obj.id, obj.content_type))

    except Exception as e:
        logger.error(str(e))
