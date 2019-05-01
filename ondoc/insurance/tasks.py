from __future__ import absolute_import, unicode_literals

from django.core.files.uploadedfile import TemporaryUploadedFile, InMemoryUploadedFile
from rest_framework import status
from django.conf import settings
from celery import task
import requests

import json
import logging


logger = logging.getLogger(__name__)


@task(bind=True, max_retries=2)
def push_insurance_banner_lead_to_matrix(self, data):
    from ondoc.authentication.models import User
    from ondoc.insurance.models import InsuranceLead, InsurancePlans
    try:
        if not data:
            raise Exception('Data not received for banner lead.')

        id = data.get('id', None)
        if not id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        banner_obj = InsuranceLead.objects.filter(id=id).first()

        if not banner_obj:
            raise Exception("Banner object could not found against id - " + str(id))

        extras = banner_obj.extras
        plan = InsurancePlans.objects.filter(id=extras.get('plan_id', 0)).first()

        request_data = {
            'LeadID': banner_obj.matrix_lead_id if banner_obj.matrix_lead_id else 0,
            'LeadSource': 'InsuranceOPD',
            'Name': 'none',
            'BookedBy': banner_obj.user.phone_number,
            'PrimaryNo': banner_obj.user.phone_number,
            'PaymentStatus': 0,
            'UtmCampaign': extras.get('utm_campaign', ''),
            'UTMMedium': extras.get('utm_medium', ''),
            'UtmSource': extras.get('utm_source', ''),
            'UtmTerm': extras.get('utm_term', ''),
            'ProductId': 5,
            'SubProductId': 3,
            'PolicyDetails': {
                "ProposalNo": None,
                "BookingId": None,
                'PolicyPaymentSTATUS': 0,
                "ProposerName": None,
                "PolicyId": None,
                "InsurancePlanPurchased": plan.name if plan else None,
                "PurchaseDate": None,
                "ExpirationDate": None,
                "COILink": None,
                "PeopleCovered": 0
            }
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

            insurance_banner_qs = InsuranceLead.objects.filter(id=id)
            insurance_banner_qs.update(matrix_lead_id=resp_data.get('Id'))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing insurance banner lead to the matrix- " + str(e))



@task(bind=True, max_retries=2)
def push_insurance_buy_to_matrix(self, *args, **kwargs):
    from ondoc.authentication.models import User
    from ondoc.insurance.models import UserInsurance, InsuranceLead
    try:
        user_id = kwargs.get('user_id', None)
        if not user_id:
            logger.error("[CELERY ERROR: Incorrect values provided.]")
            raise ValueError()

        user_obj = User.objects.filter(id=user_id).first()

        if not user_obj:
            raise Exception("User could not found against id - " + str(user_id))

        user_insurance = user_obj.active_insurance
        if not user_insurance:
            raise Exception("Invalid or None user insurance found for user id %s " % str(user_id))

        primary_proposer = user_insurance.get_primary_member_profile()
        if not primary_proposer:
            raise Exception('Insurance does not have the primary proposer. Insurance id ' + str(user_insurance.id))

        if not user_insurance.matrix_lead_id:
            user_insurance.matrix_lead_id = InsuranceLead.get_latest_lead_id(user_insurance.user)
            user_insurance.save()

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
                'PolicyPaymentSTATUS': 300,
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

            # user_insurance_qs = UserInsurance.objects.filter(id=user_insurance.id)
            # user_insurance_qs.update(matrix_lead_id=resp_data.get('Id'))

    except Exception as e:
        logger.error("Error in Celery. Failed pushing insurance to the matrix- " + str(e))

@task()
def push_mis():
    from ondoc.insurance.models import InsuranceMIS
    from ondoc.notification.models import EmailNotification
    from ondoc.api.v1.utils import util_absolute_url
    from ondoc.crm.admin.insurance import UserInsuranceResource, UserInsuranceDoctorResource, UserInsuranceLabResource
    from datetime import datetime, timedelta
    from io import StringIO, BytesIO
    import zipfile
    in_memory = BytesIO()
    zip = zipfile.ZipFile(in_memory, "a", zipfile.ZIP_DEFLATED, False)

    resources = [
        (UserInsuranceResource, InsuranceMIS.AttachmentType.USER_INSURANCE_RESOURCE),
        (UserInsuranceDoctorResource, InsuranceMIS.AttachmentType.USER_INSURANCE_DOCTOR_RESOURCE),
        (UserInsuranceLabResource, InsuranceMIS.AttachmentType.USER_INSURANCE_LAB_RESOURCE)
    ]

    from_date = str(datetime.now().date() - timedelta(days=1))
    to_date = str(datetime.now().date())
    arguments = {
        'from_date': from_date,
        'to_date': to_date,
    }

    email_attachments = []

    for resource in resources:
        resource_obj = resource[0]()

        dataset = resource_obj.export(**arguments)
        filename = "%s_%s_%s.xls" % (resource_obj.__class__.__name__ , from_date, to_date)
        zip.writestr(filename, dataset.xls)

    # zip.setpassword("akusaini".encode('utf-8'))
    for zfile in zip.filelist:
        zfile.create_system = 0

    zip.setpassword("akusaini".encode('utf-8'))
    zip.close()

    in_memory.seek(0)
    data = in_memory.read()
    pos = data.find('\x50\x4b\x05\x06'.encode())  # End of central directory signature
    if (pos > 0):
        in_memory.seek(pos + 22)  # size of 'ZIP end of central directory record'
        in_memory.truncate()
        # in_memory.close()

    in_memory.seek(0)
    filename = "All_MIS_%s_%s.zip" % (from_date, to_date)
    file = TemporaryUploadedFile(filename, 'byte', 1000, 'utf-8')
    f = open(file.temporary_file_path(), 'wb')
    f.write(in_memory.read())
    f.seek(0)
    f.flush()
    f.content_type = 'application/zip'

    attachment = InMemoryUploadedFile(file, None, filename, 'application/zip', file.tell(), None)
    insurance_mis_obj = InsuranceMIS(attachment_file=attachment, attachment_type=InsuranceMIS.AttachmentType.ALL_MIS_ZIP)
    insurance_mis_obj.save()

    print(insurance_mis_obj.attachment_file.url)
    email_attachments.append({'filename': filename, 'path': util_absolute_url(insurance_mis_obj.attachment_file.url)})

    EmailNotification.send_insurance_mis(email_attachments)
