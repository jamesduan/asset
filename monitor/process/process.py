# -*- coding: utf-8 -*-
import json
import time
from rest_framework.exceptions import APIException
from django.db.models import Q
from django.template.loader import get_template
from django.template import Context
from output import NotificationOutPut
from shield import NotificationShield

from monitor.assemble.MQ import Pika
from monitor.utils import cleanhtml
from server.models import Server
from cmdb.models import App, Site, DdDomain
from monitor.models import *
from monitor.AI.section.mod_route import ModRoute
from monitor.process.event_judge import Judge
from monitor.process.output import check_phone, SendTTS
# from hardcode import hardcode_process
from assetv2.settingsmonitor import EVENT_CONFIRM_URL


class MyException(APIException):
    def __init__(self, detail="未定义", status_code=400):
        self.detail = detail
        self.status_code = status_code

mod_route_instance = ModRoute()
filter_instance = NotificationShield()
output = NotificationOutPut()

# amqp = Pika(task='monitor.tasks.run_convergence')


def process_notification(json_data, template=None):
    json_data = json.loads(json_data)
    pool_id = json_data.get('pool_id', 0)
    pool_name = json_data.get('pool_name', '')
    level_id = int(json_data.get('level_id', 500))
    level_adjustment_id = json_data.get('level_adjustment_id', 0)
    type_id = int(json_data.get('type_id', 0))
    source_id = int(json_data.get('source_id', 0))
    ip = json_data.get('ip', '')
    title = json_data.get('title', '')
    message = json_data.get('message', '')
    send_to = json_data.get('send_to', '')
    cc = json_data.get('cc', '')
    caller = json_data.get('caller', '')
    caller_message = json_data.get('caller_message', '')
    get_time = json_data.get('get_time', 0)
    cancel_user = json_data.get('cancel_user', '')
    sub_type = json_data.get('sub_type', 0)
    ignore = int(json_data.get('ignore', 0))  # 1-屏蔽默认发送 2-只屏蔽默认短信 3-邮件 4-voice
    is_tts = Judge.is_tts(json_data)

    # hardcode(硬编码的特殊逻辑处理 +_+)
    # res = hardcode_process(**{
    #     'ip': ip,
    #     'source_id': source_id,
    #     'message': message
    # })

    # 如果没有ip没有pool_id有pool_name,就根据pool_name来
    if(not ip) and (not pool_id) and pool_name:
        site_name, pool_name = pool_name.split('/')
        res = Site.objects.filter(name=site_name, status=0)
        if res:
            try:
                site_id = res[0].id
                res2 = App.objects.filter(site_id=site_id, name=pool_name, status=0)
                if res2:
                    pool_id = res2[0].id
            except MyException, e:
                raise e

    # filter
    result = filter_instance.filter(ip, message, source_id, type_id, level_id, pool_id)
    if result:
        status, is_alarm = 2, result[1]
    else:
        status, is_alarm = 0, 0


    detail_list = []
    pool_list = []
    if ip:
        ip_list = ip.split(',')
        servers = Server.objects.filter(ip__in=ip_list).exclude(server_status_id=400)

        app_map = {}
        switch_map = {}
        servers_map = {}
        if servers:
            app_ids = []
            parent_ips = []
            servers_map = {}
            for i in servers:
                app_ids.append(i.app_id)
                parent_ips.append(i.parent_ip)
                obj = {}
                obj['ip'] = i.ip
                obj['pool_id'] = i.app_id
                obj['server_type'] = i.server_type_id
                obj['parent_ip'] = i.parent_ip if i.parent_ip else ''
                servers_map[obj['ip']] = obj
                if i.app_id not in pool_list:
                    pool_list.append(i.app_id)

            apps = App.objects.filter(id__in=app_ids)

            if apps:
                for i in apps:
                    app_map[i.id] = i.site_id

            switch_servers = SwitchServer.objects.filter(server_ip__in=ip_list)
            if switch_servers:
                for i in switch_servers:
                    switch_map[i.server_ip] = i.switch_ip

        for i in ip_list:
            if i in servers_map:
                detail_list.append(servers_map[i])
            else:
                detail_list.append({
                    'ip': i,
                    'pool_id': 0,
                    'server_type': -1,
                    'parent_ip': ''
                })

        for i in detail_list:
            i['site_id'] = app_map[i['pool_id']] if app_map.has_key(i['pool_id']) else 0
            i['switch_ip'] = switch_map[i['ip']] if switch_map.has_key(i['ip']) else ''
    elif pool_id and pool_id != "0":
        if isinstance(pool_id, basestring):
            pool_list = pool_id.split(',')
        else:
            pool_list = [pool_id]

        apps = App.objects.filter(id__in=pool_list)
        app_map = {}
        if apps:
            for i in apps:
                app_map[i.id] = i.site_id
        for i in pool_list:
            if i:
                obj = {}
                obj['ip'] = ''
                obj['pool_id'] = int(i)
                obj['site_id'] = app_map[int(i)] if (int(i) in app_map) else 0
                obj['server_type'] = 0
                obj['parent_ip'] = ''
                obj['switch_ip'] = ''
                detail_list.append(obj)

    # 执行打标记模块
    tag = mod_route_instance.route_mod(**{
        'level_id': level_id,
        'type_id': type_id,
        'source_id': source_id,
        'title': title,
        'message': message,
        'send_to': send_to,
        'caller': caller,
        'create_time': int(time.time()),
        'detail_list': detail_list
    })

    try:
        # 收敛逻辑
        converge_id = 0
        converge_rule_id = 0
        max_interval = 60   # 最大收敛时间段

        # 应为level_id 规则配置里可以不填，所以先找是否有都符合的
        rules = EventConvergenceRule.objects.filter(
            source_id=source_id,
            type_id=type_id,
            level_id=level_id
        )
        if not rules:
            rules = EventConvergenceRule.objects.filter(
                source_id=source_id,
                type_id=type_id
            )

        rules_v2 = []
        if rules:
            for i in rules:
                weight = 0

                if (i.pool_id <= 0) or (i.pool_id and (len(pool_list) == 1) and (i.pool_id in pool_list)):
                    if (not i.key) or (i.key and (message.find(i.key) > -1)):
                        if i.pool_id <= 0:
                            weight -= 1
                        if not i.key:
                            weight -= 1
                        if i.same_ip == 0:
                            weight -= 1
                        rules_v2.append({'value': i, 'weight': weight})

        rules_last = None
        if rules_v2:
            max_weight = -100# 初始权重
            for i in rules_v2:
                if i['weight'] > max_weight:
                    max_weight = i['weight']
            for j in rules_v2:
                if j['weight'] == max_weight:
                    rules_last = j['value']
                    break

        if rules_last:
            def re_converge(my_res):
                _converge_id = 0
                _converge_rule_id = 0
                s = 0
                c = len(my_res)
                for _i in my_res:
                    the_converge_id = _i.converge_id
                    the_converge_rule_id = _i.converge_rule_id
                    if (the_converge_id == 0) and (the_converge_rule_id != 0):
                        _converge_id = _i.id
                        _converge_rule_id = _i.converge_rule_id
                        break
                    else:
                        s += 1
                if s == c:
                    _converge_rule_id = rules_last.id
                return _converge_id, _converge_rule_id

            interval = rules_last.interval

            now = int(time.time())
            start_time = now - interval * 60

            self_defined_filters = {
                'source_id': source_id,
                'type_id': type_id,
                'level_id': level_id,
                'create_time__gte': start_time
            }
            if rules_last.key:
                self_defined_filters['message__contains'] = rules_last.key

            res = Event.objects.filter(**self_defined_filters).order_by('-create_time')

            if res:
                event_details = {}
                res_ids = []
                for i in res:
                    res_ids.append(i.id)
                event_detail = EventDetail.objects.filter(event_id__in=res_ids)
                for item in event_detail:
                    event_details.setdefault(item.event_id, []).append(item)

                if rules_last.key and (rules_last.same_ip == 0):
                    converge_id, converge_rule_id = re_converge(res)
                elif (rules_last.same_ip == 1) and ip:
                    ip_list = ip.split(',')
                    need_id = []
                    for k, v in event_details.items():
                        tmp_c = 0
                        for j in v:
                            if j.ip in ip_list:
                                tmp_c += 1
                            else:
                                break
                        if tmp_c == len(ip_list):
                            need_id.append(k)
                    if rules_last.key:
                        converge_id, converge_rule_id = re_converge([i for i in res if i.id in need_id])
                    elif not rules_last.key:
                        tmp_message_id = []
                        for item in res:
                            if item.message == message:
                                tmp_message_id.append(item.id)
                        jiaoji = list(set(need_id).intersection(set(tmp_message_id)))
                        converge_id, converge_rule_id = re_converge([i for i in res if i.id in jiaoji])

                elif (not rules_last.key) and (rules_last.same_ip == 0):
                    tmp_message_id = []
                    for item in res:
                        if item.message == message:
                            tmp_message_id.append(item.id)
                    converge_id, converge_rule_id = re_converge([i for i in res if i.id in tmp_message_id])
            else:
                converge_rule_id = rules_last.id

        instance = EventCreate.objects.create(
            tag=tag.get('tag', ''),
            tag_remark=tag.get('remark', ''),
            level_id=level_id,
            level_adjustment_id=level_adjustment_id,
            type_id=type_id,
            source_id=source_id,
            title=title,
            status=status,
            message=message,
            send_to=send_to,
            cc=cc,
            caller=caller,
            caller_message=caller_message,
            cancel_user=cancel_user,
            converge_id=converge_id,
            converge_rule_id=converge_rule_id,
            create_time=int(time.time()),
            sub_type=sub_type,
            get_time=get_time,
            comment='',
            ignore=ignore
        )
        _id = instance.id
        title = instance.title
        message = instance.message
        send_to = instance.send_to
        caller = instance.caller
        pool_ids = []
        tmp = []
        if detail_list:
            for i in detail_list:
                if i['pool_id'] > 0:
                    pool_ids.append(i['pool_id'])
                i['event_id'] = _id
                tmp.append(EventDetailCreate(**i))
            EventDetailCreate.objects.bulk_create(tmp)

        # 去重
        pool_ids = list(set(pool_ids))

        # output 如果没有被收敛
        if not converge_id:
            level_res = EventLevelMap.objects.all()
            level_map = {}
            for i in level_res:
                level_map[i.id] = i.name

            pool_res = None
            pool_name = ''
            site_name = ''
            source_name = ''

            domain_name = ''
            domain_email = ''
            domain_leader = ''

            type_name = ''
            site_id = 0

            try:
                if (len(pool_list) > 0) and pool_list[0]:
                    pool_res = App.objects.filter(id=pool_list[0])
                if pool_res:
                    pool_name = pool_res[0].name
                    site_id = pool_res[0].site_id
                if site_id:
                    site_res = Site.objects.filter(id=site_id)
                    if site_res:
                        site_name = site_res[0].name
            except MyException, e:
                pass

            try:
                if source_id:
                    source_res = EventSourceMap.objects.filter(id=source_id)
                    if source_res:
                        source_name = source_res[0].name
                        source_domain_id = source_res[0].domain_id
                        if source_domain_id:
                            dddomain_res = DdDomain.objects.filter(id=source_domain_id, enable=0)
                            if dddomain_res:
                                domain_name = dddomain_res[0].domainname
                                domain_email = dddomain_res[0].domainemailgroup
                                domain_leader = dddomain_res[0].domainleaderaccount
            except MyException, e:
                pass

            try:
                if type_id:
                    type_res = EventTypeMap.objects.filter(id=type_id)
                    if type_res:
                        type_name = type_res[0].name
            except MyException, e:
                pass

            head = "等级:" + level_map[level_id]
            if pool_name:
                head += ", Pool:" + pool_name
            if ip:
                head += ", IP:" + ip
            if title:
                head += ", " + title + ":" + message
            if source_name:
                head += ", 来源:" + source_name
            message_yuanshi = cleanhtml(head)

            html_level = level_map[level_id]
            html_pool = (site_name + "/" + pool_name) if pool_name else ''
            html_ip = ip if ip else ''
            html_title = title if title else ''
            html_message = message
            html_source = source_name
            html_type = type_name
            html_source_msg = "Domain: "+domain_name+"("+domain_email+")"+"<br />Leader: "+domain_leader
            html_get_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(get_time))
            html_event_confirm_url = EVENT_CONFIRM_URL+'%d' % _id

            html_level_class = "level-normal"
            if level_id == 100:
                html_level_class = "level-critical"
            elif level_id == 200:
                html_level_class = "level-high"
            else:
                html_level_class = "level-normal"

            # if ("dingdan@yhd.com" in send_to) or ("panluyan@yhd.com" in send_to):
            t = get_template('mail/monitor/alert_template_new.html')
            # else:
            #     t = get_template('mail/monitor/alert_template.html')
            html_content = t.render(Context(locals()))
            if is_alarm != 1:  # 1是屏蔽
                if pool_ids:
                    p_id = pool_ids[0]
                    # for p_id in pool_ids:
                    result = output.send(level_id, p_id, _id, ignore, status, {
                        'caller': caller.split(',') if caller else [],
                        'sender_to': send_to.split(',') if send_to else [],
                        'cc': cc.split(',') if cc else [],
                        'subject': title,
                        'message': message,
                        'caller_message': caller_message,
                        'content': message_yuanshi,
                        'html_content': template if template else html_content,
                        'app_name': '-'
                    })
                else:
                    result = output.send(level_id, 0, _id, ignore, status, {
                        'caller': caller.split(',') if caller else [],
                        'sender_to': send_to.split(',') if send_to else [],
                        'cc': cc.split(',') if cc else [],
                        'subject': title,
                        'message': message,
                        'caller_message': caller_message,
                        'content': message_yuanshi,
                        'html_content': template if template else html_content,
                        'app_name': '-'
                    })

                if is_tts:
                    TTS_instance = SendTTS()
                    # if message.find('dinggo') > -1:
                    #     phone = '15800850671'
                    # else:
                    phone = Judge.get_today_BI_manager().get("MOBILE", 0)
                    ok_list, bad_list = check_phone([phone])
                    if ok_list:
                        for phone in ok_list:
                            res = Alarm.objects.create(
                                event_id=_id, method_id=4, result='', receiver=phone, create_time=int(time.time()))
                            tmp = {
                                'pid': res.id,
                                'receiver_list': phone,
                                'content': message,
                                'app_id': 0,
                                'app_name': '-'
                            }

                            result = TTS_instance.send(**tmp)

                    if bad_list:
                        status_id = 3
                        receiver_str = ','.join(bad_list)

                        Alarm.objects.create(
                            event_id=_id, method_id=4, result='', receiver=receiver_str, status_id=status_id, create_time=int(time.time()))

    except MyException, e:
        raise e
