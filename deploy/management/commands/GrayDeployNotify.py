# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from django.template import loader
from cmdb.models import AppContact, App, Site
from deploy.models import DeployMain, DeployMainConfig
from deploy.utils.Utils import *
from util.timelib import *
from util.sendmail import *
from assetv2.settingsdeploy import OMS_HOST, DEPLOY_INTERVAL, U_DELAY, U_MAIL_RECIPIENT, U_MAIL_RECIPIENT_FOR_PUBLISH_ERROR, LEDAO_POOL_ID
from util.httplib import httpcall2
from django.conf import settings
import time
import datetime

event_url_v2 = settings.EVENT['PREFIX'] + settings.EVENT['API_V2']

class Command(BaseCommand):

    def handle(self, *args, **options):
        now = datetime.datetime.now()
        st = datetime.datetime.strptime(now.strftime('%Y-%m-%d %H'), '%Y-%m-%d %H')
        # en = st + datetime.timedelta(hours=1) - datetime.timedelta(seconds=1)
        st_unixtime = long(time.mktime(st.timetuple()))
        mail_dict = dict()
        jiraid_dict = dict()
        packtype_dict = {0: 'webapps', 3: 'static'}
        app_id_list = []
        filters = dict()
        filters['is_auto_published'] = 0
        filters['publishdatetimefrom'] = st_unixtime
        # filters['publishdatetimeto'] = en_unixtime
        filters['publishtimetype__in'] = (1, 2, 3, 4)

        for deploy in DeployMainConfig.objects.filter(**dict(filters, **{'status': 1, 'gray_release_info__isnull' : False})):
            jiraid = str(deploy.jiraid)
            app = deploy.app
            site = app.site if app else None
            pool = '{0}/{1}'.format(site.name if site else '', app.name if app else '')
            mail_dict[jiraid] = mail_dict.get(jiraid, dict())
            mail_dict[jiraid][pool] = mail_dict[jiraid].get(pool, dict())
            mail_dict[jiraid][pool]['config'] = mail_dict[jiraid][pool].get('config', [])
            mail_dict[jiraid][pool]['config'].append(str(deploy.depid))
            # deploy.is_auto_published = 1
            # deploy.save()
            jiraid_dict[jiraid] = deploy.create_time
            app_id_list.append(deploy.app_id)
        # 拉取webapps和static发布申请单
        for deploy in DeployMain.objects.filter(**dict(filters, **{'status__in': (1, 2, 3), 'packtype__in': (0, 3), 'is_gray_release': 1})):
            jiraid = str(deploy.jiraid)
            packtype = deploy.packtype
            app = deploy.app
            site = app.site if app else None
            pool = '{0}/{1}'.format(site.name if site else '', app.name if app else '')
            mail_dict[jiraid] = mail_dict.get(jiraid, dict())
            mail_dict[jiraid][pool] = mail_dict[jiraid].get(pool, dict())
            mail_dict[jiraid][pool][packtype_dict[packtype]] = mail_dict[jiraid][pool].get(packtype_dict[packtype], [])
            mail_dict[jiraid][pool][packtype_dict[packtype]].append(str(deploy.depid))
            # deploy.is_auto_published = 1
            # deploy.save()
            jiraid_dict[jiraid] = deploy.create_time
            app_id_list.append(deploy.app_id)
        # # 拉取webapps和static发布申请单
        print mail_dict
        if mail_dict:
            # email_info = self.format_table(mail_dict)
            # print "sending email..."
            # self.deploy_email(email_info, st.hour, app_id_list)
            # 语音告警
            event_dict_v2 = {
            'title' : '灰度发布提醒',
            'level_id' : 300,
            'type_id' : 3,
            'source_id' : 16,
            'pool_id' : LEDAO_POOL_ID,
            'message' : '当前时间段内有灰度发布，请检查邮件!',
            'send_to' : ','.join(U_MAIL_RECIPIENT),
            'ignore' : 1
            }
            print httpcall2(event_url_v2, 'POST', body=event_dict_v2)
        else:
            print "Can not found any gray publish task."

    #def deploy_email(self, email_info, hour, app_id_list):
    def deploy_email(self, email_info, hour, app_id_list):
        to = []
        for app_id in list(set(app_id_list)):
            try:
                contact = AppContact.objects.get(pool_id=app_id)
            except AppContact.DoesNotExist:
                print 'AppContact is None'
            mails = [contact.domain_email]+contact.p_email.split(',')
            to += [item.strip() for item in mails if item.strip()]
        # mail_title = u'【上线预告(新版)】%s--%s' % (stamp2str(time.time(),  formt='%Y%m%d'),stamp2str(time.time(),  formt='%H:10'))
        mail_title = u'【灰度发布】操作通知'
        html_content = loader.render_to_string('deploy/gray_deploy_notify.html', {'email_info': email_info})
        # send_email(subject=mail_title, content=html_content.encode('utf8'), recipient_list=list(set(to)) + U_MAIL_RECIPIENT)
        sendmail_v2(mail_title, html_content.encode('utf8'), list(set(to)) + U_MAIL_RECIPIENT, None)

    def format_table(self, mail_dict):
        table_list = []
        for jiraid in mail_dict:
            jiraid_flag = True
            jiraid_rowspan = 0
            for pool in mail_dict[jiraid]:
                jiraid_rowspan += sum([len(mail_dict[jiraid][pool][type]) for type in mail_dict[jiraid][pool]])
            for pool in mail_dict[jiraid]:
                pool_flag = True
                pool_rowspan = sum([len(mail_dict[jiraid][pool][type]) for type in mail_dict[jiraid][pool]])
                site_name, app_name = pool.split('/')
                app_obj = App.objects.get(name=app_name, site_id=Site.objects.get(name=site_name).id, status=0)
                for type in mail_dict[jiraid][pool]:
                    # detail = 'ycc' if type == 'config' else ('prod' if app_obj.id in settings.APP_ID_LIST else 'normal')
                    detail = 'ycc' if type == 'config' else 'prod'
                    for depid in mail_dict[jiraid][pool][type]:
                        # if detail == 'normal' and DeployMain.objects.get(depid=depid).is_gray_release == 1:
                        #     detail = 'gray'
                        table_list.append('<tr>')
                        if jiraid_flag:
                            table_list.append('<td rowspan={0}>'.format(jiraid_rowspan))
                            table_list.append('<a href="http://trident.yihaodian.com.cn/browse/{0}">{1}</a></td>'.format(jiraid, jiraid))
                            table_list.append('</td>')
                            jiraid_flag = False
                        if pool_flag:
                            table_list.append('<td rowspan={0}>{1}</td>'.format(pool_rowspan, pool))
                            pool_flag = False
                        table_list.append('<td>')
                        table_list.append('<a href="http://{0}/deploy/{1}/detail/?depid={2}">{3}</a></td>'.format(OMS_HOST, detail, depid, depid))
                        table_list.append('</td>')
                        table_list.append('</tr>')
        return '\n'.join(table_list)