import copy
from decimal import Decimal

from django.core.management.base import BaseCommand
from ondoc.account.models import Order
from ondoc.diagnostic.models import LabAppointmentTestMapping


class Command(BaseCommand):
    help = 'Map test details from order in lab appointments'

    def handle(self, *args, **options):
        order_queryset = Order.objects.filter(product_id=Order.LAB_PRODUCT_ID, reference_id__isnull=False)
        appointment_test_mappings = []
        for order in order_queryset:
            temp_action_data = order.action_data
            if temp_action_data:
                temp_action_data = dict(copy.deepcopy(temp_action_data))
                temp_extra_details = temp_action_data.get('extra_details', [])
                for test_details in temp_extra_details:
                    test_details.pop('name', None)
                    test_details['appointment_id'] = order.reference_id
                    test_details['test_id'] = test_details.pop('id')
                    test_details['mrp'] = Decimal(test_details['mrp']) if test_details['mrp'] != 'None' else None
                    test_details['custom_deal_price'] = Decimal(test_details['custom_deal_price']) if test_details[
                                                                                          'custom_deal_price'] != 'None' else None
                    test_details['computed_deal_price'] = Decimal(test_details['computed_deal_price']) if test_details[
                                                                                              'computed_deal_price'] != 'None' else None
                    test_details['custom_agreed_price'] = Decimal(test_details['custom_agreed_price']) if test_details[
                                                                                              'custom_agreed_price'] != 'None' else None
                    test_details['computed_agreed_price'] = Decimal(test_details['computed_agreed_price']) if test_details[
                                                                                                  'computed_agreed_price'] != 'None' else None
                    appointment_test_mappings.append(LabAppointmentTestMapping(**test_details))
        LabAppointmentTestMapping.objects.bulk_create(appointment_test_mappings)

