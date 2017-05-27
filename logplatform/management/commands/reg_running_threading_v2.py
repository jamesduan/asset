# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from logplatform.models import Reg, Log
from elasticsearch import Elasticsearch
import threading
import time
import requests


DB_ALIA = 'logplatform'


def get_index(start_time, end_time):
    # index_step_len = 60 * 60 * 24;
    # index_start_time = start_time
    # index_end_time = end_time
    indices = set()
    start_indstr = "accesslog-" + time.strftime("%Y.%m.%d", time.localtime(start_time))
    indices.add(start_indstr)
    end_indstr = "accesslog-" + time.strftime("%Y.%m.%d", time.localtime(end_time))
    indices.add(end_indstr)
    return ','.join(indices)


class Output(object):
    @staticmethod
    def save_to_log(kwargs_dict):
        print kwargs_dict
        l = Log(**kwargs_dict)
        l.save(using=DB_ALIA)


class EsProcess(object):
    es_flag = None

    def __init__(self):
        if not self.es_flag:
            try:
                self.es_flag = Elasticsearch([{'host': 'es.oms.yihaodian.com.cn', 'port': 80}])
            except Exception, e:
                print Exception, ": ", e

    def es_search(self, regs, is_test=0):
        _format_m = "%Y.%m.%d.%H.%M"
        today_str = time.strftime(_format_m, time.localtime())
        today_stamp_end = time.mktime(time.strptime(today_str, _format_m))
        # 开始时间下面处理

        if not regs:
            return None
        for reg in regs:
            _id = reg.id
            query = "type:haproxy AND " + reg.query
            interval_value = reg.interval_value  # 多少秒
            count = reg.count
            group_by = reg.group_by

            today_stamp_start = today_stamp_end - interval_value
            index = get_index(today_stamp_start, today_stamp_end-1)

            body = {
                "size": 0,
                "query": {
                    "bool": {
                        "must": [
                            {
                                "query_string": {
                                    "analyze_wildcard": True,
                                    "query": query
                                }
                            },
                            {
                                "range": {
                                    "@timestamp": {
                                        "gte": int(today_stamp_start*1000),
                                        "lte": int(today_stamp_end*1000-1),
                                        "format": "epoch_millis"
                                    }
                                }
                            }
                        ]
                    }
                },
                "aggs": {
                    "result": {
                        "terms": {
                            "field": group_by,
                            "size": 1000,
                            "min_doc_count": count
                        }
                    }
                }
            }

            try:
                result = self.es_flag.search(index=index, body=body)
                buckets = result['aggregations']['result']['buckets']
                if is_test:
                    return {"request": body, "response": result}
                else:
                    if buckets:
                        # 过滤5分钟tracker占比超过5%的ip
                        tracker_ips = ' '.join([item['key'] for item in buckets])
                        tracker_query = "type:haproxy AND access_ip:(" + tracker_ips + ")"

                        tracker_stamp_end = today_stamp_end
                        tracker_stamp_start = tracker_stamp_end - 60 * 5
                        tracker_index = get_index(tracker_stamp_start, tracker_stamp_end-1)

                        tracker_body = {
                            "size": 0,
                            "query": {
                                "bool": {
                                    "must": [
                                        {
                                            "query_string": {
                                                "analyze_wildcard": True,
                                                "query": tracker_query
                                            }
                                        },
                                        {
                                            "range": {
                                                "@timestamp": {
                                                    "gte": int(tracker_stamp_start * 1000),
                                                    "lte": int(tracker_stamp_end * 1000-1),
                                                    "format": "epoch_millis"
                                                }
                                            }
                                        }
                                    ]
                                }
                            },
                            "aggs": {
                                "result": {
                                    "terms": {
                                        "field": "access_ip",
                                        "size": 1000
                                    },
                                    "aggs": {
                                        "tracker": {
                                            "filters": {
                                                "filters": {
                                                    "tracker": {
                                                        "query_string": {
                                                            "query": "domain:tracker.yhd.com"
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }

                        tracker_result = self.es_flag.search(index=tracker_index, body=tracker_body)
                        ips = ''
                        for item in tracker_result['aggregations']['result']['buckets']:
                            percent = item['tracker']['buckets']['tracker']['doc_count']*100/item['doc_count']
                            if percent < 5:
                                ips += item['key'] + ','

                        if ips:
                            ips = ips[:-1]
                            content = "规则:"+query+", 时间(s):"+str(interval_value)+", 阀值:"+str(count)+", 防CC规则ID<"+str(_id)+">"
                            payload = {'ip': ips, 'content': content, 'operator': '防CC系统'}
                            print payload
                            r = requests.post("http://oms.yihaodian.com.cn/ipblock/api/?action=blacklist&method=bulk", data=payload)
                            print r.text

            except Exception, e:
                print Exception, ": ", e
                if is_test:
                    return {"request": body, "response": e}


class Command(BaseCommand):
    """
    获取reg表里的规则，执行防cc
    """
    args = ''
    help = 'run reg rules'
    thread_max_count = 5  # 多少个为一组线程,组之间并发

    type_map = {
        1: '防cc',
        2: 'others'
    }

    def get_reg(self):
        regs = Reg.objects.using(DB_ALIA).filter(enable=0, type=1)
        return regs

    def handle(self, *args, **options):
        regs = self.get_reg()
        # 根据type分类
        my_regs = {}
        i = 0
        k = 0
        for item in regs:
            if item:
                if i < self.thread_max_count:
                    i += 1
                else:
                    i = 1
                    k += 1
                my_regs.setdefault(k, []).append(item)

        if my_regs:
            threads = []
            p = EsProcess()
            for key in my_regs:
                threads.append(threading.Thread(target=p.es_search, args=(my_regs[key],)))
            for t in threads:
                t.setDaemon(False)
                t.start()


def test_my_reg(_id):
    """
    :description: 提供规则测试
    """
    regs = Reg.objects.using(DB_ALIA).filter(id=_id)

    p = EsProcess()
    return p.es_search(regs, 1)
