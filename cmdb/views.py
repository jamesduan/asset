# -*- coding: utf-8 -*-
from rest_framework.authtoken.models import Token
from django.shortcuts import render_to_response, HttpResponseRedirect
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, LOGOUT_URL, LOGIN_URL, ES_HOST,DOMAIN_HEAD_ID
from django.views.decorators.csrf import csrf_exempt
from users.usercheck import login_required
from models import *
from asset.models import Room, Rack, Asset, RackSpace, IpTotal
from cmdb.models import News
from server.models import Server
from util.timelib import *
from django.db import connection
import elasticsearch
from django.core.paginator import PageNotAnInteger, Paginator, InvalidPage, EmptyPage
import json,csv
from django.utils.safestring import mark_safe
from assetv2.settingsapi import IDC_SHOW
from cmdb.models import AppContact, Site, App,DailyDutyConfig,DailyDutyTime
from util import webmenu, breadcrumbs
from django.http import HttpResponse
from django.db.models import Q
import re,calendar
from util.sendmail import *
from django.template import loader
from monitor.process.process import process_notification

def my_render(request, template, context={}):
    tokenobj = Token.objects.get(user_id=request.user.id)
    token = tokenobj.key if tokenobj is not None else None
    expire_date = stamp2datestr(int(time.time()) - 7 * 24 * 3600)
    news = News.objects.filter(created__gte=expire_date, status=1).order_by('-id')[:1]
    for item in news:
        context['GLOBAL_NEWS'] = item
    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL
    context['API_TOKEN'] = token
    context['ROOT_URL'] = ROOT_URL
    context['USER'] = request.user
    context['LOGOUT_URL'] = LOGOUT_URL
    context['LOGIN_URL'] = LOGIN_URL
    context['DOMAIN_HEAD_ID']=DOMAIN_HEAD_ID
    # 查询是否管理员
    cursor = connection.cursor()
    sql = "SELECT a.id FROM asset.auth_user AS a LEFT JOIN asset.auth_user_groups AS b ON a.id = b.user_id LEFT JOIN asset.auth_group AS c ON b.group_id = c.id WHERE a.username = '%s' and c.name = 'DB管理员'" % request.user
    cursor.execute(sql)
    queryset = cursor.fetchone()
    if queryset:
        context['tmp'] = "admin"
    else:
        context['tmp'] = "noadmin"

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)


@login_required
@csrf_exempt
def instancesdblist(request):
    idc = Room.objects.filter(status=1)
    db_instance = ConfigDbInstance.objects.values('instance_url', 'port', 'idc__name_ch', 'idc').distinct()
    db_default_instances = ConfigDbKvDefault.objects.exclude(jdbctype=0).order_by('dbtype')
    groups = request.user.groups.values_list()
    is_soa_group = False
    for info in groups:
        if info[0] == 9:
            is_soa_group = True
    db_permission = True if request.user.is_superuser or is_soa_group else False
    return my_render(request, 'cmdbv2/cmdb/instancesdblist.html', locals())


@login_required
@csrf_exempt
def sitelist(request):
    return my_render(request, 'cmdbv2/cmdb/sitelist.html', locals())


@login_required
@csrf_exempt
def applist(request):
    sitelist = Site.objects.all()
    return my_render(request, 'cmdbv2/cmdb/applist.html', locals())


def dept_getdomain(dept_level, level_id, node, domains):
    nodelist = []
    if level_id +1 > len(dept_level):
        return []
    else:
        if level_id == -1 and node is None:
            child_dept = [dept for dept in dept_level[0]]
            if len(child_dept):
                for d in child_dept:
                    nodelist.append({
                        'name': d.deptname.decode("utf-8"),
                        'leader': d.deptleaderaccount,
                        'mailgroup': d.deptemailgroup,
			'children': dept_getdomain(dept_level, 0, d, domains),
                        'type': 'dept'
                    })
        else:
            for dm in domains:      #当前节点下存在domain，则添加
                if dm.departmentid == node.id:
                    nodelist.append({
                        'name': dm.domainname.decode("utf-8"),
                        'leader': dm.domainleaderaccount,
                        'mailgroup': dm.domainemailgroup,
                        'type': 'domain'
                    })
            if (level_id + 1) < len(dept_level):
                child_dept = [dept for dept in dept_level[level_id + 1] if dept.pid == node.id]
                if len(child_dept):
                    for d in child_dept:
                        nodelist.append({
                            'name': d.deptname.decode("utf-8"),
                            'leader': d.deptleaderaccount,
                            'mailgroup': d.deptemailgroup,
                            'children': dept_getdomain(dept_level, level_id +1, d, domains),
                            'type': 'dept'
                        })
        return nodelist

