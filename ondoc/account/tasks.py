from __future__ import absolute_import, unicode_literals

from boto3.resources import params
from django.db import transaction
from rest_framework import status
from django.conf import settings
import hashlib
from decimal import Decimal
import psycopg2
from django.db import connection, transaction
from rest_framework import status
import uuid
from celery import task
import requests
import json
import logging
from collections import OrderedDict
import datetime
from django.db.models import Q

logger = logging.getLogger(__name__)

@task()
def dump_to_elastic():
    from ondoc.elastic import models as elastic_models

    try:
        obj = elastic_models.DemoElastic.objects.all().order_by('id').last()
        if not obj:
            raise Exception('Could not elastic object.')

        headers = {
            'Content-Type': 'application/json',
        }

        elastic_url = obj.elastic_url
        elastic_alias = obj.elastic_alias
        primary_index = obj.primary_index
        secondary_index_a = obj.secondary_index_a
        secondary_index_b = obj.secondary_index_b
        primary_index_mapping_data = obj.primary_index_mapping_data
        secondary_index_mapping_data = obj.secondary_index_mapping_data

        if not obj.active or not elastic_url or not elastic_alias or not primary_index or not secondary_index_a or not secondary_index_b \
                or not primary_index_mapping_data or not secondary_index_mapping_data:
            raise Exception("Necessary vales of the elastic configuration is not set.")

        params = (
            ('format', 'json'),
        )

        # Fetch currently used index.
        response = requests.get(elastic_url + '/_cat/aliases/' + elastic_alias, params=params)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            raise Exception('Could not get current index.')

        response = response.json()
        if not response:
            raise Exception('Invalid Response received while fetching current index.')

        currently_used_index = response[0].get('index')
        if not currently_used_index:
            raise Exception('Invalid json received while fetching the index.')

        # Decide which index to use for dumping the data to elastic.
        if secondary_index_a == currently_used_index:
            original = secondary_index_a
            destination = secondary_index_b
        else:
            original = secondary_index_b
            destination = secondary_index_a

        # Delete the primary index.
        response = requests.delete(elastic_url + '/' + primary_index, headers=headers)
        if response.status_code != status.HTTP_200_OK or not response.ok:

            if response.status_code == status.HTTP_404_NOT_FOUND and response.json().get('error', {}).get('type', "") == "index_not_found_exception".lower():
                pass
            else:
                raise Exception('Could not delete the primary index.')

        # create the primary index for dumping the data.
        createIndex = requests.put(elastic_url + '/' + primary_index, headers=headers, data=json.dumps(primary_index_mapping_data))
        if createIndex.status_code != status.HTTP_200_OK or not createIndex.ok:
            raise Exception('Could not create the primary index.')

        query = obj.query.strip()
        if not query:
            raise ValueError('Query is empty or invalid.')

        def default(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

        batch_size = 5000
        with transaction.atomic():
            with connection.connection.cursor(name='elasticdata', cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.itersize = batch_size
                cursor.execute(query)
                response_list = list()
                attempted = 0
                hashlib_obj = hashlib.sha1()
                for row in cursor:
                    attempted = attempted + 1
                    json_format_row = json.dumps(row) + row.get('name', uuid.uuid4())
                    hashlib_obj.update(json_format_row.encode('utf-8'))

                    document_dict = {
                        "_index": primary_index,
                        "_type": "entity",
                        "_id": hashlib_obj.hexdigest()
                    }

                    response_list.append({'index': document_dict})
                    response_list.append(row)
                    if len(response_list) >= batch_size:
                        response_list = json.loads(json.dumps(response_list, default=default))
                        data = '\n'.join(json.dumps(d) for d in response_list) + '\n'
                        dump_headers = {"Content-Type": "application/x-ndjson"}
                        dump_response = requests.post(elastic_url + '/_bulk', headers=dump_headers, data=data)
                        if dump_response.status_code != status.HTTP_200_OK or not dump_response.ok:
                            raise Exception('Dump unsuccessfull')

                        response_list = list()

                # write all remaining records
                if len(response_list) > 0:
                    response_list = json.loads(json.dumps(response_list, default=default))
                    data = '\n'.join(json.dumps(d) for d in response_list) + '\n'
                    dump_headers = {"Content-Type": "application/x-ndjson"}
                    dump_response = requests.post(elastic_url + '/_bulk', headers=dump_headers, data=data)
                    if dump_response.status_code != status.HTTP_200_OK or not dump_response.ok:
                        raise Exception('Dump unsuccessfull')

        call_data = {
            'primary_index': primary_index,
            'secondary_index_mapping_data' : secondary_index_mapping_data,
            'elastic_alias': elastic_alias,
            'url': elastic_url,
            'original': original,
            'destination': destination,
            'timestamp': int(datetime.datetime.now().timestamp()),
            'id': obj.id
        }

        logger.error(json.dumps(call_data))

        obj.post_task_data = call_data
        obj.save()

        # elastic_alias_switch.apply_async((call_data,), countdown=3600)

        logger.error("Sync elastic job 1 completed")
        return

    except Exception as e:
        logger.error("Error in syncing process of elastic - " + str(e))

@task()
def elastic_alias_switch():
    from ondoc.elastic import models as elastic_models

    obj = elastic_models.DemoElastic.objects.all().order_by('id').last()
    if not obj:
        raise Exception('Could not elastic object.')

    data = obj.post_task_data
    if data.get('timestamp', 0) + (2 * 3600) < int(datetime.datetime.now().timestamp()):
        raise Exception('Object found is not desired object or last object.')

    headers = {
        'Content-Type': 'application/json',
    }

    elastic_url = data.get('url')
    destination = data.get('destination')
    original = data.get('original')
    elastic_alias = data.get('elastic_alias')
    secondary_index_mapping_data = data.get('secondary_index_mapping_data')
    primary_index = data.get('primary_index')
    if not elastic_url or not destination or not original or not elastic_alias or not secondary_index_mapping_data or not primary_index:
        raise Exception('Invalid data found. Cannot sync to elastic.')

    # Delete the index or empty the index for new use.
    deleteResponse = requests.delete(elastic_url + '/' + destination)
    if deleteResponse.status_code != status.HTTP_200_OK or not deleteResponse.ok:
        if deleteResponse.status_code == status.HTTP_404_NOT_FOUND and deleteResponse.json().get('error', {}).get('type', "") == "index_not_found_exception".lower():
            pass
        else:
            raise Exception('Could not delete the destination index.')

    # create the destination index for dumping the data.
    createDestinationIndex = requests.put(elastic_url + '/' + destination, headers=headers, data=json.dumps(secondary_index_mapping_data))
    if createDestinationIndex.status_code != status.HTTP_200_OK or not createDestinationIndex.ok:
        raise Exception('Could not create the destination index. ', destination)

    data = {"source": {"index": primary_index}, "dest": {"index": destination}}
    response = requests.post(elastic_url + '/_reindex', headers={'Content-Type': 'application/json'}, data=json.dumps(data))
    if response.status_code != status.HTTP_200_OK or not response.ok:
        raise Exception('Could not switch the ')

    alias_data = {
        "actions": [
            {
                "remove": {
                    "indices": [original],
                    "alias": elastic_alias
                }
            },
            {
                "add": {"indices": [destination], "alias": elastic_alias}
            }
        ]
    }

    response = requests.post(elastic_url + '/_aliases', headers={'Content-Type': 'application/json'}, data=json.dumps(alias_data))
    if response.status_code != status.HTTP_200_OK or not response.ok:
        logger.error('Could not switch the latest index to the live aliases. ', alias_data)
        logger.error("Sync to elastic failed.")
    else:
        logger.error("Sync to elastic successfull.")
        obj.save()
    return


@task()
def consumer_refund_update():
    from ondoc.api.v1.utils import consumers_balance_refund
    from ondoc.account.models import ConsumerRefund
    consumers_balance_refund()
    ConsumerRefund.request_pending_refunds()
    ConsumerRefund.update_refund_status()

@task()
def update_ben_status_from_pg():
    from ondoc.authentication.models import Merchant
    Merchant.update_status_from_pg()
    return True

@task()
def update_merchant_payout_pg_status():
    from ondoc.account.models import MerchantPayout
    # payouts = MerchantPayout.objects.all().order_by('-id')
    # payouts = MerchantPayout.objects.filter(Q(pg_status='SETTLEMENT_COMPLETED')|Q(utr_no__gt='')|Q(utr_no__isnull=False)|Q(type=2))

    payouts = MerchantPayout.objects.filter((Q(pg_status='SETTLEMENT_COMPLETED') & Q(utr_no='')) | Q(status=MerchantPayout.INPROCESS) | Q(type=2))
    for p in payouts:
        p.refresh_from_db()
        p.update_status_from_pg()
    return True

@task(bind=True)
def refund_status_update(self):
    from ondoc.account.models import ConsumerRefund, PgTransaction
    SUCCESS_OK_STATUS = '1'
    FAILURE_OK_STATUS = '0'
    if settings.AUTO_REFUND:
        refund_ids = ConsumerRefund.objects.filter(refund_state=ConsumerRefund.REQUESTED).values_list('id', flat=True)
        url = settings.PG_REFUND_STATUS_API_URL
        token = settings.PG_REFUND_AUTH_TOKEN
        headers = {
            "auth": token
        }
        for ref_id in refund_ids:
            response = requests.get(url=url, params={"refId": ref_id}, headers=headers)
            print(response.url)
            print(response.status_code)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                temp_data = resp_data.get("data")
                code = None
                try:
                    if temp_data:
                        for d in temp_data:
                            if "code" in d:
                                code = d.get("code")
                except:
                    pass
                if resp_data.get("ok") and str(resp_data["ok"]) == SUCCESS_OK_STATUS and code is not None and code != PgTransaction.REFUND_UPDATE_FAILURE_STATUS:
                    with transaction.atomic():
                        obj = ConsumerRefund.objects.select_for_update().get(id=ref_id)
                        if obj.refund_state != ConsumerRefund.COMPLETED:
                            obj.refund_state = ConsumerRefund.COMPLETED
                            obj.save()
                            print("status updated for - " + str(obj.id))
                else:
                    logger.error("Invalid ok status or code mismatch - " + str(response.content))


@task(bind=True, max_retries=6)
def refund_curl_task(self, req_data):
    from ondoc.account.models import ConsumerRefund, PgTransaction
    if settings.AUTO_REFUND:
        print(req_data)
        try:
            token = settings.PG_REFUND_AUTH_TOKEN
            headers = {
                "auth": token,
                "Content-Type": "application/json"
            }
            url = settings.PG_REFUND_URL
            # For test only
            # url = 'http://localhost:8000/api/v1/doctor/test'
            print(url)
            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                logger.error("Response content - " + str(response.content) + " with request data - " + json.dumps(req_data))
                if resp_data.get("ok") is not None and str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS:
                    ConsumerRefund.update_refund_status_on_resp(req_data["refNo"])
                elif (resp_data.get("ok") is not None and str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS and
                      resp_data.get("status") is not None and str(resp_data["status"]) == PgTransaction.PG_REFUND_ALREADY_REQUESTED_STATUS):
                    ConsumerRefund.update_refund_status_on_resp(req_data["refNo"])
                    print("Already Requested")
                elif (resp_data.get("ok") is None or
                      (str(resp_data["ok"]) == PgTransaction.PG_REFUND_FAILURE_OK_STATUS and
                       (resp_data.get("status") is None or str(resp_data["status"]) == PgTransaction.PG_REFUND_FAILURE_STATUS))):
                    print("Refund Failure")
                    raise Exception("Retry on wrong response - " + str(response.content))
                else:
                    print("Incorrect response")
                    raise Exception("Retry on wrong response - " + str(response.content))
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))
        except Exception as e:
            countdown_time = (2 ** self.request.retries) * 60 * 10
            logger.error("Error in Refund with next retry countdown - " + str(countdown_time) + " of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
            self.retry([req_data], countdown=countdown_time)


@task(bind=True, max_retries=5)
def set_order_dummy_transaction(self, order_id, user_id):
    from ondoc.account.models import Order, DummyTransactions
    from ondoc.insurance.models import UserInsurance
    from ondoc.account.models import User
    try:
        if not settings.PAYOUTS_ENABLED:
            return

        order_row = Order.objects.filter(id=order_id).first()
        user = User.objects.filter(id=user_id).first()

        if order_row and user and order_row.reference_id:
            if order_row.getTransactions():
                print("dummy Transaction already set")
                return

            appointment = order_row.getAppointment()
            if not appointment:
                raise Exception("No Appointment found.")

            token = settings.PG_DUMMY_TRANSACTION_TOKEN
            headers = {
                "auth": token,
                "Content-Type": "application/json"
            }
            url = settings.PG_DUMMY_TRANSACTION_URL

            insurer_code = None
            insurance_order_id = None
            insurance_order_number = None
            if order_row.product_id == Order.INSURANCE_PRODUCT_ID:
                insurer_code = appointment.insurance_plan.insurer.insurer_merchant_code

            user_insurance = UserInsurance.get_user_insurance(user)
            if order_row.product_id in [Order.DOCTOR_PRODUCT_ID, Order.LAB_PRODUCT_ID] and user_insurance:
                insurance_order = user_insurance.order

                insurance_order_transactions = insurance_order.getTransactions()
                if not insurance_order_transactions:
                    raise Exception('No transactions found for appointment insurance.')
                insurance_order_transaction = insurance_order_transactions[0]
                insurance_order_id = insurance_order_transaction.order_id
                insurance_order_number = insurance_order_transaction.order_no

            req_data = {
                "customerId": user_id,
                "mobile": user.phone_number,
                "email": user.email or "dummyemail@docprime.com",
                "productId": order_row.product_id,
                "orderId": order_id,
                "name": appointment.profile.name,
                "txAmount": str(appointment.effective_price),
                "couponCode": "",
                "couponAmt": 0,
                "paymentMode": "DC",
                "AppointmentId": order_row.reference_id,
                "buCallbackSuccessUrl": "",
                "buCallbackFailureUrl": ""
            }

            if insurance_order_id and insurance_order_number:
                req_data['refOrderNo'] = insurance_order_number
                req_data['refOrderId'] = insurance_order_id

            if insurer_code:
                req_data['insurerCode'] = insurer_code

            response = requests.post(url, data=json.dumps(req_data), headers=headers)
            if response.status_code == status.HTTP_200_OK:
                resp_data = response.json()
                if resp_data.get("ok") is not None and resp_data.get("ok") == 1:
                    tx_data = {}
                    tx_data['user'] = user
                    tx_data['product_id'] = order_row.product_id
                    tx_data['order_no'] = resp_data.get('orderNo')
                    tx_data['order_id'] = order_row.id
                    tx_data['reference_id'] = order_row.reference_id
                    tx_data['type'] = DummyTransactions.CREDIT
                    tx_data['amount'] = 0
                    tx_data['payment_mode'] = "DC"

                    # tx_data['transaction_id'] = resp_data.get('orderNo')
                    # tx_data['response_code'] = response.get('responseCode')
                    # tx_data['bank_id'] = response.get('bankTxId')
                    # transaction_time = parse(response.get("txDate"))
                    # tx_data['transaction_date'] = transaction_time
                    # tx_data['bank_name'] = response.get('bankName')
                    # tx_data['currency'] = response.get('currency')
                    # tx_data['status_code'] = response.get('statusCode')
                    # tx_data['pg_name'] = response.get('pgGatewayName')
                    # tx_data['status_type'] = response.get('txStatus')
                    # tx_data['pb_gateway_name'] = response.get('pbGatewayName')

                    DummyTransactions.objects.create(**tx_data)
                    print("SAVED DUMMY TRANSACTION")
            else:
                raise Exception("Retry on invalid Http response status - " + str(response.content))

    except Exception as e:
        logger.error("Error in Setting Dummy Transaction of user with data - " + json.dumps(req_data) + " with exception - " + str(e))
        self.retry([order_id, user_id], countdown=300)

@task()
def process_payout(payout_id):
    from ondoc.account.models import MerchantPayout, Order
    from ondoc.api.v1.utils import create_payout_checksum

    try:
        if not settings.PAYOUTS_ENABLED:
            return

        if not payout_id:
            raise Exception("No payout specified")

        payout_data = MerchantPayout.objects.filter(id=payout_id).first()
        if not payout_data or payout_data.status == payout_data.PAID:
            raise Exception("Payment already done for this payout")

        appointment = payout_data.get_appointment()
        billed_to = payout_data.get_billed_to()
        merchant = payout_data.get_merchant()
        order_data = None

        if not appointment or not billed_to or not merchant:
            raise Exception("Insufficient Data " + str(payout_data))

        if not merchant.verified_by_finance or not merchant.enabled:
            raise Exception("Merchant is not verified or is not enabled. " + str(payout_data))

        associated_merchant = billed_to.merchant.first()
        if not associated_merchant.verified:
            raise Exception("Associated Merchant not verified. " + str(payout_data))

        # assuming 1 to 1 relation between Order and Appointment
        order_data = Order.objects.filter(reference_id=appointment.id).order_by('-id').first()

        if not order_data:
             raise Exception("Order not found for given payout " + str(payout_data))

        all_txn = order_data.getTransactions()

        if not all_txn or all_txn.count() == 0:
            raise Exception("No transactions found for given payout " + str(payout_data))

        req_data = { "payload" : [], "checkSum" : "" }

        idx = 0
        for txn in all_txn:
            curr_txn = OrderedDict()
            curr_txn["idx"] = idx
            curr_txn["orderNo"] = txn.order_no
            curr_txn["orderId"] = order_data.id
            curr_txn["txnAmount"] = str(order_data.amount)
            curr_txn["settledAmount"] = str(payout_data.payable_amount)
            curr_txn["merchantCode"] = merchant.id
            curr_txn["pgtxId"] = txn.transaction_id
            curr_txn["refNo"] = txn.id
            curr_txn["bookingId"] = appointment.id
            req_data["payload"].append(curr_txn)
            idx += 1

        req_data["checkSum"] = create_payout_checksum(req_data["payload"], order_data.product_id)
        headers = {
            "auth": settings.PG_REFUND_AUTH_TOKEN,
            "Content-Type": "application/json"
        }
        url = settings.PG_SETTLEMENT_URL

        response = requests.post(url, data=json.dumps(req_data), headers=headers)
        if response.status_code == status.HTTP_200_OK:
            resp_data = response.json()
            if resp_data.get("ok") is not None and resp_data.get("ok") == '1':
                success_payout = False
                result = resp_data.get('result')
                if result:
                    for res_txn in result:
                        success_payout = res_txn['status'] == "SUCCESSFULLY_INSERTED"

                if success_payout:
                    payout_data.payout_time = datetime.datetime.now()
                    payout_data.status = payout_data.PAID
                    payout_data.api_response = json.dumps(resp_data)
                    payout_data.save()
                    print("Payout processed")
                    return

        payout_data.retry_count += 1
        payout_data.api_response = json.dumps(resp_data)
        payout_data.save()
        raise Exception("Retry on invalid Http response status - " + str(response.content))

    except Exception as e:
        logger.error("Error in processing payout - with exception - " + str(e))


@task()
def integrator_order_summary():
    from ondoc.integrations.models import IntegratorResponse
    IntegratorResponse.get_order_summary()

@task()
def get_thyrocare_reports():
    from ondoc.integrations.Integrators import Thyrocare
    Thyrocare.get_generated_report()

@task()
def create_appointment_admins_from_spocs():
    from ondoc.authentication.models import SPOCDetails, GenericAdmin
    SPOCDetails.create_appointment_admins_from_spocs()
    GenericAdmin.create_users_from_generic_admins()

@task()
def add_net_revenue_for_merchant():
    from ondoc.doctor.models import OpdAppointment
    from ondoc.diagnostic.models import LabAppointment
    opd_appointments_count = OpdAppointment.objects.count()
    opd_appointments = OpdAppointment.objects.filter(status=OpdAppointment.COMPLETED)[0:opd_appointments_count]
    appointment_wise_revenue(opd_appointments)
    print('Opd Appointment Done')

    lab_appointments_count = LabAppointment.objects.count()
    lab_appointments = LabAppointment.objects.filter(status=LabAppointment.COMPLETED)[0:lab_appointments_count]
    appointment_wise_revenue(lab_appointments)
    print('Lab Appointment Done')


def appointment_wise_revenue(all_appointments):
    from ondoc.authentication.models import MerchantNetRevenue
    with transaction.atomic():
        for appointment in all_appointments.iterator(chunk_size=100):
            created_at = datetime.datetime.strptime(appointment.created_at.strftime("%Y-%m-%d"), "%Y-%m-%d")
            financial_year_end = datetime.datetime.strptime('2019-03-31', "%Y-%m-%d")

            if created_at <= financial_year_end:
                financial_year = "2018-2019"
            else:
                financial_year = '2019-2020'

            # Create net revenue
            booking_net_revenue = appointment.get_booking_revenue()
            merchant = appointment.get_merchant
            if merchant:
                # print(booking_net_revenue)
                net_revenue_obj = MerchantNetRevenue.objects.filter(merchant=merchant, financial_year=financial_year).first()
                if net_revenue_obj:
                    net_revenue_obj.total_revenue += booking_net_revenue
                    net_revenue_obj.save()
                else:
                    MerchantNetRevenue.objects.create(merchant=merchant, total_revenue=booking_net_revenue,
                                                      financial_year=financial_year)
