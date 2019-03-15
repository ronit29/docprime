from __future__ import absolute_import, unicode_literals
from rest_framework import status
from django.conf import settings
from celery import task
import requests

from ondoc.authentication.models import User
import json
import logging


logger = logging.getLogger(__name__)


@task(bind=True, max_retries=2)
def push_insurance_banner_lead_to_matrix(self, data):
    from ondoc.insurance.models import InsuranceBannerLead
    try:
        if not data:
            raise Exception('Data not received for banner lead.')

        id = data.get('id', None)
        if not id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        banner_obj = InsuranceBannerLead.objects.filter(id=id).first()

        if not banner_obj:
            raise Exception("Banner object could not found against id - " + str(id))

        request_data = {
            'LeadSource': 'InsuranceOPD',
            'Name': None,
            'BookedBy': banner_obj.user.phone_number,
            'PrimaryNo': banner_obj.user.phone_number,
            'ProductId': 5,
            'SubProductId': 3,
        }

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Insurance banner lead could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)

            countdown_time = (2 ** self.request.retries) * 60 * 10
            logging.error("Lead sync with the Matrix System failed with response - " + str(response.content))
            print(countdown_time)
            self.retry([data], countdown=countdown_time)
        else:
            resp_data = response.json()
            if not resp_data:
                raise Exception('Data received from matrix is null or empty.')

            if not resp_data.get('Id', None):
                logger.error(json.dumps(request_data))
                raise Exception("[ERROR] Id not recieved from the matrix while pushing insurance banner lead to matrix.")

            insurance_banner_qs = InsuranceBannerLead.objects.filter(id=id)
            insurance_banner_qs.update(matrix_lead_id=resp_data.get('Id'))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing insurance banner lead to the matrix- " + str(e))



@task(bind=True, max_retries=2)
def push_insurance_buy_to_matrix(self, *args, **kwargs):
    from ondoc.insurance.models import UserInsurance
    try:
        user_id = kwargs.get('user_id', None)
        if not user_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        user_obj = User.objects.filter(id=user_id).first()

        if not user_obj:
            raise Exception("User could not found against id - " + str(user_id))

        user_insurance = user_obj.purchased_insurance.filter().last()
        if not user_insurance or not user_insurance.is_valid():
            logger.error("Invalid or None user insurance found for email notification")

        primary_proposer = user_insurance.get_primary_member_profile()
        if not primary_proposer:
            raise Exception('Insurance does not have the primary proposer. Insurance id ' + str(user_insurance.id))

        request_data = {
            'LeadSource': 'InsuranceOPD',
            'Name': primary_proposer.get_full_name(),
            'BookedBy': user_obj.phone_number,
            'LeadID': user_insurance.matrix_lead_id if user_insurance.matrix_lead_id else 0,
            'PrimaryNo': user_obj.phone_number,
            'ProductId': 5,
            'SubProductId': 3,
            "PolicyDetails": {
                "ProposalNo": None,
                "BookingId": user_insurance.id,
                "ProposerName": primary_proposer.get_full_name(),
                "PolicyId": user_insurance.policy_number,
                "InsurancePlanPurchased": user_insurance.insurance_plan.name,
                "PurchaseDate": int(user_insurance.purchase_date.timestamp()),
                "ExpirationDate": int(user_insurance.expiry_date.timestamp()),
                "COILink": user_insurance.coi.url if user_insurance.coi is not None and user_insurance.coi.name else None,
                "PeopleCovered": user_insurance.insurance_plan.get_people_covered()

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

            user_insurance_qs = UserInsurance.objects.filter(id=user_insurance.id)
            user_insurance_qs.update(matrix_lead_id=resp_data.get('Id'))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing insurance to the matrix- " + str(e))

