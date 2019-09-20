import operator
from ondoc.plus.models import PlusUser, PlusMembers, PlusPlans, PlusPlanUtmSources, PlusPlanUtmSourceMapping
from django.conf import settings


class PlusIntegration:

    @classmethod
    def get_response(cls, data):
        resp = {}
        utm_source = data.get('utm_source', None)
        utm_source_obj = PlusPlanUtmSources.objects.filter(source=utm_source).first()
        utm_mapping_obj = PlusPlanUtmSourceMapping.objects.filter(utm_source=utm_source_obj).first()
        if not utm_mapping_obj:
            return {}
        plus_plan = utm_mapping_obj.plus_plan
        # plus_plan = PlusPlans.objects.filter(is_live=True, utm_source__containing=utm_source).first()
        if not utm_source or not plus_plan:
            return {}
        data = PlusIntegration.transform_data(data)
        if utm_source == "OnlineAffiliate":
            resp['url'] = settings.VIP_SALESPOINT_URL
            resp['auth_token'] = settings.VIP_SALESPOINT_AUTHTOKEN
            resp['request_data'] = PlusIntegration.get_docprime_data(data)


        return resp

    @classmethod
    def get_docprime_data(cls, data):
        plan = data.get('plan', None)
        member = data.get('member', None)
        email = ""
        plan_id = None
        plan_name = ""
        email = ""
        name = ""
        address = ""
        dob = ""
        phone_number = ""
        if plan:
            plan_id = plan.get('plan_id', None)
            plan_name = plan.get('plan_name', "")
        if member:
            email = member.get('email', "")
            name = member.get('name', "")
            address = member.get('address', "")
            dob = member.get('dob', "")
            phone_number = member.get('phone_number', "")

        request_data = { "IPDHospital": "",
                            "IsInsured": None,
                            "PolicyLink": "",
                            "InsurancePolicyNumber": None,
                            "AppointmentStatus": None,
                            "Age": None,
                            "Email": email,
                            "VirtualNo": "",
                            "OTP": "",
                            "KYC": None,
                            "Location": "",
                            "PaymentType": None,
                            "PaymentTypeId": None,
                            "PaymentStatus": None,
                            "OrderID": None,
                            "DocPrimeBookingID": None,
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
                            "DocPrimeUserId": None,
                            "LeadID": 0,
                            "Name": name,
                            "PrimaryNo": str(phone_number),
                            "LeadSource": "DocPrime",
                            "EmailId": "",
                            "Gender": None,
                            "CityId": 0,
                            "ProductId": 5,
                            "SubProductId": None,
                            "UtmTerm": "ADRM5",
                            "UtmMedium": "ADRM5",
                            "UtmCampaign": "ADRM5",
                            "UtmSource": "OfflineAffiliate",
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
