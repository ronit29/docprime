from ondoc.location.models import GoogleSearchEntry, GoogleSearches, GoogleResult
import requests
from django.conf import settings
from rest_framework import status
from django.db import transaction


class SearchedDoctorData():

    @staticmethod
    def find_doctor_data():
        pincodes = [ '110092', '110051', '110032', '110090', '110053', '110091', '110094', '110095', '110031',
                     '110096', '110093', '110006', '110033', '110036', '110034', '110054', '110052', '110039', '110085',
                     '110042', '110040', '110086', '110084', '110007', '110081', '110009', '110035', '110088', '110082',
                     '110083', '110056', '110089', '110002', '110055', '110005', '110001', '110008', '110003', '110012',
                     '110011', '110060', '110004', '110069', '110025', '110062', '110019', '110076', '110024', '110049',
                     '110044', '110020', '110013', '110017', '110065', '110048', '110014', '110080', '110010', '110038',
                     '110021', '110029', '110047', '110061', '110074', '110030', '110016', '110037', '110068', '110067',
                     '110097', '110023', '110070', '110066', '110022', '110057', '110075', '110018', '110026', '110071',
                     '110077', '110041', '110043', '110072', '110059', '110058', '110045', '110015', '110073', '110078',
                     '110064', '110027', '110063', '110087', '110028', '110046', '122104', '122005', '122107', '122001',
                     '122508', '122101', '122105', '122006', '122503', '122108', '122505', '122103', '122102', '122413',
                     '122017', '122002', '122502', '122102', '122008', '122010', '122002', '122016', '123106', '122506',
                     '122101', '122104', '122009', '122505', '122001', '122003', '122011', '122018', '122003', '122504',
                     '122052', '122414', '122016', '122007', '122504', '123401', '122051', '122502', '122004', '122506',
                     '122108', '122414', '122004', '122051', '122107', '122015', '122017', '122503', '122508', '122006',
                     '122015', '122103', '122105', '201313', '201304', '201008', '201306', '201314', '201307', '201311',
                     '203207', '201312', '201310', '201309', '201305', '201301', '201303', '201307', '201008']

        for pincode in pincodes:
            search_keywords = 'Doctors in ' + pincode
            print(search_keywords + ' ' + SearchedDoctorData.searched_google_data(search_keywords))
        return 'success'

    @staticmethod
    def run_google_search(search_keywords, next_token):
        params = {'query': search_keywords, 'key': settings.REVERSE_GEOCODING_API_KEY}
        results = {}
        if next_token:
            params['next_token'] = next_token

        response = requests.get(
                'https://maps.googleapis.com/maps/api/place/textsearch/json',
                params=params)

        if response.status_code != status.HTTP_200_OK or not response.ok:
            print('failure  status_code: ' + str(response.status_code) + ', reason: ' + str(response.reason))
            return results

        searched_data = response.json()
        google_result = []

        if isinstance(searched_data.get('results'), list) and \
                len(searched_data.get('results')) == 0:
            return searched_data.get('status')

        if searched_data.get('results'):
            for data in searched_data.get('results'):
                google_result.append(data)
            results['data'] = google_result
            results['count'] = len(google_result)

        if searched_data.get('next_page_token'):
            results['next_page_token'] = searched_data.get('next_page_token')

        return results

    @staticmethod
    def create_place_data(data, google_data, place_id):
        params = {'place_id': place_id, 'key': settings.REVERSE_GEOCODING_API_KEY}
        place_response = requests.get('https://maps.googleapis.com/maps/api/place/details/json',
                                      params=params)
        if place_response.status_code != status.HTTP_200_OK or not place_response.ok:
            return 'failure  status_code: ' + str(place_response.status_code) + ', reason: ' + str(
                place_response.reason)

        place_searched_data = place_response.json()
        if place_searched_data.get('status') == 'OVER_QUERY_LIMIT':
            return 'OVER_QUERY_LIMIT'

        doctor_details = dict()
        doctor_details['name'] = data.get('name') if data.get('name') else None
        if place_searched_data.get('result'):
            place_searched_data = place_searched_data.get('result')
            doctor_details['address'] = place_searched_data.get('formatted_address')
            doctor_details['phone_number'] = place_searched_data.get('formatted_phone_number')
            doctor_details['website'] = place_searched_data.get('website')
            if place_searched_data.get('address_components'):
                address_components = place_searched_data.get('address_components')
                for address in address_components:
                    types = [key.upper() for key in address.get('types', [])]
                    if 'LOCALITY' in types:
                        doctor_details['city'] = address.get('long_name')
                    if 'POSTAL_CODE' in types:
                        doctor_details['pin_code'] = address.get('long_name')

        create_place_entry = GoogleSearchEntry.objects.create(place_id=place_id,
                                                                      place_result=place_searched_data,
                                                                      doctor_details=doctor_details)
        create_google_result = GoogleResult.objects.create(place_entry=create_place_entry,
                                                           search_results=google_data)
        return "% success" %place_id

    @staticmethod
    def searched_google_data(search_keywords):
        google_data = GoogleSearches.objects.filter(search_keywords=search_keywords).first()
        count = 0
        page = 1
        next_page_token = None
        search_results = []

        if not google_data:
            while next_page_token or page==1:
                page += 1
                result = SearchedDoctorData.run_google_search(search_keywords, next_page_token)
                next_page_token = result.get('next_page_token')
                if result.get('count'):
                    count += result.get('count')
                if result.get('data') and len(result.get('data'))>0:
                    search_results.append(result.get('data'))
            google_data = GoogleSearches.objects.create(search_keywords=search_keywords,
                                                                        results=search_results, count=count)
            if google_data:
                id = google_data.id
                results = google_data.results
                for data in results:
                    place_id = data.get('place_id')
                    if place_id:
                        google_result_obj = GoogleResult.objects.filter(place_entry_id__place_id=place_id).first()
                        google_place_entry_obj = GoogleSearchEntry.objects.filter(place_id=place_id).first()
                        if google_result_obj and google_place_entry_obj:
                            GoogleResult.objects.create(place_entry_id=google_result_obj.place_entry_id,
                                                        search_results_id=id)
                        else:
                            print(SearchedDoctorData.create_place_data(data, google_data, place_id))
        return "success"







        #
        # if create_google_search_record:
        #     id = create_google_search_record.id
        #     results = create_google_search_record.results
        #     place_entry_list = list()
        #     for data in results:
        #         place_id = data.get('place_id')
        #         if place_id:
        #             google_result_obj = GoogleResult.objects.filter(place_entry_id__place_id=place_id).first()
        #             if google_result_obj:
        #                 GoogleResult.objects.create(place_entry_id=google_result_obj.place_entry_id,
        #                                             search_results_id=id)
        #             else:
        #
        #                 place_response = requests.get('https://maps.googleapis.com/maps/api/place/details/json',
        #                                   params={'place_id': place_id, 'key': settings.REVERSE_GEOCODING_API_KEY})
        #                 if place_response.status_code != status.HTTP_200_OK or not response.ok:
        #                     return 'failure  status_code: ' + str(response.status_code) + ', reason: ' + str(
        #                         response.reason)
        #                 else:
        #                     place_searched_data = place_response.json()
        #                     if place_searched_data.get('status') == 'OVER_QUERY_LIMIT':
        #                         create_google_search_record.delete()
        #                         return 'OVER_QUERY_LIMIT'
        #
        #                     doctor_details = dict()
        #                     doctor_details['name'] = data.get('name')
        #                     if place_searched_data.get('result'):
        #                         place_searched_data = place_searched_data.get('result')
        #                         doctor_details['address'] = place_searched_data.get('formatted_address')
        #                         doctor_details['phone_number'] = place_searched_data.get('formatted_phone_number')
        #                         doctor_details['website'] = place_searched_data.get('website')
        #                         if place_searched_data.get('address_components'):
        #                             address_components = place_searched_data.get('address_components')
        #                             for address in address_components:
        #                                 types = [key.upper() for key in address.get('types', [])]
        #                                 if 'LOCALITY' in types:
        #                                     doctor_details['city'] = address.get('long_name')
        #                                 if 'POSTAL_CODE' in types:
        #                                     doctor_details['pin_code'] = address.get('long_name')
        #                     # searched_result.append(doctor_details)
        #                     place_entry_list.append({'place_id':place_id,
        #                                             'place_result':place_searched_data,
        #                                             'doctor_details':doctor_details})
        #     with transaction.atomic():
        #         for place in place_entry_list:
        #             create_google_search_entry = GoogleSearchEntry.objects.create(place_id=place.get('place_id'),
        #                                          place_result=place.get('place_result'), doctor_details=place.get('doctor_details'))
        #             create_google_result = GoogleResult.objects.create(place_entry=create_google_search_entry,
        #                                                                            search_results=create_google_search_record)
        #
        #
        # return 'success