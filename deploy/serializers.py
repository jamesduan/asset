from rest_framework import serializers
from deploy.models import *
from django.conf import settings
from cmdb.serializers import AppSerializer

class DeployVersionAppSerializer(serializers.ModelSerializer):
    site_id = serializers.ReadOnlyField(source='app.site.id')
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_id = serializers.ReadOnlyField(source='app.id')
    app_name = serializers.ReadOnlyField(source='app.name')
    pack_type = serializers.ReadOnlyField()
    ftp_path = serializers.ReadOnlyField()

    class Meta:
        model = DeployVersionApp
        fields = ('id', 'site_id', 'site_name', 'app_id', 'app_name', 'app_env_name', 'app_version', 'ftp_path', 'pack_type', 'created_time', 'updated_time')


class DeployMainSerializer(serializers.ModelSerializer):
    depid = serializers.ReadOnlyField()
    jiraid = serializers.ReadOnlyField()
    username = serializers.ReadOnlyField(source='user.username')
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    restart = serializers.ReadOnlyField()
    last_modified = serializers.ReadOnlyField()
    publishdatetimefrom = serializers.ReadOnlyField()
    publishdatetimeto = serializers.ReadOnlyField()
    comment = serializers.ReadOnlyField()
    gray_status = serializers.ReadOnlyField()
    gray_release_info = serializers.ReadOnlyField()
    gray_stage_interval = serializers.ReadOnlyField()
    colony_surplus = serializers.ReadOnlyField()
    recover_time = serializers.ReadOnlyField()
    gray_rollback_type_name = serializers.ReadOnlyField()
    app_id = serializers.ReadOnlyField()
    pre_deploy_progress = serializers.ReadOnlyField()
    deploy_progress = serializers.ReadOnlyField()
    rollback_progress = serializers.ReadOnlyField()

    class Meta:
        model = DeployMain
        fields = ('depid', 'jiraid', 'username', 'site_name', 'app_name', 'deptype_name', 'packtype_name', 'restart',
                  'last_modified', 'publishdatetimefrom', 'publishdatetimeto', 'status_name', 'comment', 'status',
                  'gray_status', 'gray_release_info', 'gray_stage_interval', 'colony_surplus', 'recover_time',
                  'gray_rollback_type_name', 'app_id', 'in_progress', 'is_gray_release', 'valid', 'create_time',
                  'restart_interval', 'signal', 'deploy_progress', 'rollback_progress', 'pre_deploy_progress')


class DeployDetailSerializer(serializers.ModelSerializer):
    room_name = serializers.ReadOnlyField(source='room.comment')

    class Meta:
        model = DeployDetail
        fields = ('host', 'is_source', 'has_backup', 'backup_time', 'has_pre', 'pre_time', 'has_real', 'real_time',
                  'has_rollback', 'rollback_time', 'has_error', 'complete', 'room_name', 'gray_stage')


class DeployRollbackReasonSerializer(serializers.ModelSerializer):
    category_name = serializers.ReadOnlyField(source='get_category_display')
    uid_name = serializers.ReadOnlyField(source='uid.username')
    class Meta:
        model = DeployRollbackReason
        fields = ('id', 'uid', 'uid_name', 'depid', 'verifier', 'reason', 'created', 'category', 'category_name')


class DeployMainConfigSerializer(serializers.ModelSerializer):
    depid = serializers.ReadOnlyField()
    jiraid = serializers.ReadOnlyField()
    username = serializers.ReadOnlyField(source='user.username')
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    restart = serializers.ReadOnlyField()
    last_modified = serializers.ReadOnlyField()
    publishdatetimefrom = serializers.ReadOnlyField()
    publishdatetimeto = serializers.ReadOnlyField()
    comment = serializers.ReadOnlyField()
    app_id = serializers.ReadOnlyField()
    gray_release_info = serializers.ReadOnlyField()
    gray_stage_interval = serializers.ReadOnlyField()
    colony_surplus = serializers.ReadOnlyField()
    recover_time = serializers.ReadOnlyField()
    gray_rollback_type = serializers.ReadOnlyField()
    config = serializers.ReadOnlyField()

    class Meta:
        model = DeployMainConfig
        fields = ('depid', 'jiraid', 'username', 'site_name', 'app_name', 'idc_name', 'restart', 'last_modified',
                  'publishdatetimefrom', 'publishdatetimeto', 'status_name', 'comment', 'status', 'app_id',
                  'gray_release_info', 'gray_stage_interval', 'colony_surplus', 'recover_time', 'gray_rollback_type',
                  'config', 'in_progress', 'deploy_progress', 'rollback_progress')


