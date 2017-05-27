# -*- coding: utf-8 -*-
__author__ = 'liuyating1'

from django.core.management.base import BaseCommand
from util.sendmail import sendmail_html

class Command(BaseCommand):
    args = ''
    help = 'test auto send mail'

    def handle(self, *args, **options):
        state = True
        try:
            sendmail_html(subject='test',
                          html_content='<h1>test</h1>',
                          recipient_list=['testsendmail@yhd.com'])
        except Exception, e:
            if "{u'testsendmail@yhd.com': (550, '5.1.1 User unknown')}" == str(e):
                pass
            else:
                print('error:%s' % str(e))
                state = False
        print('send mail function: %s' % state)