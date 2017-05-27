# -*- coding: utf-8 -*-
from util.Pika import Pika
from cmdb.models import AppContact, DdUsers
from monitor.models import SendLog, VoiceWarning, Alarm
from cmdb.models import Rota, RotaMan, RotaBackup
from monitor.utils import get_date
import time
import hashlib


def get_manager_info():
    now = int(time.time())
    try:
        current_time = get_date()
        cur_rota = Rota.objects.get(promotion=0, duty_domain=800, duty_date_start__lt=current_time, duty_date_end__gte=current_time)
        duty_manager = RotaMan.objects.get(rota_id=cur_rota.id).man
        back_duty_manager = RotaBackup.objects.get(rota_id=cur_rota.id).backup

        return {
            'username': duty_manager.username,
            'email': duty_manager.email,
            'telephone': duty_manager.telephone
        }
    except Exception, e:
        return False


def check_phone(phone_list):
    ok_list = []
    bad_list = []
    phone_map = {}

    phone_list = [str(ii) for ii in phone_list if ii]
    if not phone_list:
        return ok_list, bad_list

    try:
        name = DdUsers.objects.filter(telephone__in=phone_list, enable=0)
    except Exception, e:
        name = []
    if name:
        for j in name:
            phone_map[j.telephone] = j.username

    for i in phone_list:
        if i in phone_map:
            ok_list.append(i)
        else:
            bad_list.append(i)

    return ok_list, bad_list


class OutPut(object):
    def send(self):
        pass


class SendMailXX(OutPut):
    """
    :app_name: site and pool with "/" like "ops/dev"
    """
    def send(self, receiver_list, subject, content, app_id, app_name, cc, pid):
        message = {
            'sender': 'notification.ledao@yihaodian.com',
            'pid': pid,
            'receiver': receiver_list,
            'cc': cc if cc else '',
            'subject': subject,
            'content': content,
            'app': app_id,
            'app_name': app_name
        }
        try:
            amqp = Pika(message=message, exchange='message-exchange', routing_key='mailkey')
            return amqp.basic_publish()
        except Exception, e:
            return e


class SendPhoneXX(OutPut):
    def send(self, receiver_list, content, app_id, app_name, pid):
        message = {
            'sender': 'notification.ledao@yihaodian.com',
            'pid': pid,
            'receiver': receiver_list,
            'cc': '',
            'content': content,
            'app': app_id,
            'app_name': app_name
        }
        try:
            amqp = Pika(message=message, exchange='message-exchange', routing_key='smskey')
            return amqp.basic_publish()
        except Exception, e:
            return e


class SendVoice(OutPut):
    def send(self, message):
        content = message
        h = hashlib.md5()
        h.update(content)
        md5_content = h.hexdigest()
        create_time = int(time.time())
        status = 0
        operator = ''
        operator_time = 0

        # 判断是否在15分内发过了
        res = VoiceWarning.objects.filter(
            md5_content=md5_content,
            create_time__gte=create_time-15*60
        )
        if res:
            return "this message have inserted in 15 minutes."
        else:
            res = VoiceWarning.objects.create(
                content=content,
                md5_content=md5_content,
                create_time=create_time,
                status=status,
                operator=operator,
                operator_time=operator_time
            )
            if res:
                return "send ok"
            else:
                return "send fail"


class SendTTS(OutPut):
    def send(self, receiver_list, content, app_id, app_name, pid):
        message = {
            'sender': 'notification.ledao@yihaodian.com',
            'pid': pid,
            'receiver': receiver_list,
            'cc': '',
            'content': content,
            'app': app_id,
            'app_name': app_name
        }
        try:
            amqp = Pika(message=message, exchange='message-exchange', routing_key='voicekey')
            return amqp.basic_publish()
        except Exception, e:
            return e


class BasicInfo(object):
    def get_send_info(self, app_id):
        monitor_email = "Monitor@yhd.com"
        zhiban_manager = None
        zhiban_email = None
        zhiban_no = None

        head_user = None
        head_email = None
        head_no = None

        p_user = None
        p_email = None
        p_no = None

        domain_email = None

        res = get_manager_info()
        if res:
            zhiban_manager = res['username']
            zhiban_email = res['email']
            zhiban_no = res['telephone']

        res = AppContact.objects.filter(pool_id=app_id)
        if res:
            res = res[0]
            head_user = res.head_user
            head_email = res.head_email
            head_no = res.head_no

            p_user = res.p_user
            p_email = res.p_email
            p_no = res.p_no

            domain_email = res.domain_email

        return {
            'zhiban_manager': zhiban_manager, 'zhiban_no': zhiban_no, 'zhiban_email': zhiban_email,
            'monitor_email': monitor_email,
            'head_user': head_user, 'head_email': head_email, 'head_no': head_no,
            'p_user': p_user, 'p_email': p_email, 'p_no': p_no,
            'domain_email': domain_email
        }


