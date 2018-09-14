from django.core.management.base import BaseCommand
from ondoc.diagnostic.models import Lab
from ondoc.location.models import EntityLocationRelationship, EntityUrls


def map_lab_location_urls():
    all_labs = Lab.objects.all()
    for lab in all_labs:
        if lab.data_status == 3:
            success = EntityLocationRelationship.create(latitude=lab.location.y, longitude=lab.location.x, content_object=lab)
            if success:
                response = EntityUrls.create(lab)
                if response:
                    print("Url creation of lab {name} success".format(name=lab.name))
                else:
                    print("Url creation of lab {name} failed".format(name=lab.name))
            else:
                print("Location parsing of lab {name} failed".format(name=lab.name))
                break



class Command(BaseCommand):
    def handle(self, **options):
        map_lab_location_urls()
