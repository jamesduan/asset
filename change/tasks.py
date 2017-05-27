# -*- coding: utf-8 -*-
'''
    @description:   消息队列生产者/消费者方法

    @copyright:     ©2015 yihaodian.com
    @author:        jackie
    @since:         15-03-02
    @version:       1.0
'''
from __future__ import absolute_import
import uuid, logging
import time
from celery import shared_task
import json
from change.models import *
from cmdb.models import App

@shared_task()
def collect(data):
    default_change_data = {
        'type':  'undefined',
        'action': 'undefined',
        'index': 'undefined',
        'level': 'info',
        'message': '',
        'happen_time': '1970-01-01 00:00:00',
        'user': 'undefined',
        'app_id': 0,
    }
    format_data = dict(default_change_data, **data)
    format_data['task_id'] = uuid.uuid4()
    format_data['created'] = time.strftime("%Y-%m-%d %X", time.localtime())

    # 检查action和type的合法性
    input_type = format_data['type']
    input_action = format_data['action']

    try:
        logging.info("checking type('{type}') is exists.".format(type=input_type))
        fetched_type = Type.objects.using('change').get(key=input_type)
    except Type.DoesNotExist as e:
        logging.warn("task.collect() fetched type does not exists!")
        fetched_type = None

    app, fetched_action = (None, None)
    if fetched_type:
        try:
            logging.info("checking type('{type}')->action('{action}') is exists.".format(
                                                action=input_action,
                                                type=fetched_type.key))
            fetched_action = Action.objects.using('change')\
                                           .get(key=input_action, 
                                                type_id=fetched_type.id)
            app_id = format_data['app_id']
            logging.info("checking app_id('{app_id}')".format(app_id=app_id))
            app = App.objects.get(id=int(app_id))
            result = Main.objects.using('change').create(
                task_id=uuid.uuid4(),
                type=input_type,
                action=input_action,
                action_id=fetched_action.id,
                index=format_data['index'],
                level=format_data['level'],
                message=format_data['message'],
                happen_time=format_data['happen_time'],
                created=time.strftime("%Y-%m-%d %X", time.localtime()),
                user=format_data['user'],
                app = app)
            return 'success'
        except Action.DoesNotExist as e:
            logging.warn('task.collect() fetched action does not exists!')
            return "None"
        except App.DoesNotExist as e:
            logging.warn(str(e) + ' task.collect() app does not exists!')
            result = Main.objects.using('change').create(
                task_id=uuid.uuid4(),
                type=input_type,
                action=input_action,
                action_id=fetched_action.id,
                index=format_data['index'],
                level=format_data['level'],
                message=format_data['message'],
                happen_time=format_data['happen_time'],
                created=time.strftime("%Y-%m-%d %X", time.localtime()),
                user=format_data['user'],
                app = app)
            return "success"
        except Exception, e:
            logging.error("server error: " + str(e))
            return "None"
    else:
        return "None"