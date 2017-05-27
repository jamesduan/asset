# -*- coding: utf-8 -*-
import json
import datetime
from monitor.assemble.tools import http_request


class Judge(object):
    @staticmethod
    def __get_params(json_data):
        return {
            'level_id': int(json_data.get('level_id', 500)),
            'source_id': int(json_data.get('source_id', 0)),
            'message': json_data.get('message', '')
        }

    @staticmethod
    def is_tts(json_data):
        p = Judge.__get_params(json_data)
        # if p['message'].find('dinggo') > -1:
        #     return 1
        if p['source_id'] == 5 and p['level_id'] == 300:
            n = datetime.datetime.now()
            now = n.strftime("%Y%m%d")
            now_hour = n.strftime("%H")
            now_week = n.strftime("%w")
            jjr_api = "http://tool.bitefu.net/jiari/?d=" + now
            code, data = http_request(jjr_api)
            if code != 500:
                if data == '0' and (9 <= int(now_hour) <= 18):  # 工作日 0 休息日 1 节假日 2
                    return 0
                else:
                    return 1
            else:
                if (1 <= int(now_week) <= 5) and (9 <= int(now_hour) <= 18):
                    return 0
                else:
                    return 1
        else:
            return 0

    @staticmethod
    def get_BI_manager():
        url_api = "http://oms.yihaodian.com.cn/itil/api/?action=business&method=getBiContact"
        data = http_request(url_api)[1]
        return json.loads(data)

    @staticmethod
    def get_today_BI_manager():
        today = datetime.datetime.now()
        now = today.strftime('%d-') + today.strftime('%b').upper() + today.strftime('-%y')
        data = Judge.get_BI_manager()
        for i in data:
            if i.get('COUNT_DATE') == now:
                return i
        return {}