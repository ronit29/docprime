from django.core.management.base import BaseCommand
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
from ondoc.tracking.models import MigrateTracker
from datetime import datetime, timedelta

class Command(BaseCommand):

    help = 'Migrate Old tracking visits from psql into mongo'

    def handle(self, *args, **options):

        class VisitMigrateIterator():

            def __init__(self, delta_hours, iter_count_limit):
                self.delta_hours = delta_hours
                self.iter_count = 0
                self.iter_count_limit = iter_count_limit

                last_migrate_ts = MigrateTracker.objects.first()
                if not last_migrate_ts:
                    raise Exception("Specify from where to start Migration")

                self.last_migrate_ts = last_migrate_ts
                self.time_upper_limit = last_migrate_ts.start_time
                self.time_lower_limit = self.time_upper_limit - timedelta(hours=self.delta_hours)


            def __iter__(self):
                return self

            def __next__(self):
                # update limit in db at each iteration
                self.last_migrate_ts.start_time = self.time_upper_limit
                self.last_migrate_ts.save()

                visits = track_models.TrackingVisit.objects.filter(created_at__lte=self.time_upper_limit,
                                                                   created_at__gte=self.time_lower_limit)

                if self.iter_count >= self.iter_count_limit:
                    raise StopIteration
                self.iter_count += 1

                # update limits in iter
                self.time_upper_limit = self.time_lower_limit
                self.time_lower_limit = self.time_upper_limit - timedelta(hours=self.delta_hours)

                return visits

        total_migrated = 0
        # storing events
        try:
            for visits in VisitMigrateIterator(240, 30):
                create_objects = []
                mongo_visits = track_mongo_models.TrackingVisit.objects.filter(id__in=[x.id for x in visits]).values_list('id')
                psql_visits = visits.exclude(id__in=mongo_visits)

                for visit in psql_visits:
                    visitJson = {"id": visit.id, "visitor_id": visit.visitor_id, "ip_address": visit.ip_address,
                                 "location": visit.location, "user_agent": visit.user_agent,
                                 "created_at": visit.created_at,
                                 "updated_at": visit.updated_at}
                    if visit.data:
                        visitJson["data"] = visit.data
                    mongo_visit = track_mongo_models.TrackingVisit(**visitJson)
                    create_objects.append(mongo_visit)
                    total_migrated += 1

                if create_objects:
                    track_mongo_models.TrackingVisit.objects.insert(create_objects)
                print("MIGRATED COUNT : " + str(total_migrated))

        except StopIteration:
            pass
        except Exception as e:
            print("FAILED TO MIGRATE ALL VISITS")
            return

        print("DONE MIGRATING VISITS")