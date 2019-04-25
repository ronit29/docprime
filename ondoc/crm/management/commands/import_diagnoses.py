from django.core.management.base import BaseCommand
from django.conf import settings
from ondoc.prescription.models import PrescriptionDiagnoses
import logging
import pandas as pd
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'import diagnoses to DB model PrescriptionDiagnoses from CSV File'

    def handle(self, *args, **options):

        filename = 'diagnosis.csv'
        csv_file = settings.ROOT_DIR.root + '/ondoc/prescription/templates/import_data/' + filename
        df = pd.read_csv(csv_file)

        filtered_df = df[~df.name.isin(
            PrescriptionDiagnoses.objects.filter(name__in=df['name']).values_list('name', flat=True))]

        obj_list = list()
        for index, data in filtered_df.iterrows():
            obj_list.append(PrescriptionDiagnoses(name=data.get('name'), source_type=data.get('source_type'), moderated=True))
        try:
            PrescriptionDiagnoses.objects.bulk_create(obj_list)
        except Exception as e:
            logger.error(str(e))
            print("Error while bulk creating Prescription Diagnoses; ERROR :: {}".format(str(e)))
