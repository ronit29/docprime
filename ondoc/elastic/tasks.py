# from __future__ import absolute_import, unicode_literals
# from celery import task
# import requests
# import uuid
# import json
# from rest_framework import status
# from ondoc.elastic import models as elastic_models
# import logging
# logger = logging.getLogger(__name__)
# from django.db import connection, transaction
# import hashlib
# import psycopg2
# from decimal import Decimal
#
# @task()
# def dump_to_elastic():
#
#     try:
#         obj = elastic_models.DemoElastic.objects.all().order_by('id').last()
#         if not obj:
#             raise Exception('Could not elastic object.')
#
#         headers = {
#             'Content-Type': 'application/json',
#         }
#
#         elastic_url = obj.elastic_url
#         elastic_alias = obj.elastic_alias
#         primary_index = obj.primary_index
#         secondary_index_a = obj.secondary_index_a
#         secondary_index_b = obj.secondary_index_b
#         primary_index_mapping_data = obj.primary_index_mapping_data
#         secondary_index_mapping_data = obj.secondary_index_mapping_data
#
#         if not obj.active or not elastic_url or not elastic_alias or not primary_index or not secondary_index_a or not secondary_index_b \
#                 or not primary_index_mapping_data or not secondary_index_mapping_data:
#             raise Exception("Necessary vales of the elastic configuration is not set.")
#
#         params = (
#             ('format', 'json'),
#         )
#
#         # Fetch currently used index.
#         response = requests.get(elastic_url + '/_cat/aliases/' + elastic_alias, params=params)
#         if response.status_code != status.HTTP_200_OK or not response.ok:
#             raise Exception('Could not get current index.')
#
#         response = response.json()
#         if not response:
#             raise Exception('Invalid Response received while fetching current index.')
#
#         currently_used_index = response[0].get('index')
#         if not currently_used_index:
#             raise Exception('Invalid json received while fetching the index.')
#
#         # Decide which index to use for dumping the data to elastic.
#         if secondary_index_a == currently_used_index:
#             original = secondary_index_a
#             destination = secondary_index_b
#         else:
#             original = secondary_index_b
#             destination = secondary_index_a
#
#         # Delete the primary index.
#         response = requests.delete(elastic_url + '/' + primary_index, headers=headers)
#         if response.status_code != status.HTTP_200_OK or not response.ok:
#
#             if response.status_code == status.HTTP_404_NOT_FOUND and response.json().get('error', {}).get('type', "") == "index_not_found_exception".lower():
#                 pass
#             else:
#                 raise Exception('Could not delete the primary index.')
#
#         # create the primary index for dumping the data.
#         createIndex = requests.put(elastic_url + '/' + primary_index, headers=headers, data=json.dumps(primary_index_mapping_data))
#         if createIndex.status_code != status.HTTP_200_OK or not createIndex.ok:
#             raise Exception('Could not create the primary index.')
#
#         query = obj.query.strip()
#         if not query:
#             raise ValueError('Query is empty or invalid.')
#
#         def default(obj):
#             if isinstance(obj, Decimal):
#                 return str(obj)
#             raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)
#
#         batch_size = 10000
#         with transaction.atomic():
#             with connection.connection.cursor(name='elasticdata', cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
#                 cursor.itersize = batch_size
#                 cursor.execute(query)
#                 response_list = list()
#                 attempted = 0
#                 hashlib_obj = hashlib.sha1()
#                 for row in cursor:
#                     attempted = attempted + 1
#                     json_format_row = json.dumps(row) + row.get('name', uuid.uuid4())
#                     hashlib_obj.update(json_format_row.encode('utf-8'))
#
#                     document_dict = {
#                         "_index": primary_index,
#                         "_type": "entity",
#                         "_id": hashlib_obj.hexdigest()
#                     }
#
#                     response_list.append({'index': document_dict})
#                     response_list.append(row)
#                     if len(response_list) >= batch_size:
#                         response_list = json.loads(json.dumps(response_list, default=default))
#                         data = '\n'.join(json.dumps(d) for d in response_list) + '\n'
#                         dump_headers = {"Content-Type": "application/x-ndjson"}
#                         dump_response = requests.post(elastic_url + '/_bulk', headers=dump_headers, data=data)
#                         if dump_response.status_code != status.HTTP_200_OK or not dump_response.ok:
#                             raise Exception('Dump unsuccessfull')
#
#                         response_list = list()
#
#                 # write all remaining records
#                 if len(response_list) > 0:
#                     response_list = json.loads(json.dumps(response_list, default=default))
#                     data = '\n'.join(json.dumps(d) for d in response_list) + '\n'
#                     dump_headers = {"Content-Type": "application/x-ndjson"}
#                     dump_response = requests.post(elastic_url + '/_bulk', headers=dump_headers, data=data)
#                     if dump_response.status_code != status.HTTP_200_OK or not dump_response.ok:
#                         raise Exception('Dump unsuccessfull')
#
#         # Delete the index or empty the index for new use.
#         deleteResponse = requests.delete(elastic_url + '/' + destination)
#         if deleteResponse.status_code != status.HTTP_200_OK or not deleteResponse.ok:
#             if deleteResponse.status_code == status.HTTP_404_NOT_FOUND and deleteResponse.json().get('error', {}).get('type', "") == "index_not_found_exception".lower():
#                 pass
#             else:
#                 raise Exception('Could not delete the destination index.')
#
#         # create the destination index for dumping the data.
#         createDestinationIndex = requests.put(elastic_url + '/' + destination, headers=headers, data=json.dumps(secondary_index_mapping_data))
#         if createDestinationIndex.status_code != status.HTTP_200_OK or not createDestinationIndex.ok:
#             raise Exception('Could not create the destination index. ', destination)
#
#         data = {"source": {"index": primary_index}, "dest": {"index": destination}}
#         response = requests.post(elastic_url + '/_reindex', headers={'Content-Type': 'application/json'}, data=json.dumps(data))
#         if response.status_code != status.HTTP_200_OK or not response.ok:
#             raise Exception('Could not switch the ')
#
#         aliasData = {
#             "actions": [
#                 {
#                     "remove": {
#                         "indices": [original],
#                         "alias": elastic_alias
#                     }
#                 },
#                 {
#                     "add": {"indices": [destination], "alias": elastic_alias}
#                 }
#             ]
#         }
#
#         response = requests.post(elastic_url + '/_aliases', headers={'Content-Type': 'application/json'}, data=json.dumps(aliasData))
#         if response.status_code != status.HTTP_200_OK or not response.ok:
#             raise Exception('Could not switch the latest index to the live aliases. ', aliasData)
#
#         print("Sync to elastic successfull.")
#
#     except Exception as e:
#         logger.error("Error in syncing process of elastic - " + str(e))