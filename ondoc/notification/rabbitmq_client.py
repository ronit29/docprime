import pika
from django.conf import settings


class RabbitmqConnection():

    def __init__(self):
        self.parameters = pika.URLParameters(
            settings.RABBITMQ_CONNECTION_SETTINGS["CONNECTION_URL"])

    def __enter__(self):
        self.connection = pika.BlockingConnection(self.parameters)
        return self.connection

    def __exit__(self, *args):
        self.connection.close()


def publish_message(body):

    with RabbitmqConnection() as connection:
        channel = connection.channel()
        channel.basic_publish(exchange='',
                              routing_key=settings.RABBITMQ_CONNECTION_SETTINGS["NOTIFICATION_QUEUE"],
                              body=body)
