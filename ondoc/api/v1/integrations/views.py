import re

from rest_framework.response import Response
from rest_framework import viewsets, status
from ondoc.integrations.models import IntegratorResponse, IntegratorReport, IntegratorTestParameterMapping
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

        report_url = report.xml_url
        pdf_url = report.pdf_url

        if report.json_data:
            return Response({'pdf_report_url': pdf_url, 'data': report.json_data})
        else:
            if not report_url:
                return Response({"error": "Thyrocare Report url not found for booking"}, status=status.HTTP_404_NOT_FOUND)

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

            report.json_data = data
            report.save()
            return Response({'pdf_report_url': pdf_url, 'data': data})

    def get_test_result_data(self, lead_detail, test_results):
        separated_details = self.get_name_age_gender(lead_detail['PATIENT'])

        patient_detail = {'NAME': separated_details['name'], 'AGE': separated_details['age'],
                          'GENDER': separated_details['gender'],
                          'MOBILE': lead_detail['MOBILE'], 'EMAIL': lead_detail['EMAIL'],
                          'LEADID': lead_detail['LEADID'], 'TESTS': lead_detail['TESTS']}
        red = list()
        white = list()

        if type(test_results) is dict:
            min_max_value = self.get_min_max_value(test_results['NORMAL_VAL'])
            test_detail = {'REPORT_GROUP_ID': test_results['REPORT_GROUP_ID'], 'R3': test_results['R3'], 'UNITS': test_results['UNITS'],
                           'REPORT_PRINT_ORDER': test_results['REPORT_PRINT_ORDER'], 'MIN': min_max_value['min_val'], 'MAX': min_max_value['max_val'],
                           'Description': test_results['Description'], 'TEST_CODE': test_results['TEST_CODE'],
                           'PROFILE_CODE': test_results['PROFILE_CODE'],
                           'SDATE': test_results['SDATE'], 'TEST_VALUE': test_results['TEST_VALUE']}

            inte_test_parameter = IntegratorTestParameterMapping.objects.filter(integrator_test_name=test_results['Description']).first()
            if inte_test_parameter:
                test_detail['TEST_PARAMETER_ID'] = inte_test_parameter.test_parameter_chat.id
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
                min_max_value = self.get_min_max_value(result['NORMAL_VAL'])
                test_detail = {'REPORT_GROUP_ID': result['REPORT_GROUP_ID'], 'R3': result['R3'], 'UNITS': result['UNITS'],
                               'REPORT_PRINT_ORDER': result['REPORT_PRINT_ORDER'], 'MIN': min_max_value['min_val'], 'MAX': min_max_value['max_val'],
                               'Description': result['Description'], 'TEST_CODE': result['TEST_CODE'],
                               'PROFILE_CODE': result['PROFILE_CODE'],
                               'SDATE': result['SDATE'], 'TEST_VALUE': result['TEST_VALUE']}

                inte_test_parameter = IntegratorTestParameterMapping.objects.filter(integrator_test_name=result['Description']).first()

                if inte_test_parameter:
                    test_detail['TEST_PARAMETER_ID'] = inte_test_parameter.test_parameter_chat.id
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

    def get_name_age_gender(self, patient_name):
        name, age, gender = None, None, None
        if patient_name:
            p_name = patient_name.split('(')
            name = p_name[0]
            age = p_name[1].split('/')[0]
            gender = p_name[1].split('/')[1]
            gender = re.sub('\W+', '', gender)

        return {'name': name, 'age': age, 'gender': gender}

    def get_min_max_value(self, normal_value):
        if "-" in normal_value:
            min_val = normal_value.split('-')[0].strip()
            max_val = normal_value.split('-')[1].strip()
        elif "<" in normal_value:
            min_val = "-"
            max_val = normal_value.split('<')[1].strip()
        elif ">" in normal_value:
            min_val = normal_value.split('>')[1].strip()
            max_val = "-"
        else:
            min_val = None
            max_val = None

        return {'min_val': min_val, 'max_val': max_val}




