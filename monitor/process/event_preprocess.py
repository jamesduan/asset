# -*- coding: utf-8 -*-

# preprocess event
# written by Zhang Yunyang

import collections
from django.db.models import Q
from django.template.loader import get_template
from django.template import Context
import time
import json
from monitor.models import EventLevelAdjustment
from monitor.models import EventMask
from monitor.models import EventPreprocess
from util.Pika import Pika
from monitor.process.output import BasicInfo as GetReceiver


# event handler id
HandlerID_MASK = 1
HandlerID_ADJUST_LEVEL = 2

# return code
RET_NO_NEED_NEXT = -1
RET_NOTHING_DONE = 0
RET_PROCESSED = 1

HandlerMessage = {
    HandlerID_ADJUST_LEVEL: "请注意，事件等级由%s调整为%s。",
    HandlerID_MASK: "请注意，事件被屏蔽。"
}


class BaseHandler(object):
    def __init__(self):
        pass

    def take_action(self, request_data):
        pass

    # check  and update hit info
    # 0: first time; 1: notify once, no need notify this time
    def check_update_hit_info(self):
        pass

    # subject and content
    def get_message(self, request_data):
        pass

    # get receivers
    @staticmethod
    def get_receivers(app_id, send_to):
        instance = GetReceiver()
        contact_list = instance.get_send_info(app_id)

        email_list = [
            contact_list['monitor_email'], contact_list['p_email'], contact_list['domain_email']
        ]

        email_list = [i.strip() for i in email_list if i]

        sender_to_list = send_to.split(',') if send_to else []
        sender_to_list = [i.strip() for i in sender_to_list if i]

        email_list = list(set(email_list).union(set(sender_to_list)))
        receivers = ';'.join([i for i in email_list if i])

        return receivers

    # get app info
    @staticmethod
    def get_app_info(app_id):
        return {'app_id': app_id, 'app_name': '-'}

    # dict to string
    @staticmethod
    def get_dict2str(origin_dict):
        result = json.dumps(origin_dict, encoding='UTF-8', ensure_ascii=False)
        return result

    # save in db
    @staticmethod
    def save(receivers, event_info, alarm_content):
        now = int(time.time())
        res = EventPreprocess.objects.create(event_info=event_info, alarm_content=alarm_content, receiver=receivers, create_time=now)
        if not res:
            record_id = 0
        else:
            record_id = res.id

        return record_id

    @staticmethod
    def pack_message(envelop):
        envelop['sender'] = 'eventpreprocess.ledao@yihaodian.com'
        envelop['cc'] = ''
        # render
        envelop['content'] = BaseHandler.render(envelop['content'])

    @staticmethod
    def send_message(msg):
        try:
            amqp = Pika(message=msg, exchange='message-exchange', routing_key='mailkey')
            return amqp.basic_publish()
        except Exception, e:
            return e

    @staticmethod
    def render(content):
        alarm_html_body_content = content['内容']
        alarm_html_time = content['起止时间']
        alarm_html_reason = content['原因']
        alarm_html_title = content['规则标题']
        event_html_content = ''
        for key in content:
            if key not in ('内容', '原因', '起止时间', '规则标题'):
                event_html_content += "<tr>"
                event_html_content += "<td class='td-first'>" + key + "</td>"
                event_html_content += "<td>" + content[key] + "</td>"
                event_html_content += "</tr>"

        t = get_template('mail/monitor/alert_template_preprocess.html')
        html_content = t.render(Context(locals()))
        return html_content

    @staticmethod
    def notify(req_data, subject_content):
        #     'sender': 'notification.ledao@yihaodian.com',
        #     'pid': pid,
        #     'receiver': receiver_list,
        #     'cc': cc if cc else '',
        #     'subject': subject,
        #     'content': content,
        #     'app': app_id,
        #     'app_name': app_name

        envelop = subject_content

        # notify message string
        subject_content_str = BaseHandler.get_dict2str(subject_content)

        # get receiver
        app_id = req_data.get('pool_id', 0)
        send_to = req_data.get('send_to', '')
        receivers = BaseHandler.get_receivers(app_id, send_to)

        # get app info
        app_info = BaseHandler.get_app_info(app_id)

        # event information
        event_info = BaseHandler.get_dict2str(req_data)

        # save in db
        record_id = BaseHandler.save(receivers, event_info, subject_content_str)

        envelop['receiver'] = receivers
        envelop['pid'] = record_id
        envelop['app'] = app_id
        envelop['app_name'] = app_info['app_name']
        # pack message
        BaseHandler.pack_message(envelop)

        # send
        BaseHandler.send_message(envelop)


