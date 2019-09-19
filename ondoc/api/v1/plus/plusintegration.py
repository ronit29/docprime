import operator
from ondoc.plus.models import PlusUser, PlusMembers, PlusPlans
from django.conf import settings


class PlusIntegration:

    def get_response(self, data):
        resp = {}
        utm_source = data.get('utm_source', None)
        plus_plan = PlusPlans.objects.filter(is_live=True, utm_source__containing=utm_source).first()
        if not utm_source or not plus_plan:
            return {}
        if utm_source == "docprime":
            resp['url'] = settings.VIP_SALESPOINT_URL
            resp['auth_token'] = settings.VIP_SALESPOINT_AUTHTOKEN
            resp['request_data'] = self.get_docprime_data(data)

        return resp

    def get_docprime_data(self, data):
        request_data = { "IPDHospital": "",
                            "IsInsured": None,
                            "PolicyLink": "",
                            "InsurancePolicyNumber": None,
                            "AppointmentStatus": None,
                            "Age": None,
                            "Email": "",
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
                            "PatientAddress": "",
                            "ProviderName": "",
                            "ServiceName": "",
                            "InsuranceCover": 0,
                            "BookingUrl": "",
                            "Fees": None,
                            "EffectivePrice": None,
                            "MRP": None,
                            "DealPrice": None,
                            "DOB": "",
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
                            "PrimaryNo": data.get('phone_number', None),
                            "LeadSource": "DocPrime",
                            "EmailId": "",
                            "Gender": None,
                            "CityId": 0,
                            "ProductId": 5,
                            "SubProductId": None,
                            "UtmTerm": "",
                            "UtmMedium": "",
                            "UtmCampaign": "",
                            "UtmSource": data.get('utm_source', None),
                            "PlanName": data.get('plan_name', "")
                            }

        return request_data