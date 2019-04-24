from django.core.management.base import BaseCommand
from ondoc.tracking import models as track_models
from ondoc.tracking import mongo_models as track_mongo_models
from ondoc.tracking.models import MigrateTracker
from datetime import datetime, timedelta
from django.forms import model_to_dict

class Command(BaseCommand):

    help = 'Migrate Old tracking data from psql into mongo'

    def handle(self, *args, **options):

        class VisitorMigrateIterator():

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

                visitors = track_models.TrackingVisitor.objects.filter(created_at__lte=self.time_upper_limit,
                                                                       created_at__gte=self.time_lower_limit)

                if self.iter_count >= self.iter_count_limit:
                    raise StopIteration
                self.iter_count += 1

                # update limits in iter
                self.time_upper_limit = self.time_lower_limit
                self.time_lower_limit = self.time_upper_limit - timedelta(hours=self.delta_hours)

                return visitors

        total_migrated = 0
        # storing events
        try:
            for visitors in VisitorMigrateIterator(240, 30):
                create_objects = []
                mongo_visitors = track_mongo_models.TrackingVisitor.objects.filter(id__in=[ x.id for x in visitors ]).values_list('id')
                psql_visitors = visitors.exclude(id__in=mongo_visitors)

                for visitor in psql_visitors:
                    visitorJson = {"id": visitor.id, "created_at": visitor.created_at,
                                   "updated_at": visitor.updated_at}
                    if visitor.device_info:
                        visitorJson["device_info"] = visitor.device_info
                    if visitor.client_category:
                        visitorJson["client_category"] = visitor.client_category
                    mongo_visitor = track_mongo_models.TrackingVisitor(**visitorJson)
                    create_objects.append(mongo_visitor)
                    total_migrated += 1

                if create_objects:
                    track_mongo_models.TrackingVisitor.objects.insert(create_objects)
                print("MIGRATED COUNT : " + str(total_migrated))
        except StopIteration:
            pass
        except Exception as e:
            print("FAILED TO MIGRATE VISITORS "+str(e))
            return

        print("DONE MIGRATING VISITORS")





