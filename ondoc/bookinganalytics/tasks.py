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

    try:
        cities = MatrixMappedCity.objects.filter(synced_analytics__isnull=True)
        for city in cities:
            city.sync_with_booking_analytics()

        states = MatrixMappedState.objects.filter(synced_analytics__isnull=True)
        for state in states:
            state.sync_with_booking_analytics()

        opd_apps = OpdAppointment.objects.filter(synced_analytics__isnull=True)
        for app in opd_apps:
            app.sync_with_booking_analytics()

        lab_apps = LabAppointment.objects.filter(synced_analytics__isnull=True)
        for app in lab_apps:
            app.sync_with_booking_analytics()

        to_be_updated = SyncBookingAnalytics.objects.exclude(synced_at=F('last_updated_at'))
        for obj in to_be_updated:
            row = obj.content_object
            row.sync_with_booking_analytics(obj)

    except Exception as e:
        logger.error(str(e))