@login_required
def deptdomainchart(request):
    deptLevel = DdDepartmentNew.objects.filter(enable=0).values_list('deptlevel').distinct().order_by('deptlevel')
    dept_level = [DdDepartmentNew.objects.filter(enable=0, deptlevel = level[0]) for level in deptLevel]
    domainlist = DdDomain.objects.filter(enable = 0).exclude(id=DOMAIN_HEAD_ID)
    resultlist = []
    nodelist = {
        'name': '组织架构图',
        'leader': '-',
        'mailgroup': '-',
        'children': dept_getdomain(dept_level, -1, None, domainlist),
        'type': 'dept'
    }
    resultlist = json.dumps(nodelist, skipkeys=True)
    tree_height = len(domainlist)
    return my_render(request, 'cmdbv2/cmdb/deptdomainchart.html', locals())

@login_required
def app_contact(request):
    sitelist = Site.objects.filter(status = 0)
    applist = App.objects.filter(status = 0)
    return my_render(request, 'cmdbv2/cmdb/appcontact_new.html', locals())

@login_required
def users_domains(request):
    return my_render(request, 'cmdbv2/cmdb/usersdomains.html', locals())
@csrf_exempt
@login_required
def userquery(request):
    currenttime = stamp2str(time.time()-10*24*60*60, '%Y-%m-%d')
    activities=RotaActivity.objects.filter(end_time__gte=currenttime).order_by('-id').exclude(promotion=2)
    sitelist = Site.objects.filter(status = 0)
    applist = App.objects.filter(status=0)
    return my_render(request,'cmdbv2/cmdb/userquery.html',locals())

@login_required
def usertel(request):

    return my_render(request,'cmdbv2/cmdb/usertel.html',locals())

@csrf_exempt
@login_required
def activity(request):
    # roleadd = RotaRole.objects.all()
    # department3 = DdDomain.objects.filter(enable=0).values('departmentname').distinct()
    defaultdoamins=SelectDomain.objects.all()
    username=request.user.username
    try:
        useremail=DdUsers.objects.get(username=username,enable=0).email
    except DdUsers.DoesNotExist:
        useremail=None
    department2 = DdDepartmentNew.objects.filter(enable=0, deptlevel=2)
    department2_domain={}
    for item in department2:
        department3=DdDepartmentNew.objects.filter(enable=0, pid=item.id)
        # if len(department3)==0:
        #     continue
        depids=[item.id]
        for object in department3:
            depids.append(object.id)
        domains=DdDomain.objects.filter(enable=0,departmentid__in=depids)
        department2_domain[item.deptname]=domains

    # domain={}
    # for item in department3:
    #     domain[item['departmentname']]=DdDomain.objects.filter(enable=0,departmentname=item['departmentname'])
    return my_render(request,'cmdbv2/cmdb/activity.html',locals())