class DeployDetailConfigSerializer(serializers.ModelSerializer):
    room_name = serializers.ReadOnlyField(source='room.comment')
    ip = serializers.ReadOnlyField(source='server.ip')

    class Meta:
        model = DeployDetailConfig
        fields = ('ip', 'real_time', 'rollback_time', 'room_name')


class DeployTicketCelerySerializer(serializers.ModelSerializer):
    class Meta:
        model = DeployTicketCelery
        fields = ('ticket_id', 'celery_task_id', 'percent')

class DeployLogSerializer(serializers.ModelSerializer):
    create_time_str = serializers.ReadOnlyField()

    class Meta:
        model = DeployLog
        fields = ('id', 'depid', 'host', 'error', 'log', 'create_time', 'create_time_str')

class Deployv3StgMainSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    created_time = serializers.ReadOnlyField()
    status_name = serializers.ReadOnlyField()
    deploy_type_name = serializers.ReadOnlyField()

    class Meta:
        model = Deployv3StgMain
        fields = ('id', 'depid', 'uid', 'site_id', 'site_name', 'app_id', 'app_name', 'deploy_type', 'status', 'source_path', 'version', 'is_restart', 'bz', 'created', 'success_update', 'rollback_update', 'is_process', 'process', 'is_autocreated', 'created_time', 'status_name', 'deploy_type_name')

class Deployv3DetailSerializer(serializers.ModelSerializer):

    class Meta:
        model = Deployv3Detail
        fields = ('depid', 'target_host', 'deploy_host')

class Deployv3StgDetailSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    created_time = serializers.ReadOnlyField()
    success_time = serializers.ReadOnlyField()
    rollback_time = serializers.ReadOnlyField()
    status_name = serializers.ReadOnlyField()
    deploy_type_name = serializers.ReadOnlyField()
    bz_safe = serializers.ReadOnlyField()
    detail = Deployv3DetailSerializer(many=True, read_only=True)
    logs = DeployLogSerializer(many=True, read_only=True)

    class Meta:
        model = Deployv3StgMain
        fields = ('id', 'depid', 'uid', 'site_id', 'site_name', 'app_id', 'app_name', 'deploy_type', 'status', 'source_path', 'version', 'is_restart', 'bz', 'created', 'success_update', 'rollback_update', 'is_process', 'process', 'is_autocreated', 'created_time', 'rollback_time', 'success_time', 'status_name', 'deploy_type_name', 'bz_safe', 'logs', 'detail')


class JenkinsJobListSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeployJenkinsJob
        fields = ('app', 'url')


class DeployPathSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')

    class Meta:
        model = DeployPath
        fields = ('id', 'app_id', 'name', 'path', 'site_name', 'app_name')


class DeployFtpSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    ftp = serializers.HiddenField(default=settings.FTP['HOST'])
    user = serializers.HiddenField(default=settings.FTP['USER'])
    passwd = serializers.HiddenField(default=settings.FTP['PASSWORD'])

    class Meta:
        model = DeployFtp
        fields = ('id', 'app_id', 'path', 'path', 'site_name', 'app_name', 'ftp', 'user', 'passwd')


class HudsonJobSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    jobtype_name = serializers.ReadOnlyField(source='get_jobtype_display')

    class Meta:
        model = HudsonJob
        fields = ('id', 'app_id', 'jobtype', 'name', 'url', 'token', 'site_name', 'app_name', 'jobtype_name')

class DeployProcessPatternSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    class Meta:
        model = DeployProcessPattern
        fields = ('id', 'app','pattern','site_name','app_name')

class Deployv3StgMaxtimeSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='app.site.name')
    app_name = serializers.ReadOnlyField(source='app.name')
    deploy_type_name = serializers.ReadOnlyField()

    class Meta:
        model = Deployv3StgMaxtime
        fields = ('id', 'app', 'deploy_maxtime', 'deploy_type', 'site_name', 'app_name', 'deploy_type_name')