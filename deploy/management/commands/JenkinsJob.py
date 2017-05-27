# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from cmdb.models import App
from deploy.models import DeployJenkinsJob
from django.conf import settings
from util.httplib import httpcall2
import json


class Command(BaseCommand):
    args = ''
    help = 'auto reboot'

    def handle(self, *args, **options):
        for app_obj in App.objects.filter(status=0, type=0):
            print app_obj.name
            url = settings.CMIS['PREFIX'] + settings.CMIS['JENKINS_API'] % app_obj.cmis_id
            code, result = httpcall2(url)
            if 200 <= code < 400:
                response = json.loads(result)['response']
                url_list = []
                for job in response:
                    if job['jobStatus'] == 0 and job['jobTypeId'] == 6:
                        url = job['jobUrl']
                        url_list.append(url)
                        owner = job['updateUserVo']['adAccount']
                        deploy_jenkins_job, created = DeployJenkinsJob.objects.get_or_create(
                            app=app_obj,
                            url=url,
                            defaults={
                                'owner': owner
                            }
                        )
                        if not created:
                            deploy_jenkins_job.owner = owner
                            deploy_jenkins_job.save()
                DeployJenkinsJob.objects.filter(app=app_obj).exclude(url__in=url_list).delete()
