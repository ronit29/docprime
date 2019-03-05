from django.core.management.base import BaseCommand
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
from ondoc.tracking.models import MigrateTracker
from datetime import datetime, timedelta

class Command(BaseCommand):

    help = 'Migrate Old tracking data from psql into mongo'

    def handle(self, *args, **options):
        visits_count = track_models.TrackingVisit.objects.count()
        visitors_count = track_models.TrackingVisitor.objects.count()
        visits = track_models.TrackingVisit.objects.all()[0:visits_count]
        visitors = track_models.TrackingVisitor.objects.all()[0:visitors_count]

        last_migrate_ts = MigrateTracker.objects.first()
        if not last_migrate_ts:
            print("Specify from where to start Migration")
            return
        migration_start_time = last_migrate_ts.start_time
        migration_end_time =  migration_start_time - timedelta(hours = 1)

        events = track_models.TrackingEvent.objects.filter(created_at__lte=migration_start_time,
                                                           created_at__gte=migration_end_time).order_by('-created_at')

        # storing visitors
        for visitor in visitors.iterator(chunk_size=2000):
            mongo_visitor = track_mongo_models.TrackingVisitor.objects.filter(id=visitor.id).first()
            if not mongo_visitor:
                visitorJson = {"id": visitor.id, "created_at": visitor.created_at, "updated_at": visitor.updated_at}
                if visitor.device_info:
                    visitorJson["device_info"] = visitor.device_info
                mongo_visitor = track_mongo_models.TrackingVisitor(**visitorJson)
                mongo_visitor.save()

        print("DONE MIGRATING VISITORS")

        # storing visits
        for visit in visits.iterator(chunk_size=2000):
            mongo_visit = track_mongo_models.TrackingVisit.objects.filter(id=visit.id).first()
            if not mongo_visit:
                visitJson = {"id": visit.id, "visitor_id": visit.visitor_id, "ip_address": visit.ip_address,
                             "location": visit.location, "user_agent": visit.user_agent, "created_at": visit.created_at,
                             "updated_at": visit.updated_at}
                if visit.data:
                    visitJson["data"] = visit.data
                mongo_visit = track_mongo_models.TrackingVisit(**visitJson)
                mongo_visit.save()

        print("DONE MIGRATING VISITS")

        # storing events
        stored_all_events = True
        for event in events.iterator(chunk_size=1000):
            try:
                mongo_event = track_mongo_models.TrackingEvent.objects.filter(id=event.id).first()
                if not mongo_event:
                    eventJson = {"id": event.id, "name": event.name, "visit_id": event.visit_id, "user": event.user_id,
                                 "created_at": event.created_at, "updated_at": event.updated_at}

                    if event.data:
                        eventJson = { **eventJson , **event.data }

                    mongo_event = track_mongo_models.TrackingEvent(**eventJson)
                    mongo_event.save()
            except:
                last_migrate_ts.start_time = event.created_at
                stored_all_events = False
                break

        if stored_all_events and events:
            last_migrate_ts.start_time = events.last().created_at
        last_migrate_ts.save()

        print("DONE MIGRATING EVENTS - upto - " + str(last_migrate_ts.start_time))


