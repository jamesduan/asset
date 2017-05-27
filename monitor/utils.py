# -*- coding: utf-8 -*-
import time
import re


def get_date(shijianchuo=0):
    if not shijianchuo:
        shijianchuo = time.time()
    return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(shijianchuo))


def cleanhtml(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext

