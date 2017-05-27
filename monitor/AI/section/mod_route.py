# -*- coding: utf-8 -*-
import mod_machine


class ModRoute(object):
    go_map = {
        'hc_alarm': mod_machine.hc_convergence,
        'tomcat_alarm': mod_machine.tomcat_convergence,
        # 'server_alarm': mod_machine.process_convergence,
        'switch_alarm': mod_machine.switch_convergence,
        'ocean_alarm': mod_machine.ocean_convergence
    }

    def __init__(self):
        pass

    def route_mod(self, **kwargs):
        """路由到需要推送到哪个打标记模型"""
        tag = ''
        type_id = kwargs.get('type_id')
        source_id = kwargs.get('source_id')
        message = kwargs.get('message')

        if type_id == 7 and source_id == 6:
            tag = 'hc_alarm'
        elif source_id == 2 and message.find(u'tomcat挂') > -1:
            tag = 'tomcat_alarm'
        elif type_id == 5 and message.find(u'交换机') > -1:
            tag = 'switch_alarm'
        elif type_id == 7 and source_id == 12:
            tag = 'ocean_alarm'

        return self.go_map[tag](**kwargs) if tag in self.go_map else {'remark': '', 'tag': ''}

