# -*- coding: utf-8 -*-
from rest_framework import generics, status, filters
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from models import *
import time
import logging
from cmdb.models import DdUsers, Rota, RotaActivity, DdDepartmentNew, DdDomainV2
from django.db.models import Q
from datetime import datetime,timedelta
import json
from rest_framework.authtoken.models import Token
import ldap
from assetv2.settings_mobile import AUTH_LDAP_BIND_DN, AUTH_LDAP_BIND_PASSWORD, AUTH_LDAP_SERVER_URI
from mobile.models import AuthUser, SearchUserHistory
from django.contrib.auth.models import User
from mobile.permissions import AppPermission
from serializers import DdUsersSerializer, SearchUserHistorySerializer

logger = logging.getLogger('django.db.backends')


class YAPIException(APIException):
    def __init__(self, detail="未定义", status_code=status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code


@api_view(['POST'])
@permission_classes((AllowAny, ))
def mobile_login(request):
    username = request.POST.get('username', '')
    password = request.POST.get('password', '')
    if password == "":
        raise YAPIException("password empty")
    if username == "":
        raise YAPIException("username empty")
    usercheck = False
    try:
        ldap.set_option(ldap.OPT_REFERRALS, 0)
        conn = ldap.initialize(AUTH_LDAP_SERVER_URI)
        conn.simple_bind_s(AUTH_LDAP_BIND_DN, AUTH_LDAP_BIND_PASSWORD)
        searchFilter = '(sAMAccountName=' + str(username) + ')'
        ldap_result_id = conn.search('OU=1_UserAccount,DC=yihaodian,DC=com', ldap.SCOPE_SUBTREE, searchFilter, None)
        result_type, result_data = conn.result(ldap_result_id, 1)
        target_user = ''
        if len(result_data) > 0:
            r_a, r_b = result_data[0]
            target_user = r_b["distinguishedName"][0]
        if target_user == '':
            raise YAPIException("用户不存在")
    except ldap.LDAPError, err:
        raise YAPIException('Connect to %s failed, Error:%s.' % (AUTH_LDAP_SERVER_URI, err.message['desc']))
    try:
        conn.simple_bind_s(target_user, password)
        usercheck = True
    except ldap.LDAPError, err:
        raise YAPIException("密码错误，请重新输入")
    conn.unbind()
    del conn

    if usercheck:
        try:
            user = AuthUser.objects.get(username=username)
        except AuthUser.DoesNotExist:
            user = None
        try:
            auth_user = User.objects.get(username=username)
        except User.DoesNotExist:
            auth_user = None
        if user and auth_user and auth_user.is_active and user.is_app == 1:
            user_token, created = Token.objects.get_or_create(user=auth_user)
            data = {
                'success': True,
                'msg': {
                    'token': user_token.key,
                    'user_id': user_token.user_id
                }
            }
            return Response(status=status.HTTP_200_OK, data=data)
        else:
            return Response(status=status.HTTP_200_OK, data={"success": False, "msg": "用户无乐道APP权限"})
    else:
        return Response(status=status.HTTP_200_OK, data={"success": False, "msg": "用户不存在或密码错误"})

@api_view(['GET'])
@permission_classes((AppPermission, ))
def get_user(request):
    username = request.GET.get('username', '')
    if username == '':
        raise YAPIException('查询参数uesrname不能为空！')
    all_user = DdUsers.objects.using('default').filter(enable=0)
    user = None
    user_dict = {}
    for u in all_user:
        user_dict[u.username] = {
            'username_ch': u.username_ch,
            'telephone': u.telephone
        }
        if u.username == username:
            user = u
    if user is None:
        raise YAPIException('用户不存在！')
    dept = user.dept_level2
    domain_list = [{
                       'domainname': dm.domainname,
                       'domainleader': dm.domainleaderaccount,
                       'leaderdetail': user_dict[dm.domainleaderaccount] if user_dict.has_key(
                           dm.domainleaderaccount) else None
                   } for dm in user.domains.all()]
    result = {
        'username': user.username,
        'username_ch': user.username_ch,
        'telephone': user.telephone,
        'deptname': dept.deptname if dept else '',
        'deptleader': dept.deptleaderaccount if dept else '',
        'deptleaderdetail': user_dict[dept.deptleaderaccount] if dept and user_dict.has_key(
            dept.deptleaderaccount) else None,
        'domains': domain_list
    }
    return Response(status=status.HTTP_200_OK, data=result)


@api_view(['GET'])
@permission_classes((AppPermission, ))
def today_duty_activity(request):
    activity_id = int(request.GET.get('activity_id', 0))
    now = datetime.now()
    today = datetime(now.year, now.month, now.day, 0, 0, 0)
    tomorrow = today + timedelta(days=1)
    rotas = Rota.objects.using('default').filter(Q(duty_date_start__gte=today,duty_date_start__lt=tomorrow)|Q(duty_date_end__gt=today,duty_date_end__lte=tomorrow)|Q(duty_date_start__lte=today,duty_date_end__gte=tomorrow))
    if activity_id:
        domain_id = int(request.GET.get('domain_id', 0))
        dept_id = int(request.GET.get('dept_id', 0))
        deptv2_id = int(request.GET.get('deptv2_id', 0))
        try:
            activity = RotaActivity.objects.using('default').get(id=activity_id)
        except RotaActivity.DoesNotExist:
            raise YAPIException('ID为%s的活动不存在！' % activity_id)
        filters = {}
        filters['rota_activity__id'] = activity_id
        if domain_id:
            filters['duty_domain__id'] = domain_id
        elif dept_id:
            filters['duty_domain__departmentid'] = domain_id
        elif deptv2_id:
            depts_ids = [d.id for d in DdDepartmentNew.objects.using('default').filter(enable=0, pid=deptv2_id)]
            filters['duty_domain__departmentid__in'] = depts_ids
        rotas = rotas.filter(**filters)
        results = []
        for rota in rotas:
            results.append({
                'start_time': rota.duty_date_start.strftime('%m/%d %H:%M'),
                'end_time': rota.duty_date_end.strftime('%m/%d %H:%M'),
                'duty_domain': rota.duty_domain.domainname,
                'duty': ','.join([d.username_ch for d in rota.duty_man.all()]),
                'duty_backup': ','.join([b.username_ch for b in rota.duty_backup.all()]),
                'duty_way': rota.duty_way,
                'duty_way_name': rota.get_duty_way_display()
            })
        return Response(status=status.HTTP_200_OK, data={'activity': {
            'name': activity.name,
            'start_time': activity.start_time.strftime('%m/%d %H:%M'),
            'end_time': activity.end_time.strftime('%m/%d %H:%M'),
        },'results': results})
    else:
        activitys ={}
        all_count = 0
        for rota in rotas:
            activity = rota.rota_activity
            act_id = int(activity.id)
            if activity:
                all_count += 1
                d_u = [dict(name=user.username_ch, tel=user.telephone) for user in rota.duty_man.all()]
                duty_users = ', '.join([user.username_ch for user in rota.duty_man.all()])
                d_b_u = [dict(name=user.username_ch, tel=user.telephone) for user in rota.duty_backup.all()]
                duty_backup_users = ', '.join([user.username_ch for user in rota.duty_backup.all()])
                all_duty_users = [dict(name=user['name'] + ' ' + user['tel'], method=None) for user in dict((v['name'],v) for v in list(d_u + d_b_u)).values()]
                if activitys.has_key(act_id):
                    activitys[act_id]['count'] = activitys[act_id]['count'] + 1
                    activitys[act_id]['duty_detail'].append({
                        'start_time': rota.duty_date_start.strftime('%m/%d %H:%M'),
                        'end_time': rota.duty_date_end.strftime('%m/%d %H:%M'),
                        'duty_domain': rota.duty_domain.domainname,
                        # 'duty': ','.join([d.username_ch for d in rota.duty_man.all()]),
                        # 'duty_backup': ','.join([b.username_ch for b in rota.duty_backup.all()]),
                        'duty_users': duty_users,
                        'duty_backup_users': duty_backup_users,
                        'all_duty_users': all_duty_users,
                        'duty_way': rota.duty_way,
                        'duty_way_name': rota.get_duty_way_display()
                    })
                else:
                    activitys[act_id] = {
                        'id': act_id,
                        'name': activity.name,
                        'start_time': activity.start_time.strftime('%m/%d %H:%M'),
                        'end_time': activity.end_time.strftime('%m/%d %H:%M'),
                        'count': 1,
                        'duty_detail': [{
                            'start_time': rota.duty_date_start.strftime('%m/%d %H:%M'),
                            'end_time': rota.duty_date_end.strftime('%m/%d %H:%M'),
                            'duty_domain': rota.duty_domain.domainname,
                            'duty_users': duty_users,
                            'duty_backup_users': duty_backup_users,
                            'all_duty_users': all_duty_users,
                            # 'duty': ','.join([d.username_ch for d in rota.duty_man.all()]),
                            # 'duty_backup': ','.join([b.username_ch for b in rota.duty_backup.all()]),
                            'duty_way': rota.duty_way,
                            'duty_way_name': rota.get_duty_way_display()
                        }]
                    }
        results = [activitys[k] for k in activitys.keys()]
        # return Response(status=status.HTTP_200_OK, data={'all_count': all_count, 'results': results})
        return Response(status=status.HTTP_200_OK, data={'all_count': all_count,'results': results})


@api_view(['GET'])
@permission_classes((AllowAny, ))
def chart_realtime_order(request):
        #time = self.request.QYERY_PARAMS.get('time')
        etime= int(time.time())
        #etime = 1483495200
        stime = etime - 60*30
        c_etime = etime - 7*86400
        c_stime = c_etime - 60*30

        filters = dict()
        filters['create_time__gte'] = stime
        filters['create_time__lte'] = etime

        filters_c = dict()
        filters_c['create_time__gte'] = c_stime
        filters_c['create_time__lte'] = c_etime

        # 实时
        realtimeOrder = TOrderMin.objects.using('business').filter(**filters).order_by("create_time")
        # 对比
        c_realtimeOrder = TOrderMin.objects.using('business').filter(**filters_c).order_by("create_time")

        series_c_dict= dict()
        for point in c_realtimeOrder:
            series_c_dict[point.time_position] = point.order_count

        realtime = []
        series_reltime_data = []
        series_c_data = []
        for point in realtimeOrder:
            day_time = point.create_time/86400 * 86400 - 28800
            xAxis_time = time.strftime("%H:%M", time.localtime(day_time + point.time_position*60))
            realtime.append(xAxis_time)
            series_reltime_data.append(point.order_count)
            series_c_data.append(series_c_dict.get(point.time_position,0))

        chart_data = dict()
        chart_data['xAxis_data'] = realtime
        chart_data['realtime_data'] = series_reltime_data
        chart_data['com_data'] = series_c_data

        return Response(status=status.HTTP_200_OK, data=chart_data)


# @api_view(['GET'])
# @permission_classes((AllowAny, ))
# def find_user(request):
#     key = request.GET.get('key', '')
#     print key
#     user_list = DdUsers.objects.using('default').filter(enable=0)
#     if key:
#         user_list = user_list.filter(Q(username__contains=key) | Q(username_ch__contains=key) | Q(telephone__contains=key))
#     result = []
#     for user in user_list:
#         result.append({
#             'username': user.username,
#             'username_ch': user.username_ch,
#             'telephone': user.telephone,
#         })
#     return Response(status=status.HTTP_200_OK, data=result)
class HistoryUserList(generics.ListCreateAPIView):
    queryset = SearchUserHistory.objects.all().order_by('-id')
    serializer_class = SearchUserHistorySerializer
    filter_fields = ('owner_id', )
    search_fields = ('owner_id', )
    permission_classes = (AppPermission, )
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)

    def perform_create(self, serializer):
        user_id = int(self.request.DATA.get('user_id', 0))
        owner_id = int(self.request.DATA.get('owner_id', 0))

        if not user_id or not owner_id:
            raise YAPIException('param user_id not exists! please check your input parameters!')
        try:
            owner = AuthUser.objects.get(id=owner_id)
            dd_user = DdUsers.objects.get(id=user_id)
            serializer.save(dd_user = dd_user)
        except DdUsers.DoesNotExist:
            raise YAPIException("用户不存在!请重新选择!")

