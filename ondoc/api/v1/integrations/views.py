from rest_framework.response import Response
from rest_framework import viewsets, status
from ondoc.integrations.models import IntegratorResponse, IntegratorReport, IntegratorTestParameter
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

        report = IntegratorReport.objects.filter(integrator_response_id=integrator_response.id).first()
        if not report:
            return Response({"error": "Thyrocare Report not found for booking"}, status=status.HTTP_404_NOT_FOUND)

        # report_url = report.xml_url
        report_url = 'https://www.thyrocare.com/apis/ReportAccess.aspx?id=C/0dHN6TXsHQgg0Cu0HS7A==' \
                     ',gATDluZRCNL9f8vQX61wSw==,+kssQUPGdmE='

        # report_url = 'https://www.thyrocare.com/apis/ReportAccess.aspx?id=9l012BpuOn46xL6XBUsjTQ==,ZBXkLSOGPPMc/ZGEx7yBhg==,+kssQUPGdmE='
        data = requests.get(report_url)
        xml_content = data.content
        json_content = json.loads(json.dumps(xmltodict.parse(xml_content)))

        lead_details = json_content['ThyrocareResult']['DATES']['DATE']['ORDERS']['ORDERNO']['LEADS']['LEADDETAILS']
        # red = list()
        # white = list()
        data = list()
        if type(lead_details) is dict:
            if lead_details:
                test_results = lead_details['BARCODES']['BARCODE']['TESTRESULTS']['TESTDETAIL']
                if test_results:
                    test_data = self.get_test_result_data(lead_details, test_results)
                    data.append(test_data)
        elif type(lead_details) is list:
            if lead_details:
                for lead_detail in lead_details:
                    test_results = lead_detail['BARCODES']['BARCODE']['TESTRESULTS']['TESTDETAIL']
                    if test_results:
                        test_data = self.get_test_result_data(lead_detail, test_results)
                        data.append(test_data)

        return Response(data)

    def get_test_result_data(self, lead_detail, test_results):
        patient_detail = {'PATIENT_NAME': lead_detail['PATIENT'], 'MOBILE': lead_detail['MOBILE'], 'EMAIL': lead_detail['EMAIL'],
                          'LEADID': lead_detail['LEADID'], 'TESTS': lead_detail['TESTS']}
        red = list()
        white = list()

        if type(test_results) is dict:
            test_detail = {'REPORT_GROUP_ID': test_results['REPORT_GROUP_ID'], 'R3': test_results['R3'], 'UNITS': test_results['UNITS'],
                           'REPORT_PRINT_ORDER': test_results['REPORT_PRINT_ORDER'], 'NORMAL_VAL': test_results['NORMAL_VAL'],
                           'Description': test_results['Description'], 'TEST_CODE': test_results['TEST_CODE'],
                           'PROFILE_CODE': test_results['PROFILE_CODE'],
                           'SDATE': test_results['SDATE'], 'TEST_VALUE': test_results['TEST_VALUE']}

            inte_test_parameter = IntegratorTestParameter.objects.filter(integrator_test_name=test_results['Description']).first()
            if inte_test_parameter:
                test_detail['TEST_PARAMETER_ID'] = inte_test_parameter.test_parameter_new.id
                test_detail['INTEGRATOR_PARAMETER_ID'] = inte_test_parameter.id

            if test_results['INDICATOR'] == 'RED':
                red.append(test_detail)
            elif test_results['INDICATOR'] == 'WHITE':
                white.append(test_detail)
            else:
                pass
            patient_detail['RED'] = red
            patient_detail['WHITE'] = white
            return patient_detail
        elif type(test_results) is list:
            for result in test_results:
                test_detail = {'REPORT_GROUP_ID': result['REPORT_GROUP_ID'], 'R3': result['R3'], 'UNITS': result['UNITS'],
                               'REPORT_PRINT_ORDER': result['REPORT_PRINT_ORDER'], 'NORMAL_VAL': result['NORMAL_VAL'],
                               'Description': result['Description'], 'TEST_CODE': result['TEST_CODE'],
                               'PROFILE_CODE': result['PROFILE_CODE'],
                               'SDATE': result['SDATE'], 'TEST_VALUE': result['TEST_VALUE']}

                inte_test_parameter = IntegratorTestParameter.objects.filter(integrator_test_name=result['Description']).first()

                if inte_test_parameter:
                    test_detail['TEST_PARAMETER_ID'] = inte_test_parameter.test_parameter_new.id
                    test_detail['INTEGRATOR_PARAMETER_ID'] = inte_test_parameter.id

                if result['INDICATOR'] == 'RED':
                    red.append(test_detail)
                elif result['INDICATOR'] == 'WHITE':
                    white.append(test_detail)
                else:
                    pass
            patient_detail['RED'] = red
            patient_detail['WHITE'] = white
            return patient_detail


