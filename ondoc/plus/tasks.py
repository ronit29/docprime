from __future__ import absolute_import, unicode_literals

from rest_framework import status
from django.conf import settings
from celery import task
import requests

import json
import logging

from ondoc.matrix.mongo_models import MatrixLog

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

        plus_user_obj = PlusUser.objects.filter(user=user_obj).order_by('id').last()
        if not plus_user_obj:
            raise Exception("Invalid or None plus membership found for user id %s " % str(user_id))

        primary_proposer = plus_user_obj.get_primary_member_profile()
        if not primary_proposer:
            raise Exception('Plus Membership does not have the primary proposer. Insurance id ' + str(plus_user_obj.id))

        if not plus_user_obj.matrix_lead_id:
            plus_user_obj.matrix_lead_id = PlusLead.get_latest_lead_id(plus_user_obj.user)
            plus_user_obj.save()

        request_data = {
            "IsRadiology": False,
            "IsPathology": False,
            "Name": primary_proposer.get_full_name(),
            "Address": primary_proposer.address,
            "YearsOfExp": 0,
            'LeadID': plus_user_obj.matrix_lead_id if plus_user_obj.matrix_lead_id else 0,
            "CityId": 0,
            "NumberofDoctor": 0,
            "NumberOfClinic": 0,
            "IsRetail": False,
            "IsPPC": False,
            "SpecialityIdList": None,
            "DMCNo": None,
            "ProductId": 11,
            "PrimaryNo": user_obj.phone_number,
            "Gender": "1",
            "SubProductId": 0,
            "LeadSource": "Docprime",
            "PolicyDetails":
                {
                    "ProposalNo": "0",
                    "BookingId": plus_user_obj.id,
                    "ProposerName": primary_proposer.get_full_name(),
                    "PolicyId": "0",
                    "PolicyPaymentSTATUS": 300,
                    "InsurancePlanPurchased": "no",
                    "PurchaseDate": int(plus_user_obj.purchase_date.timestamp()),
                    "ExpirationDate": int(plus_user_obj.expire_date.timestamp()),
                    "PeopleCovered": "yes"
                }
        }

        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})

        MatrixLog.create_matrix_logs(plus_user_obj, request_data, response.json())

        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Vip membership could not be published to the matrix system")
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

            user_plus_qs = PlusUser.objects.filter(id=plus_user_obj.id)
            user_plus_qs.update(matrix_lead_id=resp_data.get('Id'))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing vip to the matrix- " + str(e))
