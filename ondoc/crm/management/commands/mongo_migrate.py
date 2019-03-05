from django.core.management.base import BaseCommand
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models

class Command(BaseCommand):

    help = 'Migrate Old tracking data from psql into mongo'

    def handle(self, *args, **options):
        events_count = track_models.TrackingEvent.objects.count()
        visits_count = track_models.TrackingVisit.objects.count()
        visitors_count = track_models.TrackingVisitor.objects.count()
        events = track_models.TrackingEvent.objects.all()[0:events_count]
        visits = track_models.TrackingVisit.objects.all()[0:visits_count]
        visitors = track_models.TrackingVisitor.objects.all()[0:visitors_count]

        # # storing visitors
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
        for event in events.iterator(chunk_size=1000):
            mongo_event = track_mongo_models.TrackingEvent.objects.filter(id=event.id).first()
            if not mongo_event:
                eventJson = {"id": event.id, "name": event.name, "visit_id": event.visit_id, "user": event.user_id,
                             "created_at": visit.created_at, "updated_at": visit.updated_at}

                if event.data:
                    eventJson["data"] = event.data

                if event.triggered_at:
                    eventJson["triggered_at"] = event.triggered_at

                mongo_event = track_mongo_models.TrackingEvent(**eventJson)
                mongo_event.save()

        print("DONE MIGRATING EVENTS")


