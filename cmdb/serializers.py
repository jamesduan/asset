from rest_framework import serializers
from models import *

class SiteSerializer(serializers.ModelSerializer):
    app_total = serializers.ReadOnlyField()

    class Meta:
        model = Site
        fields = ('id', 'cmis_id', 'name', 'app_total', 'comment', 'created')


class SiteV2Serializer(serializers.ModelSerializer):

    class Meta:
        model = Site
        fields = ('id', 'cmis_id', 'name', 'comment', 'created')


class AppSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.name')
    type_name = serializers.ReadOnlyField(source='get_type_display')
    groups = serializers.ReadOnlyField()
    #new
    domain_name = serializers.ReadOnlyField(source='domain.domainname')
    DL = serializers.ReadOnlyField(source='domain.domainleaderaccount')
    DL_tel = serializers.ReadOnlyField(source='domain.telephone.telephone')
    Backup_DL = serializers.ReadOnlyField(source='domain.backupdomainleaderaccount')
    Backup_DL_tel = serializers.ReadOnlyField(source='domain.backuptelephone.telephone')
    department_name = serializers.ReadOnlyField(source='domain.departmentname')
    department_leader = serializers.ReadOnlyField(source='domain.department.deptleaderaccount')
    department_leader_tel = serializers.ReadOnlyField(source='domain.department.telephone.telephone')
    server_total = serializers.ReadOnlyField()
    sre= serializers.ReadOnlyField(source='appcontact.sa_user')
    sre_no= serializers.ReadOnlyField(source='appcontact.sa_no')
    sre_backup=serializers.ReadOnlyField(source='appcontact.sa_backup_user')
    sre_backup_no=serializers.ReadOnlyField(source='appcontact.sa_backup_no')
    domain_email = serializers.ReadOnlyField(source='domain.domainemailgroup')
    class Meta:
        model = App
        fields = ('id', 'cmis_id', 'cmis_site_id', 'name', 'site_id', 'site_name', 'type', 'type_name', 'level',
                  'hudson_job', 'comment', 'ctime', 'domainid', 'service_name', 'groups', 'domain_name','department_name',
                  'DL','DL_tel','Backup_DL','Backup_DL_tel','department_leader','department_leader_tel', 'server_total','sre','sre_no','sre_backup','sre_backup_no','domain_email')


class AppWebSerializer(serializers.ModelSerializer):
    site_name = serializers.ReadOnlyField(source='site.name')
    type_name = serializers.ReadOnlyField(source='get_type_display')
    groups = serializers.ReadOnlyField()
    server_total = serializers.ReadOnlyField()
    server_stg_total = serializers.ReadOnlyField()
    server_pro_total = serializers.ReadOnlyField()
    JQ_pro_total = serializers.ReadOnlyField()
    NH_pro_total = serializers.ReadOnlyField()

    class Meta:
        model = AppWeb
        fields = ('id', 'cmis_id', 'cmis_site_id', 'name', 'site_id', 'site_name', 'type', 'type_name', 'level',
                  'hudson_job', 'comment', 'ctime', 'domainid', 'service_name', 'groups',
                  'server_total', 'server_stg_total','server_pro_total', 'JQ_pro_total', 'NH_pro_total')


class AppContactSerializer(serializers.ModelSerializer):
    app_level = serializers.ReadOnlyField(source='pool.level')
    app_id = serializers.CharField(source='pool_id')
    app_name = serializers.CharField(source='pool_name')
    app_comment = serializers.CharField(source='pool.comment')
    app_type = serializers.IntegerField(source='pool.type')
    server_total = serializers.ReadOnlyField()

    class Meta:
        model = AppContact
        fields = ('site_id', 'site_name', 'app_id', 'app_name', 'app_level', 'app_type', 'department_id', 'department',
                  'p_user', 'p_email', 'p_no', 'domain_email', 'sa_user', 'sa_email', 'sa_no', 'b_user',
                  'b_email', 'b_no', 'domain_id', 'domain_name', 'domain_code', 'sa_backup_user',
                  'sa_backup_email', 'sa_backup_no', 'head_user', 'head_email', 'head_no', 'app_comment', 'server_total')


