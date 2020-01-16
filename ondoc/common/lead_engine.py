from abc import ABC, abstractmethod
from django.conf import settings
import requests
import logging
from typing import Dict, Tuple
from rest_framework import status
from ondoc.notification.tasks import save_matrix_logs
logger = logging.getLogger(__name__)
from datetime import datetime
import json


class AbstractLead(ABC):
    def __init__(self, obj, obj_type):
        self.obj = obj
        self.obj_type = obj_type
        super(AbstractLead, self).__init__()

    @abstractmethod
    def prepare_lead_data(self, *args, **kwargs) -> Dict:
        """ Prepare the custom request payload for the matrix.

        :param args:
        :param kwargs:
        :return: an Dict instance of matrix request payload.

        """
        pass

    @abstractmethod
    def update_matrix_lead_id(self, response, *args, **kwargs):
        """ After the lead has been created in the matrix, we need to update the corrosponding
        model with the lead id returned from the matrix response. Every model bind matrix lead id with different name.

        :param response: Response received from the matrix in variable `Id`.
        :param args:
        :param kwargs:
        :return:

        """
        pass

    def push_data_to_matrix(self, request_data: dict, *args, **kwargs) -> Tuple[int, dict]:
        resp_data = None
        url = settings.MATRIX_API_URL
        matrix_api_token = settings.MATRIX_API_TOKEN
        response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': matrix_api_token,
                                                                              'Content-Type': 'application/json'})
        if response.status_code != status.HTTP_200_OK or not response.ok:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] Plus lead could not be published to the matrix system")
            logger.info("[ERROR] %s", response.reason)
            status_code = response.status_code
        else:
            status_code = 200
            resp_data = response.json()

        return status_code, resp_data

    def log_responses(self, request_data: dict, response_data: dict, *args, **kwargs):
        save_matrix_logs.apply_async((self.obj.id, self.obj_type, request_data, response_data), countdown=5, queue=settings.RABBITMQ_LOGS_QUEUE)

    def process_lead(self, *args, **kwargs) -> bool:
        try:
            request_data = self.prepare_lead_data()
            raw_response = self.push_data_to_matrix(request_data)
            status_code, response = raw_response[0], raw_response[1]
            if status_code == status.HTTP_200_OK:
                self.update_matrix_lead_id(response)
            else:
                raise Exception('200 not received from matrix.')

            self.log_responses(request_data, response)

        except Exception as e:
            logger.error(str(e))
            logger.error('Error pushing data to the matrix with object id %d of model %s' % (self.obj.id, self.obj.__class__.__name__))
            return False

        return True


class DropOff(AbstractLead):

    def __init__(self, obj):
        super(DropOff, self).__init__(obj, "general_leads")

    def update_matrix_lead_id(self, response, *args, **kwargs):
        from ondoc.common.models import GeneralMatrixLeads
        lead_id = response.get('Id')
        if not lead_id:
            raise Exception('Id not received from matrix')

        GeneralMatrixLeads.objects.filter(id=self.obj.id).update(matrix_lead_id=lead_id)

    def prepare_lead_data(self, *args, **kwargs) -> Dict:
        obj = self.obj
        request_data = obj.request_body
        user = obj.user if obj.user else None

        appointment_time = None
        if request_data.get('selected_date') and request_data.get('selected_time'):
            appointment_time = request_data.get('selected_date').split('T')[0] + " " + request_data.get('selected_time')
            appointment_time = datetime.strptime(appointment_time, '%Y-%m-%d %H:%M %p')
            appointment_time = int(appointment_time.timestamp())

        data = {
            "SubProductId": 0,
            "IsInsured": "yes" if user and user.active_insurance and user.active_insurance.is_valid() else "no",
            "LeadSource": request_data.get('lead_source'),
            "LabTest": request_data.get('test_name', ''),
            "LabName": request_data.get('lab_name', ''),
            "AppointmentDate": appointment_time,
            "DoctorName": request_data.get('doctor_name'),
            "DoctorSpec": request_data.get('specialty', ''),
            "IPDHospitalName": request_data.get('hospital_name', ''),
            "ProductId": 11,
            "UtmTerm": request_data.get('source', {}).get('utm_term', ''),
            "PrimaryNo": request_data.get('phone_number') if not user else str(user.phone_number),
            "UtmCampaign": request_data.get('source', {}).get('utm_campaign', ''),
            "UTMMedium": request_data.get('source', {}).get('utm_medium', ''),
            "Name": user.full_name if user else 'none',
            "UtmSource": request_data.get('source', {}).get('utm_source', ''),
            "ExitPointUrl": request_data.get('exitpoint_url', '')
        }

        return data


