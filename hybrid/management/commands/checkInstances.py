# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from hybrid.models import *
from django.template import loader
import commands
from util.sendmail import *

class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        requirementdetail = HybridRequirementDetail.objects.filter(status=1)
        success_list = []
        fail_list = []
        for item in requirementdetail:
            cmdstr = "ssh %s -o PasswordAuthentication=yes -o UserKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -o ConnectTimeout=5 'ls' >> /dev/null && echo status:yes || echo status:no" % item.ip
            status, output = commands.getstatusoutput(cmdstr)
            if status == 0:
                if output.find("status:yes") >= 0:
                    item.status = 2
                    success_list.append(item.ip)
                else:
                    fail_list.append(item.ip)
                    item.status = 3
            else:
                fail_list.append(item.ip)
                item.status = 3
            item.save()