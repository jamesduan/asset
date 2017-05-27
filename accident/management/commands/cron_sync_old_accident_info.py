# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from accident.models import Accident, AccidentDomain, AccidentAction
import time
from util.timelib import stamp2str

class Command(BaseCommand):
    args = ''
    help = 'sync old accident info from accident database，已弃用'

    def handle(self, *args, **options):
        from django.db import connections
        cursor = connections['accident'].cursor()
        cursor.execute('select id,act_manager_id,act_title,act_date,act_num,act_finish_date,act_level,act_area,'
                       'act_affect_num,act_available,act_process,act_cause_id,act_reason,act_disabled,act_mantis_id,act_remark,act_basic_time,act_detail_time from act')
        res = cursor.fetchall()
        for act in res:
            item = {
                'id': act[0],
                'duty_manager': act[1].decode('utf-8') if act[1] else '',
                'title' :  act[2].decode('utf-8') if act[2] else '',
                'start' : act[3],
                'actid' : act[4],
                'finish' : act[5],
                'level' : act[6].decode('utf-8'),
                'affect_area' : act[7].decode('utf-8') if act[7] else '',
                'affect_order' : act[8].decode('utf-8') if act[8] else '',
                'available' : act[9].decode('utf-8'),
                'process' : act[10].decode('utf-8') if act[10] else '',
                'cause_user' : act[11].decode('utf-8'),
                'reason' : act[12].decode('utf-8')if act[12] else '',
                'enable': act[13],
                'is_mantis': act[14],
                'comment': act[15].decode('utf-8') if act[15] else '',
                'basic_time': act[16],
                'detail_time': act[17]
            }

            sync_act, created = Accident.objects.using('accident').get_or_create(accidentid=item['actid'], defaults={
                'title':     item['title'],
                'level':     int(str(item['level'])[-1]) if item['level'] != '' else 0,
                'duty_manager_name':     item['duty_manager'],
                'happened_time':     item['start'],
                'finish_time':     item['finish'],
                'process':     item['process'],
                'duty_users': item['cause_user'],
                'affect':   item['affect_area'] +' ' + item['affect_order'],
                'is_available': 1 if str(item['available']).strip()=='影响' else 0,
                'comment': item['comment'],
                'reason': item['reason'],
                'basicinfo_time': item['basic_time'],
                'detailinfo_time': item['detail_time'],
                'mantis_id': item['is_mantis'],
                'is_accident': item['enable'],
                'type_id':  0,
                'status_id': 0,

            })
            if not created:
                sync_act.title = item['title']
                sync_act.level = int(str(item['level'])[-1]) if item['level'] != '' else 0
                sync_act.duty_manager_name = item['duty_manager']
                sync_act.happened_time = item['start']
                sync_act.finish_time = item['finish']
                sync_act.process = item['process']
                sync_act.duty_users = item['cause_user']
                sync_act.affect = item['affect_area'] +' ' + item['affect_order']
                sync_act.is_available = 1 if str(item['available']).strip()=='影响' else 0
                sync_act.comment = item['comment']
                sync_act.reason = item['reason']
                sync_act.basicinfo_time = item['basic_time']
                sync_act.detailinfo_time = item['detail_time']
                sync_act.mantis_id = item['is_mantis']
                sync_act.is_accident = item['enable']
                sync_act.type_id = 0
                sync_act.status_id = 0
                sync_act.save()

            cursor.execute('select * from act_cause_dom where act_id=%s' % item['id'])
            duty_domains = cursor.fetchall()

            cursor.execute('select * from act_cause where act_id=%s' % item['id'])
            duty_dept = cursor.fetchall()
            for dm in duty_domains:
                act_dm, dm_created = AccidentDomain.objects.using('accident').get_or_create(accident_id=item['actid'], domainid=dm[1], defaults={
                    'departmentid':     duty_dept[0][1],
                })
                if not dm_created:
                    act_dm.departmentid = duty_dept[0][1]
                    act_dm.save()
            try:
                accident = Accident.objects.using('accident').get(accidentid=sync_act.accidentid)
            except Accident.DoesNotExist:
                print('accidentid=%s does not exits' % sync_act.accidentid)
                continue
            cursor.execute('select * from act_atc where act_id=%s' % item['id'])
            types = cursor.fetchall()
            if types:
                accident.type_id = int(types[0][1])

            cursor.execute('select * from act_postmortem where act_id=%s' % item['id'])
            postmortem = cursor.fetchall()
            if postmortem:
                accident.root_reason = postmortem[0][3].decode('utf-8') if postmortem[0][3] else ''
                if int(postmortem[0][2]) == 4:
                    accident.type_id = 14
                if int(postmortem[0][2])== 5:
                    accident.type_id == 15

            cursor.execute('select * from act_process where act_id=%s' % item['id'])
            actions = cursor.fetchall()
            for act in actions:
                status_name = act[6].decode('utf-8') if act[6] else ''
                status = 2
                if status_name.strip() in [u'延迟', u'无反馈']:
                    status = 2
                elif status_name.strip() in [u'进行中', u'未开始']:
                    status = 1
                elif status_name.strip() == u'已完成':
                    status = 200
                elif status_name.strip() == u'已取消':
                    status = 400
                else:
                    print('status valid:%s' % act[6])
                act_content = act[2].decode('utf-8') if act[2] else ''
                action, act_created = AccidentAction.objects.using('accident').get_or_create(accident_id=item['actid'], action=act_content, defaults={
                    'duty_users':     act[4].decode('utf-8') if act[4] else '',
                    'expect_time':      act[5],
                    'status': status
                })
                if not act_created:
                    action.duty_users = act[4].decode('utf-8') if act[4] else ''
                    action.expect_time = act[5]
                    action.status = status
                    action.save()

            if accident.level == 0 and accident.finish_time == 0:
                accident.status_id = 2
            else:
                if accident.affect == '':
                    accident.status_id = 3
                else:
                    if accident.level == 1 or accident.level == 2:
                        act_actions = AccidentAction.objects.using('accident').filter(accident_id = accident.accidentid)
                        if len(act_actions)== 0:
                            accident.status_id = 4
                        elif len(act_actions) == 1:
                            if act_actions[0].status == 1:
                                accident.status_id = 5
                            elif act_actions[0].status == 2:
                                accident.status_id =6
                            else:
                                accident.status_id = 200
                        else:
                            action_ids = [act.status for act in act_actions]
                            if 2 in action_ids:
                                accident.status_id = 6
                            elif 1 in action_ids:
                                accident.status_id = 5
                            else:
                                accident.status_id = 200
                    else:
                        accident.status_id = 200
            accident.save()
        print stamp2str(time.time()) + ':success'