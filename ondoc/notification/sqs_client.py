import boto3

from django.conf import settings


class SQSConnection():

    def __enter__(self):
        sqs = boto3.resource('sqs', region_name='ap-south-1',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

        self.queue = sqs.get_queue_by_name(QueueName=settings.NOTIFICATION_QUEUE)
        return self.queue


    # def __exit__(self, *args):
    #     self.connection.close()


def publish_message(body):

    # sqs = boto3.resource('sqs', region_name='ap-south-1',
    #     aws_access_key_id=settings.AWS_ACCESS_KEY_ID, aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY)

    sqs = boto3.resource('sqs')

    queue = sqs.get_queue_by_name(QueueName=settings.NOTIFICATION_QUEUE)

    queue.send_message(MessageBody=body)
