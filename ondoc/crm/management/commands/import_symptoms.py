from django.core.management.base import BaseCommand
from django.conf import settings
from ondoc.prescription.models import PrescriptionSymptomsComplaints
import logging
import pandas as pd
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'import symptoms to DB model PrescriptionSymptoms from JSON File'

    def handle(self, *args, **options):

        filename = 'symptoms.csv'
        csv_file = settings.ROOT_DIR.root + '/ondoc/prescription/templates/import_data/' + filename
        df = pd.read_csv(csv_file)

        filtered_df = df[~df.name.isin(
            PrescriptionSymptomsComplaints.objects.filter(name__in=df['name']).values_list('name', flat=True))]

        obj_list = list()
        for index, data in filtered_df.iterrows():
            obj_list.append(PrescriptionSymptomsComplaints(name=data.get('name'), moderated=True, source_type=data.get('source_type')))
        try:
            PrescriptionSymptomsComplaints.objects.bulk_create(obj_list)
        except Exception as e:
            logger.error(str(e))
            print("Error while bulk creating Prescription Symptoms; ERROR :: {}".format(str(e)))