class Medicine(AbstractLead):

    def __init__(self, obj):
        super(Medicine, self).__init__(obj, "general_leads")

    def update_matrix_lead_id(self, response, *args, **kwargs):
        from ondoc.common.models import GeneralMatrixLeads
        lead_id = response.get('Id')
        if not lead_id:
            raise Exception('Id not received from matrix')

        GeneralMatrixLeads.objects.filter(id=self.obj.id).update(matrix_lead_id=lead_id)

    def prepare_lead_data(self, *args, **kwargs) -> Dict:
        obj = self.obj
        request_data = obj.request_body
        user = obj.user if obj.user else None

        data = {
            "SubProductId": 0,
            "PaymentStatus": 0,
            "IsInsured": "yes" if user and user.active_insurance and user.active_insurance.is_valid() else "no",
            "IPDIsInsured": 1 if user and user.active_insurance and user.active_insurance.is_valid() else 0,
            "LeadSource": request_data.get('lead_source'),
            "ProductId": 11,
            "UtmTerm": request_data.get('source', {}).get('utm_term', ''),
            "PrimaryNo": request_data.get('phone_number') if not user else str(user.phone_number),
            "UtmCampaign": request_data.get('source', {}).get('utm_campaign', ''),
            "UTMMedium": request_data.get('source', {}).get('utm_medium', ''),
            "Name": user.full_name if user else 'none',
            "UtmSource": request_data.get('source', {}).get('utm_source', ''),
        }

        return data


class LabAds(AbstractLead):

    def __init__(self, obj):
        super(LabAds, self).__init__(obj, "general_leads")

    def update_matrix_lead_id(self, response, *args, **kwargs):
        from ondoc.common.models import GeneralMatrixLeads
        lead_id = response.get('Id')
        if not lead_id:
            raise Exception('Id not received from matrix')

        GeneralMatrixLeads.objects.filter(id=self.obj.id).update(matrix_lead_id=lead_id)

    def prepare_lead_data(self, *args, **kwargs) -> Dict:
        obj = self.obj
        request_data = obj.request_body
        user = obj.user if obj.user else None

        data = {
            "SubProductId": 0,
            "IsInsured": "yes" if user and user.active_insurance and user.active_insurance.is_valid() else "no",
            "LeadSource": request_data.get('lead_source'),
            "LabTest": request_data.get('test_name', ''),
            "LabName": request_data.get('lab_name', ''),
            # "AppointmentDate": appointment_time,
            "DoctorName": request_data.get('doctor_name'),
            "DoctorSpec": request_data.get('specialty', ''),
            "IPDHospitalName": request_data.get('hospital_name', ''),
            "ProductId": 11,
            "UtmTerm": request_data.get('source', {}).get('utm_term', ''),
            "PrimaryNo": request_data.get('phone_number') if not user else str(user.phone_number),
            "UtmCampaign": request_data.get('source', {}).get('utm_campaign', ''),
            "UTMMedium": request_data.get('source', {}).get('utm_medium', ''),
            "Name": user.full_name if user else 'none',
            "UtmSource": request_data.get('source', {}).get('utm_source', ''),
            "ExitPointUrl": request_data.get('exitpoint_url', '')
        }

        return data


class CancelDropOffLeadViaAppointment(AbstractLead):

    def __init__(self, obj):
        super(CancelDropOffLeadViaAppointment, self).__init__(obj, None)

    def update_matrix_lead_id(self, response, *args, **kwargs):
        pass

    def prepare_lead_data(self, *args, **kwargs) -> Dict:
        obj = self.obj
        user = self.obj.user if obj.user else None
        if not user:
            return {}

        data = {
            "SubProductId": 0,
            "LeadSource": "crm",
            "ProductId": 11,
            "Status": 13,
            "PrimaryNo": str(user.phone_number),
            "Name": 'none',
            "PolicyDetails":
                {
                    "ProposalNo": "0",
                    "ProposerName": "none",
                    "PolicyId": "0",
                    "PolicyPaymentSTATUS": 300,
                    "InsurancePlanPurchased": "no",
                }
        }

        return data


lead_class_mapping = {
    'MEDICINE': Medicine,
    'DROPOFF': DropOff,
    'LABADS': LabAds,
    'CANCELDROPOFFLEADVIAAPPOINTMENT': CancelDropOffLeadViaAppointment
}


def lead_class_referance(lead_type, entity):
    if not lead_type or not entity:
        return None

    if lead_type not in list(lead_class_mapping.keys()):
        return None

    klass = lead_class_mapping[lead_type]
    obj = klass(entity)
    return obj
