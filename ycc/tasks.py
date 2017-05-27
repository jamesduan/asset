# -*- coding: utf-8 -*-
from __future__ import absolute_import
from assetv2.celeryapi import app as celery_app
from celery import shared_task
from ycc.models import ConfigPostInfoV2


@shared_task()
def config_post_info(client_ip, config_list):
    for config_dict in config_list:
        try:
            post_obj, created = ConfigPostInfoV2.objects.get_or_create(ip=client_ip, data_id=config_dict.get('data_id'), group_id=config_dict.get('group_id'))
            if not created:
                post_obj.save()
        except ConfigPostInfoV2.MultipleObjectsReturned:
            pass
