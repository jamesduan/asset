# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
import requests
from util.httplib import get_api_auth
import time
from datetime import datetime, date


class Command(BaseCommand):
    utctime_start = None
    utctime_end = None
    today_str = None
    end_timestamp_ms = None

    def handle(self, *args, **options):
        fmt = "%Y-%m-%d %H:%M"
        end_str = time.strftime(fmt, time.localtime())
        end_timestamp = time.mktime(time.strptime(end_str, fmt))
        self.utctime_end = datetime.utcfromtimestamp(end_timestamp).isoformat()
        self.utctime_end = self.utctime_end + ".000Z"
        self.end_timestamp_ms = int(end_timestamp * 1000)
        start_timestamp = end_timestamp - 60
        self.utctime_start = datetime.utcfromtimestamp(start_timestamp).isoformat()
        self.utctime_start = self.utctime_start + ".000Z"

        self.today_str = time.strftime("%Y.%m.%d", time.localtime())

        self.monitor_status()
        self.monitor_applog()
        self.monitor_accesslog()


    def alarm(self, message):
        event_dict_v2 = {
            'title': 'ES集群监控告警',
            'level_id': 400,
            'type_id': 14,
            'source_id': 28,
            'pool_id': 1009,
            'message': message,
            'caller': '18616510579',
            'send_to': 'It_base_dev@yhd.com'
        }

        auth = get_api_auth("blockip", "j6RS9e8d")
        headers = {'Authorization': auth}
        r = requests.post("http://oms.yihaodian.com.cn/api/notification/event/", data=event_dict_v2, headers=headers)


    def monitor_status(self):
        r = requests.get("http://es.oms.yihaodian.com.cn/.monitoring-es-2-"+self.today_str+"/cluster_state/_search?q=timestamp:{"+self.utctime_start+"%20TO%20"+self.utctime_end+"]&sort=timestamp:desc")
        response_data = r.json()
        hits = response_data[u'hits'][u'hits']
        last_status = hits[0][u'_source'][u'cluster_state'][u'status']
        first_status = hits[-1][u'_source'][u'cluster_state'][u'status']

        if last_status != first_status:
            message = "ES status changed from [" + first_status + "] to [" + last_status + "]"
            self.alarm(message)


    def monitor_applog(self):
        r = requests.get("http://es.oms.yihaodian.com.cn/applog-" + self.today_str + "/_search?q=@timestamp:[" + self.utctime_start + "%20TO%20" + self.utctime_end + "}&size=0")
        response_data = r.json()
        total = response_data[u'hits'][u'total']

        if total < 10000:
            message = "applog 最近一分钟写入量小于10000条,请查看"
            self.alarm(message)


    def monitor_accesslog(self):
        start_timestamp_ms = self.end_timestamp_ms - 60 * 1000 * 12

        body = {
            "aggs": {
                "groupbydate": {
                    "date_histogram": {
                        "field": "@timestamp",
                        "interval": "1m",
                        "time_zone": "Asia/Shanghai",
                        "min_doc_count": 0,
                        "extended_bounds" : {
                            "min" : start_timestamp_ms,
                            "max" : self.end_timestamp_ms-1
                        }
                    }
                }
            }
        }

        r = requests.get("http://es.oms.yihaodian.com.cn/accesslog-" + self.today_str + "/_search?q=@timestamp:[" + str(start_timestamp_ms) + "%20TO%20" + str(self.end_timestamp_ms) + "}&size=0", json=body)
        response_data = r.json()

        list = []
        for bucket in response_data[u'aggregations'][u'groupbydate'][u'buckets']:
            list.append(bucket['doc_count'])

        last = list[-1]
        s_last = list[-2]
        if last < 100000:
            message = "accesslog 最近一分钟写入量小于100000条,请查看"
            self.alarm(message)
            return 0

        list = list[0:10]
        list.sort()
        list = list[1:9]
        avg = sum(list)/len(list)

        if last < avg*0.5 and s_last < avg*0.5:
            message = "accesslog 最近两分钟写入量环比降低50%,请查看"
            self.alarm(message)
            return 0
