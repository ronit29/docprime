from __future__ import absolute_import, unicode_literals
from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import InMemoryUploadedFile
import requests
from celery import task
import logging
import uuid
import datetime
import json
from rest_framework import status
from ondoc.api.v1.utils import RawSql
from io import StringIO, BytesIO
from ondoc.elastic import models as elastic_models
logger = logging.getLogger(__name__)
from django.core.files.uploadedfile import TemporaryUploadedFile
from django.template.defaultfilters import slugify
from django.core.files.storage import default_storage
import os
from django.db import connection, transaction
import psycopg2
from decimal import Decimal
from django.conf import settings
from pymongo import MongoClient

def dump_to_elastic():

    try:
        obj = elastic_models.DemoElastic.objects.all().order_by('id').last()
        if not obj:
            raise Exception('Could not elastic object.')

        headers = {
            'Content-Type': 'application/json',
        }

        elastic_url = settings.ES_URL
        elastic_alias = settings.ES_ALIAS
        primary_index = settings.ES_PRIMARY_INDEX
        secondary_index_a = settings.ES_SECONDARY_INDEX_A
        secondary_index_b = settings.ES_SECONDARY_INDEX_B
        primary_index_mapping_data = settings.ES_PRIMARY_INDEX_MAPPING_DATA
        secondary_index_mapping_data = settings.ES_SECONDARY_INDEX_MAPPING_DATA

        params = (
            ('format', 'json'),
        )

        # Fetch currently used index.
        response = requests.get(elastic_url + '/_cat/aliases/' + elastic_alias, params=params)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            raise Exception('Could not get current index.')

        response = response.json()
        if not response:
            raise Exception('Invalid Response received while fetching current index.')

        currently_used_index = response[0].get('index')

        # Decide which index to use for dumping the data to elastic.
        if secondary_index_a == currently_used_index:
            original = secondary_index_a
            destination = secondary_index_b
        else:
            original = secondary_index_b
            destination = secondary_index_a

        # Delete the primary index.
        response = requests.delete(elastic_url + '/' + primary_index, headers=headers)
        if response.status_code != status.HTTP_200_OK or not response.ok:
            pass
            # raise Exception('Could not delete the primary index.')

        # Delete the index or empty the index for new use.
        deleteResponse = requests.delete(elastic_url + '/' + destination)

        if deleteResponse.status_code != status.HTTP_200_OK or not deleteResponse.ok:
            # raise Exception('Could not delete the destination index.')
            pass

        # create the primary index for dumping the data.
        createIndex = requests.put(elastic_url + '/' + primary_index, headers=headers, data=json.dumps(primary_index_mapping_data))
        if createIndex.status_code != status.HTTP_200_OK or not createIndex.ok:
            raise Exception('Could not create the primary index.')

        query = obj.query.strip()
        if not query:
            raise ValueError('Query is empty or invalid.')

        def default(obj):
            if isinstance(obj, Decimal):
                return str(obj)
            raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

        batch_size = 10000
        with transaction.atomic():
            with connection.connection.cursor(name='elasticdata', cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                cursor.itersize = batch_size
                cursor.execute(query)
                counter = 0
                response_list = list()
                for row in cursor:
                    document_dict = {
                        "_index": primary_index,
                        "_type": "entity",
                        "_id": str(uuid.uuid4())
                    }
                    response_list.append({'index': document_dict})
                    response_list.append(row)
                    if len(response_list) >= batch_size:
                        response_list = json.loads(json.dumps(response_list, default=default))
                        requests.post(elastic_url + '_bulk', headers=headers, data=json.dumps(response_list))

                        count_response = requests.get(elastic_url + '/' + primary_index + '/_count')
                        if count_response.status_code != status.HTTP_200_OK or not count_response.ok:
                            raise Exception('Could not get the count of dumped documents.')

                        count_response = count_response.json()

                        if count_response.get('count') != batch_size:
                            logger.error('Could not dump all the records. Attempeted %d : Dumped %s' % (batch_size, count_response))

                        response_list = list()
                        counter+=1

                # write all remaining records
                if len(response_list) > 0:
                    response_list = json.loads(json.dumps(response_list, default=default))
                    data = '\n'.join(json.dumps(d) for d in response_list) + '\n'
                    headers = {"Content-Type": "application/x-ndjson"}
                    dump_response = requests.post(elastic_url + '/_bulk', headers=headers, data=data)
                    if dump_response.status_code != status.HTTP_200_OK or not dump_response.ok:
                        raise Exception('Dump unsuccessfull')

                    count_response = requests.get(elastic_url + '/' + primary_index + '/_count')
                    if count_response.status_code != status.HTTP_200_OK or not count_response.ok:
                        raise Exception('Could not get the count of dumped documents.')

                    count_response = count_response.json()

                    if count_response.get('count') != int(len(response_list)/2):
                        raise Exception('Could not dump all the records. Attempeted %d : Dumped %s' % (batch_size, count_response))

        data = {"source":{"index":primary_index},"dest":{"index":destination}}
        response = requests.post(elastic_url + '/_reindex', headers={'Content-Type': 'application/json'}, data=json.dumps(data))

        aliasData = {
            "actions": [
                {
                    "remove": {
                        "indices": [original],
                        "alias": elastic_alias
                    }
                },
                {
                    "add": {"indices": [destination], "alias": elastic_alias}
                }
            ]
        }

        response = requests.post(elastic_url + '/_aliases', headers={'Content-Type': 'application/json'}, data=json.dumps(aliasData))

        print("Sync to elastic successfull.")

    except Exception as e:
        logger.error("Error in syncing process of elastic - " + str(e))


class Command(BaseCommand):

    def handle(self, **options):
        dump_to_elastic()
