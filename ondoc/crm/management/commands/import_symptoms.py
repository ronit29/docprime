from django.core.management.base import BaseCommand
from django.conf import settings
from ondoc.prescription.models import PrescriptionSymptoms
import logging
import pandas as pd
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'import symptoms to DB model PrescriptionSymptoms from JSON File'

    def handle(self, *args, **options):

        filename = 'Updated Symptoms.csv'
        csv_file = settings.ROOT_DIR.root + '/ondoc/prescription/templates/import_data/' + filename
        df = pd.read_csv(csv_file)

        filtered_df = df[~df.name.isin(
            PrescriptionSymptoms.objects.filter(name__in=df['name']).values_list('name', flat=True))]

        obj_list = list()
        for name in filtered_df['name']:
            obj_list.append(PrescriptionSymptoms(name=name, moderated=True))
        try:
            PrescriptionSymptoms.objects.bulk_create(obj_list)
        except Exception as e:
            logger.error(str(e))
            print("Error while bulk creating Prescription Symptoms; ERROR :: {}".format(str(e)))