class UsersList(generics.ListAPIView):
    """
    基础用户表.

    输入参数：

    *

    输出参数：

    * id                -   PK
    * username          -   域控账号
    * display_name      -   展示名称
    * email             -   域控邮箱
    * domains           -   所属domain
    """
    queryset = DdUsers.objects.filter(enable=0)
    serializer_class = DdUsersSerializer
    filter_fields = ('username', 'domains')
    search_fields = ('username', 'username_ch', 'telephone')
    filter_backends = (filters.DjangoFilterBackend, filters.SearchFilter)

    def get_queryset(self):
        queryset =  DdUsers.objects.filter(enable=0)
        key = self.request.GET.get('key',None).lower()

        if key:
            queryset = queryset.filter(Q(username__contains = key)|Q(username_ch__contains = key)|Q(telephone__contains = key))
        return queryset

@api_view(['GET'])
@permission_classes((AllowAny, ))
def find_return_user(request):
    username = request.GET.get('username', '')
    if username == '':
        raise YAPIException('查询参数uesrname不能为空！')
    all_user = DdUsers.objects.using('default').filter(enable=0)
    user = None
    user_dict = {}
    for u in all_user:
        user_dict[u.username] = {
            'username_ch': u.username_ch,
            'telephone': u.telephone
        }
        if u.username == username:
            user = u
    if user is None:
        raise YAPIException('用户不存在！')
    dept = user.dept_level2
    domain_list = [{
        'domainname': dm.domainname,
        'domainleader': dm.domainleaderaccount,
        'leaderdetail': user_dict[dm.domainleaderaccount] if user_dict.has_key(dm.domainleaderaccount) else None
                   } for dm in user.domains.all()]
    result = {
        'username': user.username,
        'username_ch': user.username_ch,
        'telephone': user.telephone,
        'deptname': dept.deptname if dept else '',
        'deptleader': dept.deptleaderaccount if dept else '',
        'deptleaderdetail': user_dict[dept.deptleaderaccount] if dept and user_dict.has_key(dept.deptleaderaccount) else None,
        'domains': domain_list
    }
    return Response(status=status.HTTP_200_OK, data=result)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def today_duty_info(request):
    activity_id = int(request.GET.get('activity_id', 0))
    now = datetime.now()
    today = datetime(now.year, now.month, now.day, 0, 0, 0)
    tomorrow = today + timedelta(days=1)
    rotas = Rota.objects.using('default').filter(Q(duty_date_start__gte=today,duty_date_start__lt=tomorrow)|Q(duty_date_end__gt=today,duty_date_end__lte=tomorrow)|Q(duty_date_start__lte=today,duty_date_end__gte=tomorrow))
    if activity_id:
        domain_id = int(request.GET.get('domain_id', 0))
        dept_id = int(request.GET.get('dept_id', 0))
        deptv2_id = int(request.GET.get('deptv2_id', 0))
        try:
            activity = RotaActivity.objects.using('default').get(id=activity_id)
        except RotaActivity.DoesNotExist:
            raise YAPIException('ID为%s的活动不存在！' % activity_id)
        filters = {}
        filters['rota_activity__id'] = activity_id
        if domain_id:
            filters['duty_domain__id'] = domain_id
        elif dept_id:
            filters['duty_domain__departmentid'] = domain_id
        elif deptv2_id:
            depts_ids = [d.id for d in DdDepartmentNew.objects.using('default').filter(enable=0, pid=deptv2_id)]
            filters['duty_domain__departmentid__in'] = depts_ids
        rotas = rotas.filter(**filters)
        results = []
        for rota in rotas:
            results.append({
                'start_time': rota.duty_date_start.strftime('%m/%d %H:%M'),
                'end_time': rota.duty_date_end.strftime('%m/%d %H:%M'),
                'duty_domain': rota.duty_domain.domainname,
                'duty': ','.join([d.username_ch for d in rota.duty_man.all()]),
                'duty_backup': ','.join([b.username_ch for b in rota.duty_backup.all()]),
                'duty_way': rota.duty_way,
                'duty_way_name': rota.get_duty_way_display()
            })
        return Response(status=status.HTTP_200_OK, data=json.dumps({'activity': {
            'name': activity.name,
            'start_time': activity.start_time.strftime('%m/%d %H:%M'),
            'end_time': activity.end_time.strftime('%m/%d %H:%M'),
        },'results': results}))
    else:
        activitys ={}
        all_count = 0
        for rota in rotas:
            activity = rota.rota_activity
            act_id = int(activity.id)
            if activity:
                all_count += 1
                if activitys.has_key(act_id):
                    activitys[act_id]['count'] = activitys[act_id]['count'] + 1
                    activitys[act_id]['duty_detail'].append({
                        'start_time': rota.duty_date_start.strftime('%m/%d %H:%M'),
                        'end_time': rota.duty_date_end.strftime('%m/%d %H:%M'),
                        'duty_domain': rota.duty_domain.domainname,
                        'duty': ','.join([d.username_ch for d in rota.duty_man.all()]),
                        'duty_backup': ','.join([b.username_ch for b in rota.duty_backup.all()]),
                        'duty_way': rota.duty_way,
                        'duty_way_name': rota.get_duty_way_display()
                    })
                else:
                    activitys[act_id] = {
                        'id': act_id,
                        'name': activity.name,
                        'start_time': activity.start_time.strftime('%m/%d %H:%M'),
                        'end_time': activity.end_time.strftime('%m/%d %H:%M'),
                        'count': 1,
                        'duty_detail': [{
                            'start_time': rota.duty_date_start.strftime('%m/%d %H:%M'),
                            'end_time': rota.duty_date_end.strftime('%m/%d %H:%M'),
                            'duty_domain': rota.duty_domain.domainname,
                            'duty': ','.join([d.username_ch for d in rota.duty_man.all()]),
                            'duty_backup': ','.join([b.username_ch for b in rota.duty_backup.all()]),
                            'duty_way': rota.duty_way,
                            'duty_way_name': rota.get_duty_way_display()
                        }]
                    }
        results = [activitys[k] for k in activitys.keys()]
        # return Response(status=status.HTTP_200_OK, data={'all_count': all_count, 'results': results})
        return Response(status=status.HTTP_200_OK, data=json.dumps({'all_count': all_count,'results': results}))


