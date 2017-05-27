from rest_framework import serializers
from models import *


class ZoneSerializer(serializers.ModelSerializer):
    area_name = serializers.ReadOnlyField(source='area.name_cn')
    rack_total = serializers.ReadOnlyField()
    rack_blade_total = serializers.ReadOnlyField()
    rack_real_total = serializers.ReadOnlyField()
    parent_name = serializers.ReadOnlyField(source='parent.name')

    class Meta:
        model = Room
        fields = ('id', 'name', 'area_name', 'area', 'comment', 'points', 'ycc_code', 'zk_cluster', 'rack_total',
                  'rack_blade_total', 'rack_real_total', 'name_ch', 'ycc_display', 'parent_name', 'architecture_name')


class AssetTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetType
        fields = ('id', 'name', 'comment', 'short_name')


class AssetModelSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetModel
        fields = ('id', 'name', 'comment')


class IpSegmentSerializer(serializers.ModelSerializer):
    idc_name = serializers.ReadOnlyField(source='get_idc_display')
    type_name = serializers.ReadOnlyField(source='get_type_display')
    owner_name = serializers.ReadOnlyField(source='get_owner_display')

    class Meta:
        model = IpSegment
        fields = ('id', 'ip', 'type', 'type_name', 'mask', 'idc', 'idc_name', 'owner', 'owner_name', 'comment', 'status', 'created')

    # def get_idc(self, obj):
    #     return obj.get_idc_display()


class IpSerializer(serializers.HyperlinkedModelSerializer):

    #new
    idc_name = serializers.ReadOnlyField(source='get_idc_display')
    is_used_name = serializers.ReadOnlyField(source='get_is_used_display')
    is_virtual_name = serializers.ReadOnlyField(source='get_is_virtual_display')
    asset_type_name=serializers.ReadOnlyField(source='get_asset_type_display')
    # ipsegment = IpSegmentSerializer(many=True, read_only=True)
    ipsegment_owner = serializers.ReadOnlyField(source='ipsegment.get_owner_display')
    ipsegment_owner_number = serializers.ReadOnlyField(source='ipsegment.owner')
    room_comment = serializers.ReadOnlyField(source='room.comment')
    #room_id = serializers.ReadOnlyField(source='room.id')
    #ipsegment=serializers.ReadOnlyField()
    #new
    class Meta:
        model = IpTotal
        fields = ('id', 'idc','idc_name', 'type', 'ip_segment_id', 'ip', 'asset_type','asset_type_name', 'asset_info', 'business_info', 'is_used','is_used_name',
                  'is_virtual','is_virtual_name', 'status', 'room_comment','ipsegment_owner','ipsegment_owner_number')

class IpSerializer2(serializers.HyperlinkedModelSerializer):

    #new
    idc_name = serializers.ReadOnlyField(source='get_idc_display')
    is_used_name = serializers.ReadOnlyField(source='get_is_used_display')
    is_virtual_name = serializers.ReadOnlyField(source='get_is_virtual_display')
    asset_type_name=serializers.ReadOnlyField(source='get_asset_type_display')
    # ipsegment = IpSegmentSerializer(many=True, read_only=True)
    ipsegment_owner = serializers.ReadOnlyField(source='ip_segment.get_owner_display')
    ip_segment_number = serializers.ReadOnlyField(source='ip_segment.owner')
    room_comment = serializers.ReadOnlyField(source='room.comment')
    #room_id = serializers.ReadOnlyField(source='room.id')
    #ipsegment=serializers.ReadOnlyField()
    #new
    class Meta:
        model = IpTotal2
        fields = ('id', 'idc','idc_name', 'type', 'ip', 'asset_type','asset_type_name', 'asset_info', 'business_info', 'is_used','is_used_name',
                  'is_virtual','is_virtual_name', 'status', 'room_comment','ipsegment_owner','ip_segment_number')
    # def get_ipsegment(self, obj):
    #     request_type = self.context['request'].QUERY_PARAMS['type']
    #     ipsegment_ins = IpSegment.objects.filter(type=int(request_type))
    #     for item in ipsegment_ins:
    #         print item.id
    #     serializer = IpSegmentSerializer(instance=ipsegment_ins, many=True)
    #     return serializer.data


class RackSerializer(serializers.ModelSerializer):
    real_name = serializers.ReadOnlyField()
    type_name = serializers.ReadOnlyField(source='get_valid_display')
    room_name = serializers.StringRelatedField(source='room.name')

    class Meta:
        model = Rack
        fields = ('id', 'name', 'real_name', 'room', 'room_name', 'height', 'valid', 'type_name', 'comment', 'ip_min', 'ip_max')


class RackSpaceSerializer(serializers.ModelSerializer):

    class Meta:
        model = RackSpace
        fields = ('id', 'rack_id', 'unit_no', 'assetid')


class AssetSerializer(serializers.ModelSerializer):
    #asset_model = serializers.SlugRelatedField(slug_field='name', read_only='true')
    #asset_type = serializers.SlugRelatedField(slug_field='comment', read_only='true')
    #asset_model = serializers.StringRelatedField()
    #asset_type = serializers.StringRelatedField()
    #rack = serializers.StringRelatedField()
    #rack_real_name = serializers.ReadOnlyField(source='rack.real_name', read_only='true')
    idc = serializers.ReadOnlyField(source='rack.room.name')
    asset_type_name = serializers.ReadOnlyField(source='asset_type.comment')
    asset_model_name = serializers.ReadOnlyField(source='asset_model.name')
    rack_name = serializers.ReadOnlyField(source='rack.name')
    ip_info = IpSerializer(many=True, read_only=True)
    status_name = serializers.ReadOnlyField(source='get_new_status_display')
    rack_space = RackSpaceSerializer(many=True, read_only=True)
    class Meta:
        model = Asset
        fields = ('id', 'service_tag', 'mac', 'assetid', 'asset_type', 'asset_type_name', 'rack','rack_name', 'rack_space', 'idc',
                  'asset_model', 'asset_model_name', 'expiration_time' ,'create_time', 'last_modified', 'ip_info',
                  'new_status', 'status_name', 'comment')


class AssetRepairSerializer(serializers.ModelSerializer):
    type_name = serializers.ReadOnlyField(source='get_type_display')
    assetid = serializers.ReadOnlyField(source='asset.assetid')
    sn = serializers.ReadOnlyField(source='asset.service_tag')
    idc = serializers.ReadOnlyField(source='asset.rack.room.name')
    rack_name = serializers.ReadOnlyField(source='asset.rack.real_name')

    class Meta:
        model = AssetRepair
        fields = ('id', 'asset', 'assetid', 'sn', 'idc', 'rack_name', 'type', 'type_name', 'reson_user', 'reson', 'reson_time', 'result_user',
        'result', 'result_time')