class AdjustLevelHandler(BaseHandler):
    def __init__(self):
        self.rule = ''

    def take_action(self, request_data):
        # time, source_id, level_id
        query_filter = {'status': 0,
                        'source__id':request_data['source_id'],
                        'origin_level__id':request_data['level_id'],
                        'start_time__lte':request_data['get_time']
                        }

        queryset = EventLevelAdjustment.objects.filter(**query_filter).filter(Q(end_time__gte=request_data['get_time']) | Q(end_time=-1)).order_by('-create_time')

        if not queryset:
            return RET_NOTHING_DONE

        # type, pool, ip, keyword
        req_type = int(request_data.get('type_id', 0))
        req_pool = int(request_data.get('pool_id', 0))
        req_ip = request_data.get('ip', '')
        if req_ip:
            req_ip_list = req_ip.split(',')

        req_message = request_data.get('message', '')

        for rule in queryset:
            rule_type = rule.type_id
            rule_pool = rule.pool_id
            rule_ip = rule.ip
            rule_keyword = rule.keyword

            if rule_type > 0:
                if rule_type != req_type:
                    continue

            if rule_pool > 0:
                if rule_pool != req_pool:
                    continue

            if rule_ip:
                if not req_ip:
                    continue

                rule_ip_list = rule_ip.split(",")

                ip_match = True
                for ip in req_ip_list:
                    if ip not in rule_ip_list:
                        # inner for
                        ip_match = False
                        break

                if not ip_match:
                    # outer for
                    continue

            if rule_keyword:
                index = req_message.find(rule_keyword)
                if index == -1:
                    continue

            # at last
            self.rule = rule

            # update level id
            request_data['level_id'] = unicode(rule.new_level_id)
            request_data['level_adjustment_id'] = rule.id
            return RET_PROCESSED
        # normal
        return RET_NOTHING_DONE

    def check_update_hit_info(self):
        if not self.rule:
            return 0

        if self.rule.hit_time == 0:
            ret = 0
        else:
            ret = 1

        # update hit time
        EventLevelAdjustment.objects.filter(id=self.rule.id).update(hit_time=int(time.time()))

        return ret

    def get_message(self, request_data):
        content = collections.OrderedDict()
        if self.rule:
            # 起止时间
            start_end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.rule.start_time))
            start_end += "至"
            if self.rule.end_time == -1:
                start_end += "一直"
            else:
                start_end += time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.rule.end_time))

            content['规则标题'] = '事件等级调整规则'
            content['起止时间'] = start_end
            # 原因
            content['原因'] = self.rule.comment

            content['源'] = self.rule.source.name

            if self.rule.type_id != -1:
                content['类型'] = self.rule.type.name

            if self.rule.pool_id != -1:
                content['Pool'] = self.rule.pool.name+ "/" + self.rule.pool.name

            if self.rule.ip:
                content['IP'] = self.rule.ip

            if self.rule.keyword:
                content['关键字'] = self.rule.keyword

        content['原等级'] = self.rule.origin_level.name
        content['新等级'] = self.rule.new_level.name
        content['内容'] = HandlerMessage[HandlerID_ADJUST_LEVEL] % (self.rule.origin_level.name, self.rule.new_level.name)

        subject = u"事件等级被调整"
        message = {'subject': subject, 'content': content}
        return message

    def notify(self, req_data):
        if self.check_update_hit_info() != 0:
            # no need notify
            return

        # the subject and content of notify message
        subject_content = self.get_message(req_data)

        super(AdjustLevelHandler, self).notify(req_data, subject_content)


