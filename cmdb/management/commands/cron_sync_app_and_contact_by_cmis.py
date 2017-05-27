# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from cmdb.utils import sync_by_cmis
from util.timelib import *

class Command(BaseCommand):
    args = ''
    help = 'sync app and contact info from cmis'

    def handle(self, *args, **options):
        response = sync_by_cmis.syn_appcontact()
        if response['success']:
            print stamp2str(time.time()) + ':success'
        else:
            print stamp2str(time.time()) + ':failure  info:' + response['msg']
