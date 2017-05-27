# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from hybrid.models import *
from django.template import loader
import json, urllib2
from util.timelib import *
from util.sendmail import *
from assetv2.settingscmdbv2 import HYBRID_CDS_REQUIRE_TASK


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        requirement = HybridRequirement.objects.filter(status=2)
        for item in requirement:
            uri = HYBRID_CDS_REQUIRE_TASK + item.task_id
            req = urllib2.Request(uri)
            req.add_header("Accept", "application/json")
            req.add_header("Content-Type", "application/json")
            response = urllib2.urlopen(req)
            result = response.read()
            ret_data = json.loads(result)
            ip_list = []
            for item1 in ret_data['completed_instances']:
                if item1['status'] == 'running':
                    ip_list.append(item1['ip'])
                    hybridrequirementdetail, created = HybridRequirementDetail.objects.get_or_create(index=item1['instance_uuid'], requirement_id=item.id, defaults={
                        "ip": item1['ip'],
                        "status": 1,
                        "created": stamp2str(int(time.time())),
                    })
                    if created:
                        item.real_total = item.real_total + 1
                        item.save()
            if item.total == HybridRequirementDetail.objects.filter(requirement_id=item.id).count():
                item.status = 3
                item.save()
                mail_title = '服务器IP全部申请完毕，请等待服务器验证'
                mail_list = ["lizhigang@yhd.com", "IT_OPS_NETWORK@yhd.com"]
                html_content = loader.render_to_string('mail/hybrid.html', {
                                                                'cname': item.cname,
                                                               'total':item.total,
                                                               'machine_config':item.machine_config,
                                                               'server_template':item.server_template,
                                                               'idc':item.idc,
                                                               'ip_list':ip_list})

                sendmail_html(mail_title,html_content,mail_list)