# -*- coding: utf-8 -*-
from rest_framework import generics
from serializers import *
from util.timelib import *
from rest_framework import status
from rest_framework.exceptions import APIException
from rest_framework import filters
from assetv2.settingsapi import HYBRID_CDS_REQUIRE
import json, urllib2


class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


class HybridRequirementList(generics.ListCreateAPIView):
    serializer_class = HybridRequirementSerializer
    queryset = HybridRequirement.objects.all().order_by("-id")

    filter_backends = (filters.SearchFilter, )
    search_fields = ('cname', 'machine_config', 'server_template')

    def perform_create(self, serializer):
        serializer.save(created=stamp2str(time.time()))


class HybridRequirementDetail1(generics.RetrieveUpdateAPIView):
    queryset = HybridRequirement.objects.all()
    serializer_class = HybridRequirementSerializer

    def perform_update(self, serializer):
        instance = serializer.save()
        if instance.idc == 'cds':
            post_data = {
                'template_type': instance.server_template,
                'model_type': instance.machine_config,
                'instances_num': instance.total
            }
            url = HYBRID_CDS_REQUIRE
            data = json.dumps(post_data)
            req = urllib2.Request(url, data)
            req.add_header("Accept", "application/json")
            req.add_header("Content-Type", "application/json")
            response = urllib2.urlopen(req)
            result = response.read()
            ret_data = json.loads(result)
            task_id = ret_data['task_id']
        else:
            raise YAPIException('hybrid can not support other IDC but else cds')

        instance.task_id = task_id
        instance.save()


class HybridRequirementDetailList(generics.ListAPIView):
    serializer_class = HybridRequirementDetailSerializer
    queryset = HybridRequirementDetail.objects.all().order_by("-id")
    filter_backends = (filters.SearchFilter, filters.DjangoFilterBackend)
    search_fields = ('ip', )
    filter_fields = ('status', 'requirement__id')


class HybridRequirementDetailDetail(generics.RetrieveUpdateAPIView):
    serializer_class = HybridRequirementDetailSerializer
    queryset = HybridRequirementDetail.objects.all()