@csrf_exempt
@login_required
def sendmail(request):
    if request.method == 'POST':
        activityid=request.POST['activityid']
        recipient=request.POST['recipient']
        recipient=recipient.replace('；',';').split(';')
        # addrecipient=[]
        # for id in recipient:
        #     try:
        #         email=DdUsers.objects.get(id=id,enable=0).email
        #     except DdUsers.DoesNotExist:
        #         email=None
        #     addrecipient.append(email)
        try:
            activity=RotaActivity.objects.get(id=activityid)
        except RotaActivity.DoesNotExist:
            return HttpResponse("<title>发送失败</title>发送失败！该活动不存在，请检查。")
        domains=activity.domains.all()
        unfinished=[]
        if activity.promotion==1:
            shifts=activity.shift_times.count()
            for domain in domains:
                if Rota.objects.filter(rota_activity=activity.id,duty_domain=domain.id).count()<shifts:
                    unfinished.append(domain.domainemailgroup)
        if activity.promotion==0:
            ym=re.findall(r"\d+",activity.name)
            day=calendar.monthrange(int(ym[0]),int(ym[1]))
            for domain in domains:
                try:
                    dailyfrequency=DailyDutyConfig.objects.get(domain=domain.id,enable=1).dailyfrequency
                except DailyDutyConfig.DoesNotExist:
                    dailyfrequency=0
                if Rota.objects.filter(rota_activity=activity.id,duty_domain=domain.id).count()<dailyfrequency*day[1]:
                    unfinished.append(domain.domainemailgroup)
            # if [domain.id for domain in domains] !=[106]:
            #     for domain in domains:
            #         if Rota.objects.filter(rota_activity=activity.id,duty_domain=domain.id).count()<day[1]:
            #             unfinished.append(domain.domainemailgroup)
            # else:
            #     for domain in domains:
            #         if Rota.objects.filter(rota_activity=activity.id,duty_domain=domain.id).count()<2*day[1]:
            #             unfinished.append(domain.domainemailgroup)
        if activity.promotion==2:
            for domain in domains:
                if Rota.objects.filter(rota_activity=activity.id,duty_domain=domain.id).count()==0:
                    unfinished.append(domain.domainemailgroup)
        recipient_list=unfinished
        subject=activity.name+'录入提醒'
        if activity.promotion ==2:
            message='您Domain的反馈信息还未录入，请尽快录入。链接：http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)
            html_content = loader.render_to_string('cmdbv2/cmdb/text_mail.html', {
            'content': '您Domain的反馈信息还未录入，请尽快录入。链接：',
            'url': 'http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)
            })
        else:
            message='您Domain的值班信息还未完整录入，请尽快录入。链接：http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)
            html_content = loader.render_to_string('cmdbv2/cmdb/text_mail.html', {
            'content': '您Domain的值班信息还未完整录入，请尽快录入。链接：',
            'url': 'http://oms.yihaodian.com.cn/cmdbv2/cmdb/rotaenter/?activity_id='+str(activity.id)
            })
        if recipient_list:
            datas={'level_id': 500,'title': subject,'message': message,'send_to': ','.join(recipient_list),
                                 'cc':','.join(recipient), 'get_time': time.time()}
            process_notification(json.dumps(datas),template= html_content.encode('utf8'))
            return  HttpResponse('<title>发送成功</title><div class="text" style="text-align:center;">发送成功!(实际邮件或有延时，请等候)</div>')
        else:
            return HttpResponse('<title>发送失败</title>所有domain的信息均已录入，邮件无需发送!')




def gettemplate(request,activity_id):
    activity = RotaActivity.objects.get(id=activity_id)
    response = HttpResponse(content_type='text/csv;charset=gb18030')
    filename=activity.name.encode('gb18030')
    response['Content-Disposition'] = 'attachment; filename='+filename+'_template.csv'
    writer = csv.writer(response)
    if activity.promotion==0:
        header = ['值班开始时间','值班结束时间','值班人员(用户名)','值班方式(on call/on site/at home)','Backup值班人员(用户名)','备注']
        writer.writerow([item.encode('gb18030') for item in header])
        ym=re.findall(r"\d+",activity.name)
        ymed=re.findall(r"\d+",activity.name)
        day=calendar.monthrange(int(ym[0]),int(ym[1]))
        # hour=[' 00:00',' 00:00']
        starttime='00:00'
        endtime='00:00'
        addday=1
        id=[object.id for object in activity.domains.all()]
        domain_id=[object.id for object in activity.domains.all()]
        if len(domain_id)==1:
            try:
                dailydutytime=DailyDutyConfig.objects.get(domain__in=domain_id,enable=1).dailydutytime
            except DailyDutyConfig.DoesNotExist:
                dailydutytime=[]
            for i in range(1,day[1]+1):
                for item in dailydutytime:
                    starttime=item.starttime.strftime('%H:%M')
                    endtime=item.endtime.strftime('%H:%M')
                    addday=item.addday
                    date=str(i)
                    dated=str(i+addday)
                    if i==day[1]:
                        ymed[1]=str(int(ymed[1])+addday)
                        dated=str(1) if addday==1 else date
                        if ymed[1]=='13':
                            ymed[1]=str(1)
                            ymed[0]=str(int(ymed[0])+1)
                    if i==1:
                        writer.writerow([ym[0]+'-'+ym[1]+'-'+date +' '+starttime, ymed[0]+'-'+ymed[1]+'-'+dated +' '+endtime,'gaoxiaomi','on call','gaoxiaomi'])
                    else:
                        writer.writerow([ym[0]+'-'+ym[1]+'-'+date +' '+starttime, ymed[0]+'-'+ymed[1]+'-'+dated +' '+endtime,'','',''])

    count=0
    if activity.promotion==1:
        header = ['值班开始时间(勿改动时间)','值班结束时间(勿改动时间)','值班人员(多个用户名，请用";"隔开）','值班方式(on call/on site/at home)','Backup值班人员(多个用户名，请用";"隔开）','备注']
        writer.writerow([item.encode('gb18030') for item in header])
        shifttime=ShiftTime.objects.filter(activity=activity.id)
        for object in shifttime:
            if count==0:
                writer.writerow([object.start, object.end,'gaoxiaomi;gaoxiaomi','on call','gaoxiaomi;gaoxiaomi'])
                count=count+1
            else:
                writer.writerow([object.start, object.end,'','',''])

    return response