class DdDepartmentSerializer(serializers.ModelSerializer):

    class Meta:
        model = DdDepartmentNew
        fields = ('id', 'deptcode', 'deptname', 'deptemailgroup', 'deptleaderaccount', 'deptlevel', 'pid')


class DdDomainSerializer(serializers.ModelSerializer):
    app = AppSerializer(many=True, read_only=True)
    #department_name = serializers.ReadOnlyField(source='department.deptName')
    department_leader = serializers.ReadOnlyField(source='department.deptleaderaccount')

    class Meta:
        model = DdDomain
        fields = ('id', 'domaincode', 'domainname', 'domainemailgroup', 'domainleaderaccount',
                  'backupdomainleaderaccount', 'departmentid', 'departmentname', 'department_leader', 'app')


class DdDomainV2Serializer(serializers.ModelSerializer):
    department_leader = serializers.ReadOnlyField(source='department.deptleaderaccount')
    departmentid = serializers.ReadOnlyField(source='department.id')
    departmentname = serializers.ReadOnlyField(source='department.deptname')
    department_level2 = DdDepartmentSerializer(read_only=True)

    class Meta:
        model = DdDomainV2
        fields = ('id', 'domaincode', 'domainname', 'domainemailgroup', 'domainleaderaccount',
                  'backupdomainleaderaccount', 'departmentid', 'departmentname', 'department_leader', 'department_level2')


class DdUsersSerializer(serializers.ModelSerializer):
    domains = DdDomainSerializer(many=True, read_only=True)

    class Meta:
        model = DdUsers
        fields = ('id', 'username', 'username_ch', 'display_name', 'email', 'domains','telephone')


class DdUsersV2Serializer(serializers.ModelSerializer):

    class Meta:
        model = DdUsers
        fields = ('id', 'username', 'username_ch', 'display_name', 'email', 'telephone')

class DdUsersDomainsSerializer(serializers.ModelSerializer):
    dddomain = DdDomainV2Serializer(read_only=True)
    ddusers = DdUsersV2Serializer(read_only=True)

    class Meta:
        model = DdUsersDomains
        fields = ('id', 'dddomain', 'ddusers')

class DdUsersDomainsforrotaSerializer(serializers.ModelSerializer):
    dddomain_id = serializers.ReadOnlyField(source='dddomain.id')
    dddomain_code = serializers.ReadOnlyField(source='dddomain.domaincode')
    dddomain_name = serializers.ReadOnlyField(source='dddomain.domainname')
    ddusers_id = serializers.ReadOnlyField(source='ddusers.id')
    ddusers_name = serializers.ReadOnlyField(source='ddusers.username')
    ddusers_display = serializers.ReadOnlyField(source='ddusers.display_name')
    class Meta:
        model = DdUsersDomains
        fields = ('dddomain_id', 'dddomain_code', 'dddomain_name','ddusers_id','ddusers_name','ddusers_display')

class ConfigDbInstanceSerializer(serializers.ModelSerializer):
    idc_name = serializers.ReadOnlyField(source='idc.name')

    class Meta:
        model = ConfigDbInstance

        fields = (
            'id', 'cname', 'dbname', 'db_type', 'username', 'password', 'instance_url', 'port', 'idc',
            'idc_name')
        # fields = (
        #     'id', 'cname', 'dbname', 'db_type', 'username', 'password', 'instance_url', 'port', 'instance_type', 'idc',
        #     'idc_name')


class ConfigDbInstanceFilterPasswordSerializer(serializers.ModelSerializer):
    idc_name = serializers.ReadOnlyField(source='idc.name')

    class Meta:
        model = ConfigDbInstance
        fields = (
            'id', 'cname', 'dbname', 'db_type', 'username', 'instance_url', 'port', 'instance_type', 'idc', 'idc_name')

class ConfigDbKvDefaultSerializer(serializers.ModelSerializer):

    class Meta:
        model = ConfigDbKvDefault
        fields = ('id', 'dbtype', 'jdbckey', 'jdbcval', 'jdbctype', 'jdbcdescribe')

