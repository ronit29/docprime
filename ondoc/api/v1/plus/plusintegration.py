from ondoc.plus.models import PlusUser, PlusMembers, PlusPlans, PlusPlanUtmSources, PlusPlanUtmSourceMapping
from django.conf import settings
import requests
from rest_framework import status
import logging
import json
logger = logging.getLogger(__name__)


class PlusIntegration:

    @classmethod
    def get_response(cls, data):
        resp = {}
        response = None
        utm_source = data.get('utm_source', None)
        utm_source_obj = PlusPlanUtmSources.objects.filter(source=utm_source).first()
        utm_mapping_obj = PlusPlanUtmSourceMapping.objects.filter(utm_source=utm_source_obj).first()
        if not utm_mapping_obj:
            return {}
        plus_plan = utm_mapping_obj.plus_plan
        if not utm_source or not plus_plan:
            return {}
        if not data.get('booking_detail', None):
            data = PlusIntegration.transform_data(data)
        if utm_source == "OfflineAffiliate":
            resp['url'] = settings.VIP_SALESPOINT_URL
            resp['auth_token'] = settings.VIP_SALESPOINT_AUTHTOKEN
            resp['request_data'] = PlusIntegration.get_docprime_data(data)

        response = PlusIntegration.push_lead(resp)
        return response

    @classmethod
    def get_docprime_data(cls, data):
        plan = data.get('plan', None)
        member = data.get('member', None)
        utm_params = data.get('utm_spo_tags', None)
        booking_detail = data.get('booking_detail', None)
        email = ""
        plan_id = None
        plan_name = ""
        email = ""
        name = ""
        address = ""
        dob = ""
        phone_number = ""
        utm_term = ""
        utm_medium = ""
        utm_campaign = ""
        utm_source = ""
        plus_user_id = None
        user_id = None
        order_id = None
        booking_status = None

        if plan:
            plan_id = plan.get('id', None)
            plan_name = plan.get('plan_name', "")
        if member:
            email = member.get('email', "")
            name = member.get('name', "")
            address = member.get('address', "")
            dob = member.get('dob', "")
            phone_number = member.get('phone_number', "")
        if utm_params:
            utm_term = utm_params.get('utm_term', "")
            utm_medium = utm_params.get('utm_medium', "")
            utm_campaign = utm_params.get('utm_campaign', "")
            utm_source = utm_params.get('utm_source', "")
        if booking_detail:
            plus_user_id = booking_detail.get('plus_user_id', None)
            user_id = booking_detail.get('user_id', None)
            order_id = booking_detail.get('order_id', None)
            booking_status = booking_detail.get('booking_status', None)

        request_data = { "IPDHospital": "",
                            "IsInsured": None,
                            "PolicyLink": "",
                            "InsurancePolicyNumber": None,
                            "AppointmentStatus": booking_status,
                            "Age": None,
                            "Email": email,
                            "VirtualNo": "",
                            "OTP": "",
                            "KYC": None,
                            "Location": "",
                            "PaymentType": None,
                            "PaymentTypeId": None,
                            "PaymentStatus": None,
                            "OrderID": order_id,
                            "DocPrimeBookingID": plus_user_id,
                            "BookingDateTime": None,
                            "AppointmentDateTime": None,
                            "BookingType": "VIP",
                            "AppointmentType": "",
                            "IsHomePickUp": 0,
                            "HomePickupAddress": "",
                            "PatientName": name,
                            "PatientAddress": address,
                            "ProviderName": "",
                            "ServiceID": plan_id,
                            "ServiceName": plan_name,
                            "InsuranceCover": 0,
                            "BookingUrl": "",
                            "Fees": None,
                            "EffectivePrice": None,
                            "MRP": None,
                            "DealPrice": None,
                            "DOB": dob,
                            "ProviderAddress": "",
                            "ProviderID": None,
                            "ProviderBookingID": "",
                            "MerchantCode": "",
                            "ProviderPaymentStatus": "",
                            "PaymentURN": "",
                            "Amount": None,
                            "SettlementDate": None,
                            "LocationVerified": 0,
                            "ReportUploaded": 0,
                            "Reportsent": None,
                            "AcceptedBy": "",
                            "AcceptedPhone": None,
                            "CustomerStatus": "",
                            "RefundPaymentMode": None,
                            "RefundToWallet": None,
                            "RefundInitiationDate": None,
                            "RefundURN": "",
                            "HospitalName": "",
                            "DocPrimeUserId": user_id,
                            "LeadID": 0,
                            "Name": name,
                            "PrimaryNo": str(phone_number),
                            "LeadSource": "DocPrime",
                            "EmailId": "",
                            "Gender": None,
                            "CityId": 0,
                            "ProductId": 5,
                            "SubProductId": None,
                            "UtmTerm": utm_term,
                            "UtmMedium": utm_medium,
                            "UtmCampaign": utm_campaign,
                            "UtmSource": utm_source,
                            "PlanName": plan_name,
                            "PlanID": plan_id
                            }

        return request_data


    @classmethod
    def transform_data(cls, data):
        format_data = {}
        plan = data.get('plan', None)
        member = data.get('members', None)
        phone_number = data.get('phone_number', None)
        name = data.get('name', "")
        if plan and member:
            format_data['plan'] = plan
            format_data['member'] = member[0]
        else:
            format_data['plan'] = None
            format_data['member'] = {"phone_number": phone_number, "name": name}

        return format_data

    @classmethod
    def push_lead(cls, utm_param_dict):
        resp = {}
        if not utm_param_dict:
            resp['error'] = "Not able to find UTM Params"
            return resp
        try:
            url = utm_param_dict.get('url', "")
            request_data = utm_param_dict.get('request_data', {})
            auth_token = utm_param_dict.get('auth_token', "")

            response = requests.post(url, data=json.dumps(request_data), headers={'Authorization': auth_token,
                                                                                  'Content-Type': 'application/json'})

            if response.status_code != status.HTTP_200_OK:
                logger.error(json.dumps(request_data))
                logger.info("[ERROR] could not get 200 for process VIP Lead ")
                resp['error'] = "Error while saving data!!"
            else:
                resp['data'] = "successfully save!!"
        except Exception as e:
            logger.error(json.dumps(request_data))
            logger.info("[ERROR] {}".format(e))
        return resp

    @classmethod
    def create_vip_lead_after_purchase(cls, plus_obj):
        resp = {}
        plan = {}
        member = {}
        booking_detail = {}
        plus_plan = plus_obj.plan
        if not plus_plan:
            return resp

        order = plus_obj.order
        action_data = order.action_data
        utm_params = action_data.get('utm_parameter', None)
        utm_source =utm_params.get('utm_source', None)
        if not utm_source:
            return

        plan['plan_name'] = plus_plan.name
        plan['plan_id'] = plus_plan.id
        plus_member = plus_obj.plus_members.all().filter(relation=PlusMembers.Relations.SELF).first()
        member['name'] = plus_member.first_name
        member['dob'] = plus_member.dob
        member['email'] = plus_member.email
        member['address'] = plus_member.address
        member['phone_number'] = plus_member.phone_number

        booking_detail['booking_id'] = plus_obj.id
        booking_detail['user_id'] = plus_obj.user.id
        booking_detail['booking_status'] = 300
        booking_detail['order_id'] = order.id

        resp['plan'] = plan
        resp['members'] = member
        resp['booking_detail'] = booking_detail
        resp['utm_source'] = utm_source
        resp['utm_spo_tags'] = utm_params

        resp = PlusIntegration.get_response(resp)
        # return Response(data=resp, status=status.HTTP_200_OK)