@login_required
@csrf_exempt
# def rotaenter(request,activity_id):
def rotaenter(request):
    activity_id=request.GET.get('activity_id')
    user = DdUsers.objects.filter(enable=0)
    try:
        activity_select = RotaActivity.objects.get(id=activity_id)
    # except RotaActivity.DoesNotExist:
    except Exception, e:
        return  HttpResponse("该值班活动不存在")
    domains = activity_select.domains.all()
    if activity_select.promotion==0:
        domain_id=[item.id for item in domains]
        departmentid=DdDomain.objects.filter(id__in= domain_id).first().departmentid
        dep_domains=DdDomain.objects.filter(departmentid=departmentid)
        dep_domains_id=[item.id for item in dep_domains]
        dep_users=DdUsers.objects.filter(domains__id__in=dep_domains_id).distinct()
    shift_times = ShiftTime.objects.filter(activity=activity_id).order_by('id')
    cur_session = str(int(time.time()))
    if request.FILES.has_key('filename'):
        new_session = request.POST['cur_session']
        if new_session == request.session['cur_post']:
            fp = request.FILES.get('filename')
            duty_role=request.POST['duty_role']
            reader = csv.reader(fp)
            header = reader.next()
            errors = []
            lists = []
            result = []
            way_dict = dict()
            for code, desc in Rota.WAY:
                way_dict[desc] = code
            for row in reader:
                if not duty_role:
                    errors.append({'rowid': '', 'info': '未选择值班Domain，请检查'})
                    break
                row = [item.decode("gb18030") for item in row]
                if not len(row) == 6:
                    errors.append({'rowid': row, 'info': '该记录内容填写缺失，请检查'})
                    continue
                duty_date_start, duty_date_end,duty_man_account ,duty_way,duty_backup_account,comment= row

                if not duty_man_account:
                    errors.append({'rowid': row, 'info': '该记录未填写值班人员，请检查'})
                    continue
                if not duty_way:
                    errors.append({'rowid': row, 'info': '该记录未填写值班方式，请检查'})
                    continue

                way = way_dict.get(duty_way)
                if way == None :
                    errors.append({'rowid': row, 'info': '该记录值班方式填写错误，请检查'})
                    continue
                # if not duty_backup_account:
                #     errors.append({'rowid': row, 'info': '该记录未填写Backup值班人员，请检查'})
                #     continue
                duty_date_start=duty_date_start.replace('/','-')
                duty_date_end=duty_date_end.replace('/','-')
                startflag=re.findall(r"^(\d{4})-(\d{1,2})-(\d{1,2}) (\d{1,2}):(\d{2})(:\d{2})?$",duty_date_start)
                endflag=re.findall(r"^(\d{4})-(\d{1,2})-(\d{1,2}) (\d{1,2}):(\d{2})(:\d{2})?$",duty_date_end)
                if startflag==[] or endflag==[]:
                    errors.append({'rowid': row, 'info': '时间格式错误，请检查'})
                    continue
                tem_start=duty_date_start.replace(' ','-')
                tem_start=tem_start.replace(':','-')
                tem_start=tem_start.split('-')
                for i in range(1,4):
                    if len(tem_start[i])==1:
                        tem_start[i]='0'+tem_start[i]
                duty_date_start=tem_start[0]+'-'+tem_start[1]+'-'+tem_start[2]+' '+tem_start[3]+':'+tem_start[4]

                tem_end=duty_date_end.replace(' ','-')
                tem_end=tem_end.replace(':','-')
                tem_end=tem_end.split('-')
                for i in range(1,4):
                    if len(tem_end[i])==1:
                        tem_end[i]='0'+tem_end[i]
                duty_date_end=tem_end[0]+'-'+tem_end[1]+'-'+tem_end[2]+' '+tem_end[3]+':'+tem_end[4]

                manflag=True
                backupflag=True
                duty_man_list=[]
                duty_backup_list=[]
                duty_man_account=duty_man_account.replace('；',';').split(';')
                for man_account in duty_man_account:
                    if man_account !='':
                        try:
                            duty_man = DdUsers.objects.get(username=man_account, enable=0)
                            duty_man_list.append(duty_man)
                        except DdUsers.DoesNotExist:
                            errors.append({'rowid': row, 'info': '该值班人员不存在，请检查'})
                            manflag=False
                            break
                if manflag==False:
                    continue
                if duty_backup_account:
                    duty_backup_account=duty_backup_account.replace('；',';').split(';')
                    for backup_account in duty_backup_account:
                        if backup_account !='':
                            try:
                                duty_backup = DdUsers.objects.get(username=backup_account, enable=0)
                                duty_backup_list.append(duty_backup)
                            except DdUsers.DoesNotExist:
                                errors.append({'rowid': row, 'info': '该Backup值班人员不存在，请检查'})
                                backupflag=False
                                break
                    if backupflag==False:
                        continue

                if duty_man_list==[]:
                    errors.append({'rowid': row, 'info': '未填写值班人员。请检查'})
                    continue
                # if duty_backup_list==[]:
                #     errors.append({'rowid': row, 'info': '未填写Backup值班人员。请检查'})
                #     continue

                if activity_select.promotion==0:
                    geted = Rota.objects.filter(Q(duty_date_start__gte=duty_date_start,duty_date_start__lt=duty_date_end)|Q(duty_date_end__gt=duty_date_start,duty_date_end__lte=duty_date_end)|Q(duty_date_start__lte=duty_date_start,duty_date_end__gte=duty_date_end),promotion=activity_select.promotion,duty_domain=duty_role)
                    if not geted:
                        rotaobject=Rota.objects.create(rota_activity_id=activity_id,duty_date_start=duty_date_start,promotion=activity_select.promotion,duty_date_end=duty_date_end,duty_domain_id=duty_role,duty_way=way,comment=comment)
                        for duty_man in duty_man_list:
                            RotaMan.objects.create(rota_id=rotaobject.id,man_id=duty_man.id)
                        for duty_backup in duty_backup_list:
                            RotaBackup.objects.create(rota_id=rotaobject.id,backup_id=duty_backup.id)
                        lists.append(row)
                    else:
                        errors.append({'rowid': row, 'info': '该值班信息已存在或值班时间重合，无需录入。请检查'})
                if activity_select.promotion==1:
                    shifts=ShiftTime.objects.filter(activity=activity_id)
                    shift_time=''
                    for shift in shifts:
                        if duty_date_start==shift.start.strftime('%Y-%m-%d %H:%M') and duty_date_end==shift.end.strftime('%Y-%m-%d %H:%M'):
                            shift_time=shift.id
                            break

                    if shift_time=='':
                        errors.append({'rowid': row, 'info': '大促该班次不存在。请检查'})
                        continue

                    geted = Rota.objects.filter(duty_date_start=duty_date_start,duty_date_end=duty_date_end,rota_activity=activity_id,duty_way=way,duty_domain=duty_role)
                    if not geted:
                        rotaobject=Rota.objects.create(rota_activity_id=activity_id,duty_date_start=duty_date_start,shift_time_id=shift_time,promotion=activity_select.promotion,duty_date_end=duty_date_end,duty_domain_id=duty_role,duty_way=way,comment=comment)
                        for duty_man in duty_man_list:
                            RotaMan.objects.create(rota_id=rotaobject.id,man_id=duty_man.id)
                        for duty_backup in duty_backup_list:
                            RotaBackup.objects.create(rota_id=rotaobject.id,backup_id=duty_backup.id)
                        lists.append(row)
                    else:
                        errors.append({'rowid': row, 'info': '该时间段值班信息已存在，无需录入。请检查'})

            for item in errors:
                 result.append('%s - %s' % (item['rowid'], item['info']))
            info = " 成功导入%s条, %s条有问题, 请检查" % (len(lists),len(errors))

            result_str = "<br />".join(result)
    request.session['cur_post'] = cur_session
    rota_count=dict()
    detail_notfil = []
    detail_notcom = []
    for domain in domains:
        rota_count[domain.domainname] = Rota.objects.filter(duty_domain=domain.id,rota_activity=activity_id).count()
        if rota_count[domain.domainname] ==0:
            detail_notfil.append(domain.domainname)
        if activity_select.promotion ==1:
            if rota_count[domain.domainname] >0 and rota_count[domain.domainname] <len(shift_times):
                detail_notcom.append(domain.domainname)
        if activity_select.promotion ==0:
            ym=re.findall(r"\d+",activity_select.name)
            day=calendar.monthrange(int(ym[0]),int(ym[1]))
            try:
                dailyfrequency=DailyDutyConfig.objects.get(domain=domain.id,enable=1).dailyfrequency
            except DailyDutyConfig.DoesNotExist:
                dailyfrequency=0
            if rota_count[domain.domainname] >0 and rota_count[domain.domainname] <dailyfrequency*day[1]:
                    detail_notcom.append(domain.domainname)
            # if 106==domain.id:
            #     if rota_count[domain.domainname] >0 and rota_count[domain.domainname] <2*day[1]:
            #         detail_notcom.append(domain.domainname)
            # else:
            #     if rota_count[domain.domainname] >0 and rota_count[domain.domainname] <day[1]:
            #         detail_notcom.append(domain.domainname)
    detail_count = len(detail_notfil)+len(detail_notcom)
    return my_render(request,'cmdbv2/cmdb/rotaenter.html',locals())


