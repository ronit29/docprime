from django.core.management.base import BaseCommand
from ondoc.diagnostic import models as diagnostic_model
from django.db import connection
from django.utils import timezone


class Command(BaseCommand):
    help = 'create available lab test'

    def add_arguments(self, parser):
        parser.add_argument('lab_id', type=int)

    def create_lab_test_mapping(self, labs, old_lab_id):
        current_time = timezone.now()
        for lab in labs:
            query_string = "insert into available_lab_test(mrp,computed_agreed_price, computed_deal_price,lab_id, " \
                           "test_id, custom_agreed_price, custom_deal_price, enabled, created_at,updated_at) " \
                           "select mrp,computed_agreed_price, computed_deal_price,%s,test_id,custom_agreed_price, " \
                           "custom_deal_price,enabled, '%s', '%s'  " \
                           "from available_lab_test where lab_id = %s" % (lab.id, current_time, current_time,
                                                                          old_lab_id)
            with connection.cursor() as cursor:
                cursor.execute(query_string)

    def handle(self, *args, **options):
        lab_id = options['lab_id']
        old_lab = diagnostic_model.Lab.objects.select_related("network").filter(id=lab_id).first()
        if not old_lab:
            return
        labs = diagnostic_model.Lab.objects.filter(network=old_lab.network, availabletests__isnull=True).exclude(
            id=lab_id)
        self.create_lab_test_mapping(labs, old_lab.id)
