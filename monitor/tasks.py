# -*- coding: utf-8 -*-
from __future__ import absolute_import
from monitor.process.process import process_notification
import multiprocessing
import time
import os
import json
import threading
import Queue as Q

from celery import shared_task

from monitor.process.process import process_notification
# import monitor.AI.section.basement as basement


@shared_task()
def run_notification(jsonj):
    process_notification(jsonj)


# # lock = multiprocessing.Lock()
# pool_instance = {}
# instance_config = {
#     'basement': {'func': basement.process_convergence, 'interval': 60},  # sec
#
# }
#
#
# @shared_task()
# def run_convergence(jsonj):
#     json_data = json.loads(jsonj)
#
#     if not pool_instance:
#         # print 'create instance...'
#         for i in instance_config:
#             func = instance_config[i]['func']
#             queue = Q.Queue()
#             instance = threading.Thread(target=func, args=(queue, instance_config[i]))
#             instance.start()
#             pool_instance[i] = {'config': instance_config[i], 'queue': queue, 'instance': instance}
#
#     # print 'father pid: ' + str(os.getpid())
#     # print 'put msg...'
#     for i in pool_instance:
#         pool_instance[i]['queue'].put(json_data)
#
#     # if not pool_instance:
#     #     print 'create instance...'
#     #     for i in instance_config:
#     #         func = instance_config[i]['func']
#     #         queue = multiprocessing.Queue()
#     #         instance = multiprocessing.Process(target=func, args=(queue, instance_config[i]))
#     #         instance.start()
#     #         pool_instance[i] = {'config': instance_config[i], 'queue': queue, 'instance': instance}
#     #
#     # print 'father pid: ' + str(os.getpid())
#     # print 'put msg...'
#     # for i in pool_instance:
#     #     pool_instance[i]['queue'].put(json_data)


