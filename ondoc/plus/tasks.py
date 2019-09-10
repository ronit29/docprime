from __future__ import absolute_import, unicode_literals

from rest_framework import status
from django.conf import settings
from celery import task
import requests

import json
import logging

logger = logging.getLogger(__name__)


@task(bind=True, max_retries=2)
def push_plus_buy_to_matrix(self, *args, **kwargs):
    from ondoc.authentication.models import User
    from ondoc.plus.models import PlusUser, PlusLead
    try:
        user_id = kwargs.get('user_id', None)
        if not user_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        user_obj = User.objects.filter(id=user_id).first()

        if not user_obj:
            raise Exception("User could not found against id - " + str(user_id))

        plus_user_obj = user_obj.active_plus_user
        if not plus_user_obj:
            raise Exception("Invalid or None plus membership found for user id %s " % str(user_id))

        primary_proposer = plus_user_obj.get_primary_member_profile()
        if not primary_proposer:
            raise Exception('Plus Membership does not have the primary proposer. Insurance id ' + str(plus_user_obj.id))

        if not plus_user_obj.matrix_lead_id:
            plus_user_obj.matrix_lead_id = PlusLead.get_latest_lead_id(plus_user_obj.user)
            plus_user_obj.save()

        request_data = {
            'LeadSource': 'Docprime',
            'Name': primary_proposer.get_full_name(),
            'BookedBy': user_obj.phone_number,
            'LeadID': plus_user_obj.matrix_lead_id if plus_user_obj.matrix_lead_id else 0,
            'PrimaryNo': user_obj.phone_number,
            'ProductId': 11,
            'SubProductId': 0,
            "PolicyDetails": {
                "ProposalNo": None,
                "BookingId": plus_user_obj.id,
                'PolicyPaymentSTATUS': 300,
                "ProposerName": primary_proposer.get_full_name(),
                "InsurancePlanPurchased": plus_user_obj.insurance_plan.name,
                "PurchaseDate": int(plus_user_obj.purchase_date.timestamp()),
                "ExpirationDate": int(plus_user_obj.expire_date.timestamp()),
            }
        }

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Insurance could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry(**kwargs, countdown=countdown_time)
        else:
            resp_data = response.json()
            if not resp_data:
                raise Exception('Data received from matrix is null or empty.')

            if not resp_data.get('Id', None):
                logger.error(json.dumps(request_data))
                raise Exception("[ERROR] Id not recieved from the matrix while pushing insurance to matrix.")

            user_insurance_qs = PlusUser.objects.filter(id=plus_user_obj.id)
            user_insurance_qs.update(matrix_lead_id=resp_data.get('Id'))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing insurance to the matrix- " + str(e))
