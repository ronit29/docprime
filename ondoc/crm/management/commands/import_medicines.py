from django.core.management.base import BaseCommand
from django.conf import settings
from ondoc.prescription.models import PrescriptionMedicine
import logging
import pandas as pd
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'import medicines to DB model PrescriptionMedicines from CSV File'

    def handle(self, *args, **options):

        filename = 'Medicines.csv'
        csv_file = settings.ROOT_DIR.root + '/ondoc/prescription/templates/import_data/' + filename
        df = pd.read_csv(csv_file)

        filtered_df = df[~df.name.isin(
            PrescriptionMedicine.objects.filter(name__in=df['name']).values_list('name', flat=True))]

        obj_list = list()
        for index, data in df.iterrows():
            obj_list.append(PrescriptionMedicine(name=data.get('name'), moderated=True, source_type=data.get('source_type')))
        try:
            PrescriptionMedicine.objects.bulk_create(obj_list)
        except Exception as e:
            logger.error(str(e))
            print("Error while bulk creating Prescription Medicines; ERROR :: {}".format(str(e)))
