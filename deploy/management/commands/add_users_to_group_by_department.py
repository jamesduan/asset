# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from cmdb.models import DdDepartmentNew, DdDomain, DdUsers
from django.contrib.auth.models import User, Group
from django.conf import settings


class Command(BaseCommand):
    args = ''
    help = ''

    def handle(self, *args, **options):
        if len(args) < 2:
            print 'Invalid args'
            exit(1)
        group_name = args[0]
        group_id = settings.GROUP_ID.get(group_name)
        auth_group_obj = Group.objects.filter(id=group_id).first()
        if auth_group_obj is None:
            print 'Invalid group name'
            exit(1)
        for domain_code in args[1:]:
            for domain_obj in DdDomain.objects.filter(domaincode__istartswith=domain_code):
                for user_obj in domain_obj.ddusers_set.all():
                    auth_user_obj = User.objects.filter(username=user_obj.username).first()
                    if auth_user_obj and auth_group_obj not in auth_user_obj.groups.all():
                        auth_user_obj.groups.add(auth_group_obj)
                        print auth_user_obj.username, domain_obj.domainname

