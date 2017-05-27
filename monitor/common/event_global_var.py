# -*- coding: utf-8 -*-
# global var
# written by zhangyunyang
#
from monitor.models import EventSourceMap
from monitor.models import EventTypeMap
from monitor.models import EventLevelMap
from cmdb.models import App
from cmdb.models import DdUsers

# declare global var
g_source_map = {}
g_type_map = {}
g_level_map = {}
g_app_map = {}
g_alarm_method = {1: "Email", 2: "SMS", 3: "Voice", 4: "TTS"}

# define init method
def init_source_map():
    source_res = EventSourceMap.objects.all()
    for i in source_res:
        g_source_map.setdefault(i.id, i.name)


def init_type_map():
    type_res = EventTypeMap.objects.all()
    for i in type_res:
        g_type_map.setdefault(i.id, i.name)


def init_level_map():
    level_res = EventLevelMap.objects.all()
    for i in level_res:
        g_level_map.setdefault(i.id, i.name)


# call init method
init_source_map()
init_type_map()
init_level_map()


# get source info
def get_source_info(source_id):
    try:
        source_name = g_source_map.get(source_id, '')
    except ValueError:
        source_name = ''

    return source_name


# get type info
def get_type_info(type_id):
    try:
        type_name = g_type_map.get(type_id, '')
    except ValueError:
        type_name = ''

    return type_name


# get level info
def get_level_info(level_id):
    try:
        level_name = g_level_map.get(level_id, '')
    except ValueError:
        level_name = ''

    return level_name


# get and update app info
# check cache first, then from db if failed
def update_app_info(app_id_list):
    # 去重
    app_id_list = list(set(app_id_list))
    app_id_list_tmp = []

    for app_id in app_id_list:
        try:
            if app_id == 0:
                continue
        except ValueError:
            pass

        if not g_app_map.has_key(app_id):
            app_id_list_tmp.append(app_id)

    if app_id_list_tmp:
        try:
            app_res = App.objects.filter(status=0, id__in=app_id_list_tmp)
        except ValueError:
            return

        for one in app_res:
            # update
            g_app_map.setdefault(one.id, [one.site.name, one.name])


# get app info
def get_app_info(app_id):
    app_info = g_app_map.get(app_id, [])
    return app_info


def get_event_status_name(status_id):
    if status_id == 0:
        status_name = ""
    elif status_id == 1:
        status_name = "手动"
    elif status_id == 2:
        status_name = "自动"
    else:
        status_name = "unkown"

    return status_name


def get_alarm_method_name(method_id):
    name = g_alarm_method.get(method_id, 'unkown')
    return name


def get_alarm_receiver_name(method_id, receiver):
    if method_id == 2:
        receiver_origin = receiver
        receiver_list = receiver_origin.split(',')

        for i in range(len(receiver_list)):
            phone = receiver_list[i].strip()
            try:
                name = DdUsers.objects.get(telephone=phone).username
            except Exception:
                name = phone
            receiver_list[i] = name
        return ",".join(receiver_list)
    else:
        return receiver
