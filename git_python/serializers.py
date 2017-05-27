from rest_framework import serializers
from git_python.models import *


class GitBootShAppSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    app_id = serializers.ReadOnlyField(source='app.id')

    class Meta:
        model = GitBootShApp
        fields = ('site_name', 'app_name', 'app_id', 'app')


class GitAppSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    type_name = serializers.ReadOnlyField(source='type.name')
    room_name = serializers.ReadOnlyField(source='room.name')
    created_by_name = serializers.ReadOnlyField(source='created_by.username')

    class Meta:
        model = GitApp
        fields = ('id', 'site_name', 'app_name', 'app', 'type', 'room', 'type_name', 'room_name', 'created_by_name', 'valid')
