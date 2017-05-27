from django.core.management.base import BaseCommand, CommandError
import urllib2, datetime

class Command(BaseCommand):
    def handle(self, *args, **options):
        print 'test domain_validate.py'
        # ip = '10.4.1.249'
        # url = "http://10.4.1.249/cmdb/dns/api/domain_validate?zone_id=32&owner=9"
        # fp = urllib2.urlopen(url)
        # print datetime.datetime.now(), fp.read()
        # url = "http://10.4.1.249/cmdb/dns/api/domain_sync?zone_id=31&owner=9"
        # fp = urllib2.urlopen(url)
        # print datetime.datetime.now(), fp.read()

