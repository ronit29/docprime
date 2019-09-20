import operator
from ondoc.plus.models import PlusUser, PlusMembers, PlusPlans, PlusPlanUtmSources, PlusPlanUtmSourceMapping
from django.conf import settings


class PlusIntegration:

    @classmethod
    def get_response(self, data):
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
        if utm_source == "OnlineAffiliate":
            resp['url'] = settings.VIP_SALESPOINT_URL
            resp['auth_token'] = settings.VIP_SALESPOINT_AUTHTOKEN
            resp['request_data'] = PlusIntegration.get_docprime_data(data)


        return resp

    @classmethod
    def get_docprime_data(self, data):
        request_data = { "IPDHospital": "",
                            "IsInsured": None,
                            "PolicyLink": "",
                            "InsurancePolicyNumber": None,
                            "AppointmentStatus": None,
                            "Age": None,
                            "Email": data.get('email', ""),
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
                            "PatientName": data.get('name', ""),
                            "PatientAddress": data.get('address', ""),
                            "ProviderName": "",
                            "ServiceID": data.get('plan_id', None),
                            "ServiceName": data.get('plan_name', ""),
                            "InsuranceCover": 0,
                            "BookingUrl": "",
                            "Fees": None,
                            "EffectivePrice": None,
                            "MRP": None,
                            "DealPrice": None,
                            "DOB": data.get('dob', ""),
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
                            "Name": data.get('name', ""),
                            "PrimaryNo": str(data.get('phone_number', None)),
                            "LeadSource": "DocPrime",
                            "EmailId": "",
                            "Gender": None,
                            "CityId": 0,
                            "ProductId": 5,
                            "SubProductId": None,
                            "UtmTerm": "ADRM5",
                            "UtmMedium": "ADRM5",
                            "UtmCampaign": "ADRM5",
                            "UtmSource": data.get('utm_source', None),
                            "PlanName": data.get('plan_name', ""),
                            "PlanID": data.get('plan_id', None)
                            }

        return request_data