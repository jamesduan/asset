# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

import json
from util.httplib import *
from cmdb.models import AppContact,Site,App
from django.conf import settings
from util.sendmail import sendmail_html
from django.template.loader import get_template
from django.template import Context
from util.timelib import stamp2str, str2stamp
import time
from assetv2.settingscmdbv2 import CMDB_CRON_MAILLIST


def syn_appcontact():
    message = []

    get_response = urllib.urlopen(settings.CRON_APP_AND_CONTACT_API).read()
    res = json.loads(get_response)
    data = res['response']
    response = {'success': True, 'msg': u'CMIS系统同步完成！'}
    for item in data:
        cmis_site_id = item['siteId']
        try:
            site = Site.objects.get(cmis_id=cmis_site_id)
            site_id = site.id

            cmis_sync_app, created = App.objects.get_or_create(cmis_id= item['id'],cmis_site_id=cmis_site_id, defaults={
                'name':         item['poolName'].strip(),
                'site_id':      site_id,
                'type':         0,
                'level':        item['poolLevel'],
                'ctime':        str2stamp(item['createTime'], formt='%Y-%m-%d %H:%M:%S'),
                'comment':      item['businessDesc'],
                'status':       item['enable'],
                'is_cmis_sync': 1,
                'domainid':     item['domainId'],
                'service_name': item['serviceTypeName'],
                'test_status':  item['testEnvEnable']
            })

            if not created:
                if cmis_sync_app.type == 0:
                    #以后应添加新增App记录至变更系统
                    cmis_sync_app.name = item['poolName'].strip()
                    cmis_sync_app.site_id = site_id
                    cmis_sync_app.type = 0
                    cmis_sync_app.level = item['poolLevel']
                    cmis_sync_app.ctime = str2stamp(item['createTime'], formt='%Y-%m-%d %H:%M:%S')
                    cmis_sync_app.comment = item['businessDesc']
                    cmis_sync_app.status = item['enable']
                    cmis_sync_app.is_cmis_sync = 1
                    cmis_sync_app.domainid = item['domainId']
                    cmis_sync_app.service_name = item['serviceTypeName']
                    cmis_sync_app.test_status = item['testEnvEnable']
                    cmis_sync_app.save()
                else:
                    content = u'CMIS系统调用非业务POOL的更新，cmis ID为%s,POOL名为 %s' %(cmis_sync_app.cmis_id,cmis_sync_app.name)
                    response = {'success': False, 'msg': content}
                    message.append('error: CMIS系统调用非业务POOL的更新，cmis ID为%s,POOL名为 %s' %(cmis_sync_app.cmis_id,cmis_sync_app.name))
                    continue
            #以后应添加删除App记录至变更系统
            cmis_sync_appcontact, created = AppContact.objects.get_or_create(site_id=site.id,pool_id=cmis_sync_app.id, defaults={
                'site_name':    item['siteName'].strip(),
                'pool_name':    item['poolName'].strip(),
                'pool_status':    item['enable'],
                'department_id':    item['deptId'],
                'p_user':    item['domainLeaderVo']['adAccount'],
                'p_email':    item['domainLeaderVo']['email'],
                'p_no':    item['domainLeaderVo']['mobilePhoneNo'],
                'domain_email':    item['domainEmailGroup'],
                'sa_user':    item['saVo']['adAccount'],
                'sa_email':    item['saVo']['email'],
                'sa_no':    item['saVo']['mobilePhoneNo'],
                'b_user':    item['backupDomainLeaderVo']['adAccount'] if item.has_key('backupDomainLeaderVo') else '',
                'b_email':    item['backupDomainLeaderVo']['email'] if item.has_key('backupDomainLeaderVo') else '',
                'b_no':    item['backupDomainLeaderVo']['mobilePhoneNo'] if item.has_key('backupDomainLeaderVo') else '',
                'department':    item['deptName'].strip(),
                'domain_id':    item['domainId'],
                'domain_code':    item['domainCode'].strip(),
                'domain_name':    item['domainName'].strip(),
                'domain_leader':    item['domainLeaderVo']['displayName'] if item.has_key('domainLeaderVo') else '',
                'domain_account':    item['domainLeaderVo']['adAccount'] if item.has_key('domainLeaderVo') else '',
                'sa_backup_user':    item['backupSaVo']['adAccount'] if item.has_key('backupSaVo') else '',
                'sa_backup_email':    item['backupSaVo']['email'] if item.has_key('backupSaVo') else '',
                'sa_backup_no':    item['backupSaVo']['mobilePhoneNo'] if item.has_key('backupSaVo') else '',
                'head_user':    item['departmentLeaderVo']['adAccount'] if item.has_key('departmentLeaderVo') else '',
                'head_email':    item['departmentLeaderVo']['email'] if item.has_key('departmentLeaderVo') else '',
                'head_no':    item['departmentLeaderVo']['mobilePhoneNo'] if item.has_key('departmentLeaderVo') else ''
            })
            if not created:
                cmis_sync_appcontact.site_name = item['siteName'].strip()
                cmis_sync_appcontact.pool_name = item['poolName'].strip()
                cmis_sync_appcontact.pool_status = item['enable']
                cmis_sync_appcontact.department_id = item['deptId']
                cmis_sync_appcontact.p_user = item['domainLeaderVo']['adAccount']
                cmis_sync_appcontact.p_email = item['domainLeaderVo']['email']
                cmis_sync_appcontact.p_no = item['domainLeaderVo']['mobilePhoneNo']
                cmis_sync_appcontact.domain_email = item['domainEmailGroup']
                cmis_sync_appcontact.sa_user = item['saVo']['adAccount']
                cmis_sync_appcontact.sa_email = item['saVo']['email']
                cmis_sync_appcontact.sa_no = item['saVo']['mobilePhoneNo']
                cmis_sync_appcontact.b_user = item['backupDomainLeaderVo']['adAccount'] if item.has_key('backupDomainLeaderVo') else ''
                cmis_sync_appcontact.b_email = item['backupDomainLeaderVo']['email'] if item.has_key('backupDomainLeaderVo') else ''
                cmis_sync_appcontact.b_no = item['backupDomainLeaderVo']['mobilePhoneNo'] if item.has_key('backupDomainLeaderVo') else ''
                cmis_sync_appcontact.department = item['deptName'].strip()
                cmis_sync_appcontact.domain_id = item['domainId']
                cmis_sync_appcontact.domain_code = item['domainCode'].strip()
                cmis_sync_appcontact.domain_name = item['domainName'].strip()
                cmis_sync_appcontact.domain_leader = item['domainLeaderVo']['displayName'] if item.has_key('domainLeaderVo') else ''
                cmis_sync_appcontact.domain_account = item['domainLeaderVo']['adAccount'] if item.has_key('domainLeaderVo') else ''
                cmis_sync_appcontact.sa_backup_user = item['backupSaVo']['adAccount'] if item.has_key('backupSaVo') else ''
                cmis_sync_appcontact.sa_backup_email = item['backupSaVo']['email'] if item.has_key('backupSaVo') else ''
                cmis_sync_appcontact.sa_backup_no = item['backupSaVo']['mobilePhoneNo'] if item.has_key('backupSaVo') else ''
                cmis_sync_appcontact.head_user = item['departmentLeaderVo']['adAccount'] if item.has_key('departmentLeaderVo') else ''
                cmis_sync_appcontact.head_email = item['departmentLeaderVo']['email'] if item.has_key('departmentLeaderVo') else ''
                cmis_sync_appcontact.head_no = item['departmentLeaderVo']['mobilePhoneNo'] if item.has_key('departmentLeaderVo') else ''
                cmis_sync_appcontact.save()
        except Site.DoesNotExist:
            response = {'success': False, 'msg': u'站点%s不存在，同步错误！' % cmis_site_id}
            message.append('error: 站点%s不存在，同步错误！' % cmis_site_id)
            break
        except Exception, e:
            response = {'success': False, 'msg': str(e)}
            message.append('error: 站点ID：%s pool名：%s detail: %s' % (cmis_site_id, cmis_sync_app.name, str(e)))
            break

    message.append(stamp2str(time.time()) + ':finish')

    if not response['success']:
        # 邮件通知
        t = get_template('mail/cmdb/cron_sync_by_cmis_error.html')
        title = '【同步Pool和联系人信息失败】%s' % stamp2str(int(time.time()), formt='%Y-%m-%d %H:%M:%S')
        html_content = t.render(Context(locals()))
        sendmail_html(title, html_content, CMDB_CRON_MAILLIST)

    return response