class NotificationOutPut(BasicInfo):
    mail_instance = None
    voice_instance = None
    phone_instance = None
    TTS_instance = None

    def __init__(self):
        self.mail_instance = SendMailXX()
        self.phone_instance = SendPhoneXX()
        self.voice_instance = SendVoice()
        self.TTS_instance = SendTTS()

    def send(self, level_id, app_id, event_id, ignore, status, params_list):
        this_time = int(time.time())

        caller_list = []
        sender_to_list = []
        cc = params_list['cc']
        email_list = []
        phone_list = []

        if 'sender_to' in params_list and params_list['sender_to']:
            sender_to_list = params_list['sender_to']
        if 'caller' in params_list and params_list['caller']:
            caller_list = params_list['caller']

        if ignore != 1:
            info = self.get_send_info(app_id)
            if level_id == 100:
                email_list = [
                    info['zhiban_email'], info['monitor_email'], info['head_email'],
                    info['p_email'], info['domain_email']
                ]
                phone_list = [
                    info['zhiban_no'], info['head_no'], info['p_no']
                ]
            elif level_id == 200:
                email_list = [
                    info['monitor_email'], info['head_email'],
                    info['p_email'], info['domain_email']
                ]
                phone_list = [
                    info['head_no'], info['p_no']
                ]
            elif level_id == 300:
                email_list = [
                    info['p_email'], info['domain_email']
                ]
                phone_list = [
                    info['p_no']
                ]
            elif (level_id == 400) or (level_id == 350):
                email_list = [
                    info['p_email'], info['domain_email']
                ]
            else:
                pass

        if ignore == 2:
            phone_list = []
        elif ignore == 3:
            email_list = []

        email_list = [i.strip() for i in email_list if i]
        sender_to_list = [j.strip() for j in sender_to_list if j]
        phone_list = [str(k) for k in phone_list if k]
        caller_list = [str(l) for l in caller_list if l]

        email_list = list(set(email_list).union(set(sender_to_list)))
        phone_list = list(set(phone_list).union(set(caller_list)))

        # if level_id < 500:
        if email_list:
            receiver_str = ';'.join([j for j in email_list if j])
            cc_str = ';'.join([j for j in cc if j])
            if receiver_str:
                res = Alarm.objects.create(
                    event_id=event_id, method_id=1, result='', receiver=receiver_str, create_time=this_time)
                tmp = {
                    'pid': res.id,
                    'receiver_list': receiver_str,
                    'cc': cc_str,
                    'subject': params_list['subject'],
                    'content': params_list['html_content'],
                    'app_id': app_id,
                    'app_name': params_list['app_name']
                }
                result = self.mail_instance.send(**tmp)

        if (level_id <= 300) and (ignore not in [4]) and (status != 2):
            if params_list['content']:
                text = params_list['caller_message'] if params_list['caller_message'] else params_list['content']
                result = self.voice_instance.send(text+"(来自新版)")
                Alarm.objects.create(
                    event_id=event_id, method_id=3, result=result, receiver='', create_time=this_time)

        if phone_list:
            ok_list, bad_list = check_phone(phone_list)
            if ok_list:
                for phone in ok_list:
                    res = Alarm.objects.create(
                        event_id=event_id, method_id=2, result='', receiver=phone, create_time=this_time)
                    tmp = {
                        'pid': res.id,
                        'receiver_list': phone,
                        'content': params_list['caller_message'] if params_list['caller_message'] else params_list['content'],
                        'app_id': app_id,
                        'app_name': params_list['app_name']
                    }

                    result = self.phone_instance.send(**tmp)
            if bad_list:
                status_id = 3
                receiver_str = ','.join(bad_list)

                Alarm.objects.create(
                    event_id=event_id, method_id=2, result='', receiver=receiver_str, status_id=status_id, create_time=this_time)
