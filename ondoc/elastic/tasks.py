from __future__ import absolute_import, unicode_literals
from django.core.files.uploadedfile import InMemoryUploadedFile

from celery import task
import logging
import datetime
import json
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

@task(bind=True, max_retries=2)
def fetch_and_upload_json(self, data):

    try:
        obj_id = data.get('id', None)
        obj = elastic_models.DemoElastic.objects.filter(id=obj_id).first()
        if obj and obj.mongo_connection_string.strip():
            mongo_client = MongoClient(obj.mongo_connection_string.strip())
            db = mongo_client.__getattr__(obj.mongo_database.strip())
            collection = db.__getattr__(obj.mongo_collection.strip())
            if db and collection:
                query = obj.query.strip()
                if not query:
                    raise ValueError('Query is empty or invalid.')

                def default(obj):
                    if isinstance(obj, Decimal):
                        return str(obj)
                    raise TypeError("Object of type '%s' is not JSON serializable" % type(obj).__name__)

                # new_file_name = str(slugify('%s' % str(obj.created_at)))
                # new_file_name = 'demoelastic/%s.json' % new_file_name

                # f = default_storage.open(new_file_name, 'wb')
                # f.write('['.encode())
                # f.close()

                # file = TemporaryUploadedFile(new_file_name, 'byte', 66666, 'utf-8')
                # file.write('['.encode())
                batch_size = 50000
                with transaction.atomic():

                    with connection.connection.cursor(name='elasticdata', cursor_factory=psycopg2.extras.RealDictCursor) as cursor:
                        cursor.itersize = batch_size
                        cursor.execute(query)
                        counter = 0
                        response_list = list()
                        for row in cursor:
                            response_list.append(row)
                            if len(response_list) >= batch_size:
                                response_list = json.loads(json.dumps(response_list, default=default))
                                result = collection.insert_many(response_list, ordered=False)
                                print('Successfully uploaded the chunk of ', len(result.inserted_ids))
                                # file = default_storage.open(new_file_name, 'ab')
                                # content = json.dumps(response_list, default=default).encode()
                                # if not counter == 0:
                                    # file.write(','.encode())

                                # file.write(content[1:len(content)-1])
                                # file.close()

                                response_list = list()
                                counter+=1
                                #print(str(counter))

                        # write all remaining records
                        if len(response_list) > 0:
                            response_list = json.loads(json.dumps(response_list, default=default))
                            result = collection.insert_many(response_list, ordered=False)
                            print('Successfully uploaded the chunk of ', len(result.inserted_ids))
                                # content = json.dumps(response_list, default=default).encode()

                                # file = default_storage.open(new_file_name, 'ab')
                                # if not counter == 0:
                                    # file.write(','.encode())

                                # file.write(content[1:len(content)-1])
                                # file.close()


                # file = default_storage.open(new_file_name, 'ab')
                # file.write(']'.encode())

                # file.seek(0)
                # file.flush()
                # obj.file = file
                # obj.save()
                # print(file.temporary_file_path())
                #
                # file.close()
                print("Sync to mongo successfull.")

    except Exception as e:
        print("Error in Celery. Failed to upload to mongo.")
        logger.error("Error in Celery. Failed creating json and uploading S3 - " + str(e))