class MaskHandler(BaseHandler):
    def __init__(self):
        self.rule = ''

    def take_action(self, request_data):
        # time, source_id
        query_filter = {'status': 0,
                        'source__id':request_data['source_id'],
                        'start_time__lte':request_data['get_time']
                        }

        queryset = EventMask.objects.filter(**query_filter).filter(Q(end_time__gte=request_data['get_time']) | Q(end_time=-1)).order_by('-create_time')

        if not queryset:
            return RET_NOTHING_DONE

        # type, level, pool, ip, keyword
        req_type = int(request_data.get('type_id', 0))
        req_level = int(request_data.get('level_id', 0))
        req_pool = int(request_data.get('pool_id', 0))
        req_ip = request_data.get('ip', '')
        if req_ip:
            req_ip_list = req_ip.split(',')

        req_message = request_data.get('message', '')

        for rule in queryset:
            rule_type = rule.type_id
            rule_level = rule.level_id
            rule_pool = rule.pool_id
            rule_ip = rule.ip
            rule_keyword = rule.keyword

            if rule_type > 0:
                if rule_type != req_type:
                    continue

            if rule_level > 0:
                if rule_level != req_level:
                    continue

            if rule_pool > 0:
                if rule_pool != req_pool:
                    continue

            if rule_ip:
                if not req_ip:
                    continue

                rule_ip_list = rule_ip.split(",")

                ip_match = True
                for ip in req_ip_list:
                    if ip not in rule_ip_list:
                        # inner for
                        ip_match = False
                        break

                if not ip_match:
                    # outer for
                    continue

            if rule_keyword:
                index = req_message.find(rule_keyword)
                if index == -1:
                    continue

            # at last
            # mask the event
            self.rule = rule

            return RET_NO_NEED_NEXT
        # normal
        return RET_NOTHING_DONE

    def check_update_hit_info(self):
        if not self.rule:
            return 0

        if self.rule.hit_time == 0:
            ret = 0
        else:
            ret = 1

        # update hit time
        EventMask.objects.filter(id=self.rule.id).update(hit_time=int(time.time()))

        return ret

    def get_message(self, request_data):
        content = collections.OrderedDict()
        if self.rule:
            # 起止时间
            start_end = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.rule.start_time))
            start_end += "至"
            if self.rule.end_time == -1:
                start_end += "一直"
            else:
                start_end += time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(self.rule.end_time))

            content['规则标题'] = '事件屏蔽规则'
            content['起止时间'] = start_end
            # 原因
            content['原因'] = self.rule.comment

            content['源'] = self.rule.source.name

            if self.rule.type_id != -1:
                content['类型'] = self.rule.type.name

            if self.rule.level_id != -1:
                content['等级'] = self.rule.level.name

            if self.rule.pool_id != -1:
                content['Pool'] = self.rule.pool.name+ "/" + self.rule.pool.name

            if self.rule.ip:
                content['IP'] = self.rule.ip

            if self.rule.keyword:
                content['关键字'] = self.rule.keyword

        content['内容'] = HandlerMessage[HandlerID_MASK]

        subject = u"事件被屏蔽"
        message = {'subject': subject, 'content': content}
        return message

    def notify(self, req_data):
        if self.check_update_hit_info() != 0:
            # no need notify
            return

        # the subject and content of notify message
        subject_content = self.get_message(req_data)

        super(MaskHandler, self).notify(req_data, subject_content)


class HandlerManager(object):
    _instance = None

    # singleton
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(HandlerManager, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.handlers = {HandlerID_MASK: MaskHandler(), HandlerID_ADJUST_LEVEL: AdjustLevelHandler()}

    def register(self, handler_id, handler):
        self.handlers[handler_id] = handler

    def dispatch(self, req_data):
        for handler_id in self.handlers:
            ret = self.handlers[handler_id].take_action(req_data)
            if ret in (RET_NO_NEED_NEXT, RET_PROCESSED):
                self.handlers[handler_id].notify(req_data)
                if ret == RET_NO_NEED_NEXT:
                    # return directly
                    return RET_NO_NEED_NEXT
        return 0


# #####################################
# preprocess entry
# #####################################
def preprocess_entry(request_data):
    # init handler, handler manager
    manager = HandlerManager()
    ret = manager.dispatch(request_data)
    return ret




