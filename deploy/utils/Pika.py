import pika
import json
from celery.utils import uuid
from assetv2.settingsapi import RABBIT_MQ, CELERY_ROUTES


class Pika():
    def __init__(self, task, args):
        self.task = task
        self.args = args

    def basic_publish(self):
        credentials = pika.PlainCredentials(RABBIT_MQ['USER'], RABBIT_MQ['PASSWORD'])
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_MQ['HOST'], port=RABBIT_MQ['PORT'], credentials=credentials))
        channel = connection.channel()
        correlation_id = uuid()
        reply_to = uuid()
        message = {
            "expires": None,
            "utc": True,
            "args": self.args,
            "chord": None,
            "callbacks": None,
            "errbacks": None,
            "taskset": None,
            "id": correlation_id,
            "retries": 0,
            "task": self.task,
            "timelimit": [None, None],
            "eta": None,
            "kwargs": {}}
        channel.basic_publish(
            exchange=CELERY_ROUTES[self.task]['queue'],
            routing_key=CELERY_ROUTES[self.task]['queue'],
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