from django.core.management.base import BaseCommand
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
from ondoc.tracking.models import MigrateTracker
from datetime import datetime, timedelta

class Command(BaseCommand):

    help = 'Migrate Old tracking events from psql into mongo'

    def handle(self, *args, **options):

        class EventMigrateIterator():

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

                events = track_models.TrackingEvent.objects.filter(created_at__lte=self.time_upper_limit,
                                                                   created_at__gte=self.time_lower_limit)

                if self.iter_count >= self.iter_count_limit:
                    raise StopIteration
                self.iter_count += 1

                # update limits in iter
                self.time_upper_limit = self.time_lower_limit
                self.time_lower_limit = self.time_upper_limit - timedelta(hours=self.delta_hours)

                return events

        total_migrated = 0
        # storing events
        counter = 0
        try:
            for psql_events in EventMigrateIterator(.1, 250*4):
                print('read from postgres done '+ str(datetime.now()))
                counter += 1
                create_objects = []
                mongo_events = []
                if counter<=3:
                    mongo_events = track_mongo_models.TrackingEvent.objects.filter(id__in=[x.id for x in psql_events]).values_list('id')
                    psql_events = psql_events.exclude(id__in=mongo_events)
                print('filter from mongo done '+ str(datetime.now()))

                for event in psql_events:
                    eventJson = {"id": event.id, "name": event.name, "visit_id": event.visit_id, "user": event.user_id,
                                 "created_at": event.created_at, "updated_at": event.updated_at, "triggered_at": event.triggered_at}

                    if event.data:
                        eventJson = { **eventJson , **event.data }

                    mongo_event = track_mongo_models.TrackingEvent(**eventJson)
                    create_objects.append(mongo_event)
                    total_migrated += 1
                print('array creation done '+ str(datetime.now()))

                if create_objects:
                    track_mongo_models.TrackingEvent.objects.insert(create_objects)
                print('objects created in mongo '+ str(datetime.now()))
                print("MIGRATED COUNT : " + str(total_migrated))

        except StopIteration:
            pass
        except Exception as e:
            print("FAILED TO MIGRATE ALL EVENTS")
            print(e)
            return

        print("DONE MIGRATING EVENTS")







