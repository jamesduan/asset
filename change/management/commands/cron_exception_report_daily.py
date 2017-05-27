# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from change.models import ExceptionReport, ExceptionReportDaily,ExceptionDetailComment
from ycc.models import ExceptionConfigAccessDetail
from django.db import connections
import time
from datetime import date
import datetime
from util import sendmail
from util.timelib import *
import requests
from monitor.process.process import process_notification
import json
from django.template import loader

class Command(BaseCommand):
    args = '<threadNums>'
    help = 'Consumers for deploy'

    def handle(self, *args, **options):
        exception_reports = ExceptionReport.objects.filter(status=1)
        current_time = int(time.time())
        current_tuple = time.localtime()
        current_hour= current_tuple.tm_hour
        current_wday= current_tuple.tm_wday
        time_str = date.today().strftime("%Y-%m-%d")+ ' 00:00:00'
        update_time = int(time.mktime(time.strptime(time_str, '%Y-%m-%d %H:%M:%S'))) #控制每天只保留一条记录
        for exception_report in exception_reports:
            if exception_report.type==0:
                cursor = connections[exception_report.use_db].cursor()
                cursor.execute(exception_report.cmdbsql)
                data = cursor.fetchall()

                mail_list = str(exception_report.db_mail).split(',')
                #排除备注数据已恢复正常的情况
                indexs = [rs[0] for rs in data]
                comments = ExceptionDetailComment.objects.filter(exception_id = exception_report.id)
                comments_id = [c.index for c in comments]
                for comment in comments:
                    if comment.index not in indexs:
                        sendmail.sendmail_html(subject='CMDB异常报表存在备注数据已恢复正常',
                           html_content='<h1>Hi:</h1><br><h3>异常报表存在备注数据恢复正常，备注信息已删除，原始记录如下</h3>' +
                                        '<br>&nbsp;&nbsp;异常名称：<strong>'+ exception_report.cname +
                                        '</strong><br>&nbsp;&nbsp;查询日期：<strong>'+ stamp2str(time.time()) +
                                        '</strong><br>&nbsp;&nbsp;索引值：<strong>'+ comment.index +
                                        '</strong><br>&nbsp;&nbsp;备注信息：<strong>'+ comment.comment +
                                        '</strong><br>&nbsp;&nbsp;详细信息请查看以下页面： ' +
                                        '<br>&nbsp;&nbsp;&nbsp;&nbsp;http://oms.yihaodian.com.cn/cmdbv2/change/exception_detail/' + str(exception_report.id) +
                                        '/ <br>&nbsp;&nbsp;请核实被删除备注信息是否恢复正常！<br>&nbsp;&nbsp;谢谢！',
                                               recipient_list = mail_list)
                        comment.delete()

                new_exceptions = []
                for new in data:
                    if new[0] not in comments_id:
                        new_exceptions.append(new)

                comment_count = ExceptionDetailComment.objects.filter(exception_id = exception_report.id).count()
                new_count = len(data) - comment_count

                #与前一天的异常数做对比，出现新的异常则报警发送邮件
                # if new_count > exception_report.exception_count:
                #     new_exp = ''
                #     for new1 in new_exceptions:
                #         new_exp += str(new1[0]) + '&nbsp;&nbsp;'
                #     sendmail.sendmail_html(subject='CMDB异常报表出现' + str(new_count - exception_report.exception_count) + '条新的异常数据',
                #            html_content='<h1>Hi:</h1><br><h3>异常报表新增' + str(new_count - exception_report.exception_count) + '条异常数据</h3>' +
                #                         '<br>&nbsp;&nbsp;异常名称：<strong>'+ exception_report.cname +
                #                         '</strong><br>&nbsp;&nbsp;出现日期：<strong>'+ stamp2str(time.time()) +
                #                         '</strong><br>&nbsp;&nbsp;异常数据：<strong>'+ new_exp +
                #                         '</strong><br>&nbsp;&nbsp;详细信息请查看以下页面： ' +
                #                         '<br>&nbsp;&nbsp;&nbsp;&nbsp;http://oms.yihaodian.com.cn/cmdbv2/change/exception_detail/' + str(exception_report.id) +
                #                         '/ <br>&nbsp;&nbsp;请尽快排查数据数据出现的原因并做处理！<br>&nbsp;&nbsp;谢谢！',
                #            recipient_list = mail_list)

                #更新异常数据数量
                exception_report.last_update = current_time
                exception_report.exception_count = new_count
                exception_report.save()
                connections[exception_report.use_db].close()

                daily, created = ExceptionReportDaily.objects.get_or_create(report_id=exception_report.id, create_time=update_time,defaults={
                    'exception_count': new_count,
                })
                if not created:
                    daily.exception_count = new_count
                    daily.save()
            #if exception_report.type==1 and current_wday==1:
            if exception_report.type==1:
                url=exception_report.api_url.strip()
                headers= {'Authorization': 'Basic Y21kYjpmQWIoeFVZWTVuOSkqXmdhXmE='}
                content=requests.get(url,headers=headers).json()

                new_count=content['count']
                exception_report.exception_count = new_count
                exception_report.last_update = current_time
                exception_report.save()
                daily, created = ExceptionReportDaily.objects.get_or_create(report_id=exception_report.id, create_time=update_time,defaults={
                    'exception_count': new_count,
                })

            if exception_report.frequency and exception_report.last_email_date and new_count >0:
                next_mail_date=exception_report.last_email_date+datetime.timedelta(days=exception_report.frequency)
                if date.today()==next_mail_date:
                    title='异常报表异常提醒'
                    message='异常名称：'+exception_report.cname+'。详细信息请查看链接，请尽快排查数据数据出现的原因并做处理！http://oms.yihaodian.com.cn/cmdbv2/change/exception_detail/'+ str(exception_report.id) +'/'
                    html_content = loader.render_to_string('cmdbv2/cmdb/text_mail.html', {
                        'content': '您Domain发生'+exception_report.cname+'异常,详细信息请查看以下链接,请尽快排查数据数据出现的原因并做处理！',
                        'url': 'http://oms.yihaodian.com.cn/cmdbv2/change/exception_detail/' + str(exception_report.id) +'/'

                    })
                    recipient_list=[]
                    if exception_report.owner_domain:
                        recipient_list=exception_report.owner_domain.domainemailgroup
                    elif exception_report.type==1:
                        exceptionconfigs=ExceptionConfigAccessDetail.objects.filter(error=int(exception_report.api_url[-1]))
                        for exceptionconfig in exceptionconfigs:
                            domainemail=exceptionconfig.domain.domainemailgroup if exceptionconfig.domain else None
                            if domainemail and domainemail not in recipient_list:
                                 recipient_list.append(domainemail)
                        recipient_list=','.join(recipient_list)
                    else:
                        recipient_list=','.join(list(set([rs[-1] for rs in data])))
                    datas={'level_id':exception_report.level_id,'source_id':29 ,'title': title,'message': message,'send_to': recipient_list,
                                 'cc':exception_report.db_mail,'get_time': time.time()}
                    process_notification(json.dumps(datas))
                    exception_report.last_email_date=date.today()
                    exception_report.save()
                    print message
                    print  recipient_list

        print stamp2str(time.time()) + ':success'