# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from assetv2.settingsapi import FTP as MY_FTP
from ftplib import FTP

class Command(BaseCommand):
    args = ''
    help = 'auto load file from ftp'

    def handle(self, *args, **options):
        state = True
        try:
            ftp = FTP(MY_FTP['HOST'], MY_FTP['USER'], MY_FTP['PASSWORD'])
            ftp.dir()
        except Exception, e:
            state = False
            print('error:%s' % str(e))
        print('ftp state:%s' % state)