class ConfigDbKvCustomSerializer(serializers.ModelSerializer):
    # jdbckey = serializers.ReadOnlyField(source='dbkv.jdbckey')
    # kv_id = serializers.ReadOnlyField(source='dbkv.id')
    # dbtype = serializers.ReadOnlyField(source='dbkv.dbtype')

    class Meta:
        model = ConfigDbKvCustom
        # fields = ('id', 'configinfo_id', 'kv_id', 'jdbcval', 'jdbckey', 'dbtype')
        fields = ('id', 'configinfo_id', 'dbtype', 'jdbckey', 'jdbcval', 'jdbctype')




class RotaSerializer(serializers.ModelSerializer):
    # duty_man_name =serializers.ReadOnlyField(source = 'duty_man.display_name')
    # duty_man_account =serializers.ReadOnlyField(source = 'duty_man.username')
    # duty_man_tel =serializers.ReadOnlyField(source = 'duty_man.telephone')
    # duty_backup_name =serializers.ReadOnlyField(source = 'duty_backup.display_name')
    # duty_backup_account =serializers.ReadOnlyField(source = 'duty_backup.username')
    # duty_backup_tel =serializers.ReadOnlyField(source = 'duty_backup.telephone')
    duty_man= DdUsersV2Serializer(many=True,read_only=True)
    duty_backup = DdUsersV2Serializer(many=True,read_only=True)
    duty_domain_name = serializers.ReadOnlyField(source = 'duty_domain.domainname')
    activity_name = serializers.ReadOnlyField(source = 'rota_activity.name')
    duty_way_name = serializers.ReadOnlyField(source = 'get_duty_way_display')
    duty_date_start_p = serializers.ReadOnlyField(source = 'shift_time.start')
    duty_date_end_p = serializers.ReadOnlyField(source = 'shift_time.end')
    department_3 = serializers.ReadOnlyField(source = 'duty_domain.departmentname')
    department_2 = serializers.ReadOnlyField(source = 'duty_domain.department_level2.deptname')
    class Meta:
        model = Rota
        # fields = ('id', 'duty_date_start','duty_date_end','duty_date_start_p','duty_date_end_p','promotion','shift_time','rota_activity','activity_name','duty_domain','duty_domain_name','duty_man','duty_man_name','duty_man_account','duty_way','duty_way_name','duty_backup','duty_backup_name','duty_backup_account','duty_man_tel','duty_backup_tel')
        fields = ('id', 'duty_date_start','duty_date_end','duty_date_start_p','duty_date_end_p','promotion','shift_time','rota_activity','activity_name','department_2','department_3','duty_domain','duty_domain_name','duty_man','duty_way','duty_way_name','duty_backup','comment')

class ShiftTimeSerializer(serializers.ModelSerializer):

    class Meta:
        model = ShiftTime
        fields = ('id','start','end','activity')

class DdDomainForaSerializer(serializers.ModelSerializer):

    class Meta:
        model = DdDomain
        fields = ('id', 'domaincode', 'domainname',)


class RotaActivitySerializer(serializers.ModelSerializer):
    domains = DdDomainForaSerializer(many=True,read_only=True)
    shift_times = ShiftTimeSerializer(many=True,read_only=True)
    promotion_display = serializers.ReadOnlyField(source='get_promotion_display')

    class Meta:
        model = RotaActivity
        fields = ('id','name','description','start_time','end_time','promotion','promotion_display','domains','shift_times')

class PooltoaclSerializer(serializers.ModelSerializer):

    class Meta:
        model =  Pooltoacl
        fields = ('ha_ip','acl_name','hdr','path_beg')

class AcltobackendSerializer(serializers.ModelSerializer):
    class Meta:
        model =  Acltobackend
        fields = ('backend_name',)


class AppV2Serializer(serializers.ModelSerializer):
    site = SiteV2Serializer()

    class Meta:
        model = AppV2
        fields = ('site', 'id', 'name', 'type', 'level', 'service_name')

class DailyDutyTimeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyDutyTime
        fields = ('starttime','addday','endtime','dailydutyconfig')

class DailyDutyConfigSerializer(serializers.ModelSerializer):
    domain_name = serializers.ReadOnlyField(source='domain.domainname')
    # dailydutytime=DailyDutyTimeSerializer(read_only=True)
    class Meta:
        model = DailyDutyConfig
        fields = ('domain','domain_name','dailyfrequency','cycle','startdate','startwday','entryintoforce')