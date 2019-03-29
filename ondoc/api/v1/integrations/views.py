from rest_framework.response import Response
from rest_framework import viewsets, status
from ondoc.integrations.models import IntegratorResponse, IntegratorReport
import requests
import xmltodict
import json
import logging

logger = logging.getLogger(__name__)


class IntegratorReportViewSet(viewsets.GenericViewSet):
    def report(self, request):
        booking_id = request.query_params.get('booking_id', None)

        if not booking_id:
            return Response({"error": "Missing Parameter: booking_id"}, status=status.HTTP_400_BAD_REQUEST)

        integrator_response = IntegratorResponse.objects.filter(object_id=booking_id).first()
        if not integrator_response:
            return Response({"error": "Thyrocare Report not found for booking"}, status=status.HTTP_404_NOT_FOUND)

        # report = IntegratorReport.objects.filter(integrator_response_id=integrator_response.id).first()
        # if not report:
        #     return Response({"error": "Thyrocare Report not found for booking"}, status=status.HTTP_404_NOT_FOUND)

        # report_url = report.xml_url
        report_url = 'https://www.thyrocare.com/apis/ReportAccess.aspx?id=C/0dHN6TXsHQgg0Cu0HS7A==,gATDluZRCNL9f8vQX61wSw==,+kssQUPGdmE='

        data = requests.get(report_url)
        xml_content = data.content
        json_content = json.loads(json.dumps(xmltodict.parse(xml_content)))

        lead_details = json_content['ThyrocareResult']['DATES']['DATE']['ORDERS']['ORDERNO']['LEADS']['LEADDETAILS']
        red = list()
        white = list()
        if type(lead_details) is dict:
        if lead_details:
            # patient_detail = dict()
            for lead_detail in lead_details:
                test_results = lead_detail['BARCODES']['BARCODE']['TESTRESULTS']['TESTDETAIL']
                if test_results:
                    # patient_detail[i]['PATIENT_NAME'] = lead_detail['PATIENT']
                    # patient_detail[i]['MOBILE'] = lead_detail['MOBILE']
                    # patient_detail[i]['EMAIL'] = lead_detail['EMAIL']
                    # patient_detail[i]['LEADID'] = lead_detail['LEADID']
                    # patient_detail[i]['TESTS'] = lead_detail['TESTS']
                    # patient_detail[i]['red'] = list()
                    for result in test_results:
                        test_detail = {'REPORT_GROUP_ID': result['REPORT_GROUP_ID'], 'R3': result['R3'], 'UNITS': result['UNITS'],
                                       'REPORT_PRINT_ORDER': result['REPORT_PRINT_ORDER'], 'NORMAL_VAL': result['NORMAL_VAL'],
                                       'Description': result['Description'], 'TEST_CODE': result['TEST_CODE'], 'PROFILE_CODE': result['PROFILE_CODE'],
                                       'SDATE': result['SDATE'], 'TEST_VALUE': result['TEST_VALUE']}
                        if result['INDICATOR'] == 'RED':
                            red.append(test_detail)
                        elif result['INDICATOR'] == 'WHITE':
                            white.append(test_detail)
                        else:
                            pass

        # return Response(lead_details)
        return Response({"RED": red, "WHITE": white})