@login_required
def rotaquery(request):
    currenttime = stamp2str(time.time()-10*24*60*60, '%Y-%m-%d')
    activities=RotaActivity.objects.filter(end_time__gte=currenttime).order_by('-id').exclude(promotion=2)
    return my_render(request,'cmdbv2/cmdb/rotaquery.html',locals())

@login_required
@csrf_exempt
def url_redirect(request):
    actual_url = webmenu.get_actual_url(request)
    return my_render(request,'cmdbv2/cmdb/redirecturl.html',locals())

@login_required
@csrf_exempt
def search_server(request):
    key = request.GET.get('key')
    try:
        es = elasticsearch.Elasticsearch([{'host': ES_HOST, 'port': 80}])
        # es = elasticsearch.Elasticsearch([{'host': '10.17.26.235', 'port': 9200}])
        es.ping()
    except Exception:
        es = None
        return my_render(request, 'globalsearch/server/searchlist.html', locals())
    regex=ur"^([\u4E00-\u9FA5a-zA-Z0-9]+)([\u4E00-\u9FA5a-zA-Z0-9\ _.\-\/])*([\u4E00-\u9FA5a-zA-Z0-9.])+$"
    if key and re.search(regex, key.strip()) is not None:
        global_key = key.strip().replace('-', ' AND ').replace('/', ' AND ')
        try:
            page = int(request.GET.get("page",1))
            page_size = 10
            after_range_num = 5
            befor_range_num = 4

            try:
                if page < 1:
                    page = 1
            except ValueError:
                page = 1

            results = es.search(
                index="cmdb",
                # index="search",
                doc_type="server",
                body={
                    "query": {

                        "bool": {
                            "must": [],
                            "must_not": [
                                {
                                    "term": {
                                        "server_status_id": "400"
                                    }
                                }
                            ],
                            "should": [
                                {
                                    "query_string": {
                                        # "query": "_all:\"" + global_key + '\"'
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "assetid",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "sn",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "site_name",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "app_name",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "hostname",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "ip",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "parent_ip",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "mgmt_ip",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "rack_name",
                                        "query": '*' + global_key + '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "type_name",
                                        "query": '*' + global_key+ '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "env_name",
                                        "query": '*' + global_key+ '*'
                                    }
                                },
                                {
                                    "query_string": {
                                        "default_field": "status_name",
                                        "query": '*' + global_key+ '*'
                                    }
                                },
                            ]
                        }
                    },
                    "from": 0,
                    "size": 10000,
                    "sort": [
                        {"ip": {"order": "asc"}},
                        {"assetid": {"order": "asc"}},
                        {"sn": {"order": "asc"}},
                        {"app_name": {"order": "asc"}},
                        "_score"
                    ],
                    "highlight": {
                        "pre_tags": "<em>",
                        "post_tags": "</em>",
                        "fields": {
                            # "_all" : {},
                            "ip": {},
                            "parent_ip": {},
                            "mgmt_ip": {},
                            "site_name": {},
                            "app_name": {},
                            "assetid": {},
                            "sn": {},
                            "hostname": {},
                            "rack_name": {},
                            "type_name": {},
                            "env_name": {},
                            "status_name": {},
                        }
                    }
                }
            )

            total = results['hits']['total']
            serverlist=[]
            if total > 0:
                for h in results['hits']['hits']:
                    if h['_type'] == 'server':
                        high = h['highlight']
                        serverlist.append({
                            'id' : h['_id'],
                            'site_name': mark_safe(high['site_name'][0]) if high.has_key('site_name') else h['_source']['site_name'],
                            'app_name': mark_safe(high['app_name'][0]) if high.has_key('app_name') else h['_source']['app_name'],
                            'assetid': mark_safe(high['assetid'][0]) if high.has_key('assetid') else h['_source']['assetid'],
                            'ip':mark_safe(high['ip'][0]) if high.has_key('ip') else h['_source']['ip'],
                            'sn': mark_safe(high['sn'][0]) if high.has_key('sn') else h['_source']['sn'],
                            'hostname': mark_safe(high['hostname'][0]) if high.has_key('hoatname') else h['_source']['hostname'],
                            'type_name':  mark_safe(high['type_name'][0]) if high.has_key('type_name') else h['_source']['type_name'],
                            'parent_ip': mark_safe(high['parent_ip'][0]) if high.has_key('parent_ip') else h['_source']['parent_ip'],
                            'mgmt_ip': mark_safe(high['mgmt_ip'][0]) if high.has_key('mgmt_ip') else h['_source']['mgmt_ip'],
                            'rack_name': mark_safe(high['rack_name'][0]) if high.has_key('rack_name') else h['_source']['rack_name'],
                            'env_name': mark_safe(high['env_name'][0]) if high.has_key('env_name') else h['_source']['env_name'],
                            'status_name': mark_safe(high['status_name'][0]) if high.has_key('status_name') else h['_source']['status_name'],
                        })
                if len(serverlist) == 1:
                    server_id = serverlist.pop()['id']
                    return HttpResponseRedirect('/cmdbv2/server/detail/?id=%s' % server_id)
                else:
                    paginator = Paginator(serverlist, page_size)
                    try:
                        serverlist = paginator.page(page)
                    except(EmptyPage, InvalidPage, PageNotAnInteger):
                        serverlist = paginator.page(paginator.num_pages)
                    if page >= after_range_num:
                        page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
                    else:
                        page_range = paginator.page_range[0:int(page)+befor_range_num]
            else:
                total = 0
        except Exception,e:
            es='ConnectError'
    else:
        param = 'Error'
    return my_render(request, 'globalsearch/server/searchlist.html', locals())


@login_required
def mobile_load(request):
    return my_render(request, 'mobile/load_page.html', locals())
