# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand
from logplatform.models import Reg
from elasticsearch import Elasticsearch
import time
import json


class EsProcess(object):
    es_flag = None

    def __init__(self):
        if not self.es_flag:
            try:
                self.es_flag = Elasticsearch([{'host': '10.4.11.83', 'port': 9200}])
            except Exception, e:
                print Exception, ": ", e

    def es_search(self, regs, is_test=0):
        _format_h = "%Y.%m.%d.%H"
        _format_m = "%Y.%m.%d.%H.%M"
        today_str = time.strftime(_format_m, time.localtime())
        today_stamp_end = time.mktime(time.strptime(today_str, _format_m))
        today_stamp_index = today_stamp_end - 3600*8
        # 开始时间下面要处理的
        today_stamp_start = today_stamp_end
        if not regs:
            return None
        for reg in regs:
            title = reg.title
            query = json.loads(reg.query) if reg.query else None
            interval_value = reg.interval_value  # 多少秒
            comparison = reg.comparison
            count = reg.count
            group_by = reg.group_by

            today_stamp_start -= interval_value
            index = "accesslog-" + time.strftime(_format_h, time.localtime(today_stamp_index))

            # 生成query
            query_str = ""
            for i in query:
                key = i.get('key', None)
                operator = i.get('operator', None)
                value = i.get('value', None)
                if query_str:
                    query_str += " AND "
                if operator == "=":
                    query_str += key + ":" + "%s" % value
                elif operator == "reg":
                    query_str += key + ":/" + value.replace('/', "\\/") + "/"

            body = {
                "size": 0,
                "query": {
                    "filtered": {
                        "query": {
                            "query_string": {
                                "analyze_wildcard": True,
                                "query": query_str
                            }
                        },
                        "filter": {
                            "bool": {
                                "must": [
                                    {
                                        "range": {
                                            "@timestamp": {
                                                "gte": int(today_stamp_start*1000),
                                                "lte": int(today_stamp_end*1000),
                                                "format": "epoch_millis"
                                            }
                                        }
                                    }
                                ]
                            }
                        }
                    }
                },
                "aggs": {
                    "result": {
                        "terms": {
                            "field": group_by,
                            "size": 0,
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
            except Exception, e:
                print Exception, ": ", e
                if is_test:
                    return {"request": body, "response": e}


class Output(object):
    def p(self):
        print 111


class Command(BaseCommand):
    """
    获取reg表里的规则，执行防cc
    """
    args = ''
    help = 'run reg rules'
    DB_ALIA = 'logplatform'

    type_map = {
        1: '防cc',
        2: 'others'
    }

    def get_reg(self):
        regs = Reg.objects.using(self.DB_ALIA).filter(enable=0)
        return regs

    def handle(self, *args, **options):
        regs = self.get_reg()
        # 根据type分类
        my_regs = {}
        for item in regs:
            my_regs.setdefault(item.type, []).append(item)

        p = EsProcess()
        p.es_search(my_regs[1])


def test_my_reg(_id):
    """
    :description: 提供规则测试
    """
    DB_ALIA = 'logplatform'
    regs = Reg.objects.using(DB_ALIA).filter(id=_id)

    p = EsProcess()
    return p.es_search(regs, 1)