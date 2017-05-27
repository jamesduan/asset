# -*- coding: utf-8 -*-
import time


def stamp2str(stamp, formt='%Y-%m-%d %H:%M:%S'):
    if not stamp:
        return None
    stamp = int(stamp)
    return time.strftime(formt, time.localtime(stamp))


def str2stamp(tstr, formt='%Y%m%d'):
    if not tstr: return None
    return int(time.mktime(time.strptime(tstr, formt)))

def stamp2datestr(stamp, formt='%Y-%m-%d'):
    if not stamp:
        return None
    stamp = int(stamp)
    return time.strftime(formt, time.localtime(stamp))

def timelength_format(startstamp, endstamp, unit='s'):
    if startstamp and endstamp:
        seconds = endstamp - startstamp
        day = int(round(seconds / 86400))
        hour = int(round(seconds / 3600)) - day *24
        minute = int(round(seconds / 60)) - day *24*60 - hour * 60
        sec = seconds - day *86400 - hour * 3600 - minute * 60
        res = ''
        if unit == 's':
            if seconds <= 0:
                return '0秒'
            if day:
                res += str(day) +'天'
            if hour:
                res += str(hour) +'小时'
            if minute:
                res += str(minute) +'分'
            if sec:
                res += str(sec) + '秒'
            return res
        elif unit == 'm':
            if seconds <= 0:
                return '0分'
            if day:
                res += str(day) +'天'
            if hour:
                res += str(hour) +'小时'
            if minute or sec:
                if sec:
                    minute += 1
                res += str(minute) +'分'
            return res
        else:
            return '最小输出单位非法，只能精确到秒（s）或分（m）！'
    else:
        return ''