@api_view(['GET'])
@permission_classes((AllowAny, ))
def deptv2_domains(request):
    domain_list = DdDomainV2.objects.using('default').filter(enable=0)
    deptv2_list = DdDepartmentNew.objects.using('default').filter(deptlevel=2, enable=0)
    dept_domain_list = []
    all_domains = []
    all_domains.append({
        'value': 0,
        'text': '---所有Domain---'
    })
    for dm in domain_list:
        all_domains.append({
            'value': dm.id,
            'text': dm.domainname
        })
    dept_domain_list.append({
        'value': 0,
        'text': '---所有部门---',
        'children': all_domains
    })
    for deptv2 in deptv2_list:
        domains = [{
            'value': 0,
            'text': '---所有部门---'
        }]
        for dm in domain_list:
            dept = dm.department
            if dept.pid == deptv2.id:
                domains.append({
                    'value': dm.id,
                    'text': dm.domainname
                })
            elif dm.department_id == deptv2.id:
                domains.append({
                    'value': dm.id,
                    'text': dm.domainname
                })
        dept_domain_list.append({
            'value': deptv2.id,
            'text': deptv2.deptname,
            'children': domains
        })
    return Response(status=status.HTTP_200_OK, data=dept_domain_list)


@api_view(['GET'])
@permission_classes((AllowAny, ))
def deptv2_dept_domains(request):
    domain_list = DdDomainV2.objects.using('default').filter(enable=0)
    deptv2_list = DdDepartmentNew.objects.using('default').filter(deptlevel=2, enable=0)
    deptv3_list = DdDepartmentNew.objects.using('default').filter(deptlevel=3, enable=0)

    all_domains = [{
        'value': 0,
        'text': '---所有Domain---'
    }]
    for dm in domain_list:
        all_domains.append({
            'value': dm.id,
            'text': dm.domainname
        })
    all_dept3 = [{
        'value': 0,
        'text': '---所有三级部门---',
        'children': all_domains
    }]
    for dept in deptv3_list:
        domains = [{
            'value': 0,
            'text': '---所有Domain---'
        }]
        for dm in domain_list:
            if dm.department_id == dept.id:
                domains.append({
                    'value': dm.id,
                    'text': dm.domainname
                })
        all_dept3.append({
            'value': dept.id,
            'text': dept.deptname,
            'children': domains
        })

    deptv2_dept_domain = [{
        'value': 0,
        'text': '---所有二级部门---',
        'children': all_dept3
    }]

    for dept2 in deptv2_list:
        domains_v2 = [{
            'value': 0,
            'text': '---所有Domain---'
        }]
        for dm in domain_list:
            if dm.department.pid == dept2.id:
                domains_v2.append({
                    'value': dm.id,
                    'text': dm.domainname
                })
            if dm.department_id == dept2.id:
                domains_v2.append({
                    'value': dm.id,
                    'text': dm.domainname,
                })
        depts = [{
            'value': 0,
            'text': '---所有三级部门---',
            'children': domains_v2
        }]
        for dept in deptv3_list:
            domains = [{
                'value': 0,
                'text': '---所有Domain---'
            }]
            for dm in domain_list:
                if dm.department_id == dept.id:
                    domains.append({
                        'value': dm.id,
                        'text': dm.domainname
                    })
            if dept.pid == dept2.id:
                depts.append({
                    'value': dept.id,
                    'text': dept.deptname,
                    'children': domains
                })
        deptv2_dept_domain.append({
            'value': dept2.id,
            'text': dept2.deptname,
            'children': depts
        })
    return Response(status=status.HTTP_200_OK, data=deptv2_dept_domain)