import pika
import json
from celery.utils import uuid
from django.conf import settings


class Pika:
    def __init__(self, message, exchange, routing_key):
        self.message = message
        self.exchange = exchange
        self.routing_key = routing_key

    def basic_publish(self):
        credentials = pika.PlainCredentials(settings.RABBIT_MQ['USER'], settings.RABBIT_MQ['PASSWORD'])
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=settings.RABBIT_MQ['HOST'], port=settings.RABBIT_MQ['PORT'],
                                      credentials=credentials))
        channel = connection.channel()
        correlation_id = uuid()
        reply_to = uuid()
        message = self.message
        channel.basic_publish(
            exchange=self.exchange,
            routing_key=self.routing_key,
            body=json.dumps(message),
            properties=pika.BasicProperties(
                delivery_mode=2,
                reply_to=reply_to,
                correlation_id=correlation_id,
                priority=0,
                content_encoding='utf-8',
                content_type='application/json'
            ))
        connection.close()
        return correlation_id
