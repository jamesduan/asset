# -*- coding: utf-8 -*-
import time

from django.shortcuts import render_to_response
from rest_framework.authtoken.models import Token
from django.core.exceptions import ObjectDoesNotExist
from assetv2.settingscmdbv2 import STATIC_URL, CMDBAPI_URL, ROOT_URL, CMDBAPI_USER, CMDBAPI_PASS, LOGIN_URL, LOGOUT_URL
from models import AssetType, AssetModel, Rack, Area, Room, RackSpace, AssetPre
from util.timelib import stamp2str
from users.usercheck import login_required
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
import csv, json
from datetime import datetime
from util.timelib import *
from util.httplib import httpcall2
from models import Asset, IpTotal, IpSegment
from server.models import ServerAppTemplate, ServerOsTemplate, ServerEnv
from cmdb.models import News
from django.core.paginator import PageNotAnInteger, Paginator, InvalidPage, EmptyPage
from util import webmenu, breadcrumbs


def healthcheck(request):
    return HttpResponse('OKOK')


def my_render(request, template, context={}):
    tokenobj = Token.objects.get(user_id=request.user.id)
    token = tokenobj.key if tokenobj is not None else None
    expire_date = stamp2datestr(int(time.time()) - 7*24*3600)
    news = News.objects.filter(created__gte=expire_date, status=1).order_by('-id')[:1]
    for item in news:
        context['GLOBAL_NEWS'] = item
    context['USER'] = request.user
    context['LOGOUT_URL'] = LOGOUT_URL
    context['LOGIN_URL'] = LOGIN_URL
    context['STATIC_URL'] = STATIC_URL
    context['CMDBAPI_URL'] = CMDBAPI_URL
    context['API_TOKEN'] = token
    context['ROOT_URL'] = ROOT_URL

    # dynamic web menu and breadcrumb
    menus, bread = webmenu.get_menu_breadcrumbs(request)
    context['WEB_MENU'] = menus
    context['breadcrumb'] = bread
    return render_to_response(template, context)


def gettemplate(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="asset_template.csv"'
    writer = csv.writer(response)
    writer.writerow(['Assetid(Must)', 'Asset_type_id', 'SN(Must)', 'Room', 'Rack', 'RackNo', 'asset_model', 'ExpTime'])
    writer.writerow(['DCB-SRV-0094', '1', 'H75PD3X',  'DCB', 'RowC_Rack1', '1', 'Dell PowerEdge 2950', '2018-10-21'])
    return response

@login_required
@csrf_exempt
def assetlist(request):
    room_list = Room.objects.all()
    asset_type = AssetType.objects.all()
    asset_model = AssetModel.objects.all()
    current_date = stamp2str(time.time()+3*365*24*60*60, '%Y-%m-%d')
    rack_info = []
    rack = Rack.objects.all()
    roomlist = Room.objects.all()
    server_os_template = ServerOsTemplate.objects.filter(status=1, type=1)
    server_app_template = ServerAppTemplate.objects.filter(status=1, type=1)
    server_env = ServerEnv.objects.exclude(id=0)

    ipsegments = IpSegment.objects.filter(status=1)
    mgips = []
    ips = []
    for item in ipsegments:
        if item.type == 2:
            mgips.append(item.id)
        if item.type == 3:
            ips.append(item.id)
    mgip = IpTotal.objects.filter(ip_segment_id__in=mgips, status=1, is_used=0)[0:10]
    ip = IpTotal.objects.filter(ip_segment_id__in=ips, status=1, is_used=0)[0:10]

    for item in rack:
        rack_info.append({
            "id": item.id,
            "cname": "%s-%s" % (item.room.name, item.name)
        })
    cur_session = str(int(time.time()))

    if request.FILES.has_key('filename'):
        new_session = request.POST['cur_session']
        if new_session == request.session['cur_post']:
            fp = request.FILES.get('filename')
            reader = csv.reader(fp)
            header = reader.next()
            errors = []
            lists = []
            result = []
            for row in reader:
                row = [item.decode("gbk") for item in row]
                if not len(row) == 8:
                    errors.append({'assetid': row, 'info': '该记录内容填写缺失，请检查'})
                    continue
                assetid, asset_type_id, sn, room_n, rack_n, rackno_n, asset_model1, exp_time = row
                if not assetid:
                    errors.append({'assetid': row, 'info': '该记录未填写设备编号，请检查'})
                    continue
                if not sn:
                    errors.append({'assetid': row, 'info': '该记录未填写序列号，请检查'})
                    continue
                try:
                    room = Room.objects.get(name=room_n)
                    rack = Rack.objects.get(name=rack_n, room_id=room.id)
                    model = AssetModel.objects.get(name=asset_model1)
                except Room.DoesNotExist:
                    errors.append({'assetid': row, 'info': '该记录机房信息在CMDB中不存在，请检查'})
                    continue
                except Rack.DoesNotExist:
                    errors.append({'assetid': row, 'info': '该记录机架信息在CMDB中不存在，请检查'})
                    continue
                except AssetModel.DoesNotExist:
                    errors.append({'assetid': row, 'info': '该记录型号信息在CMDB中不存在，请检查'})
                    continue
                try:
                    exp_time = str2stamp(exp_time, '%Y/%m/%d') or 0 if exp_time else 0
                except Exception, e:
                    errors.append({'assetid': row, 'info': '过保时间格式错误%s，请检查' % e.message})
                    continue
                rackno = RackSpace.objects.filter(rack_id=rack.id, assetid="")
                if rackno is None:
                    errors.append({'assetid': row, 'info': '该记录所在机架的无剩余机位，请检查'})
                    continue
                if len(rackno) < int(rackno_n):
                    errors.append({'assetid': row, 'info': '该记录所在机架的剩余机位号不够，请检查'})
                    continue
                rackno = rackno[0 : int(rackno_n)]
                asset, created = Asset.objects.get_or_create(assetid=assetid, defaults={
                    'service_tag'    : sn,
                    'asset_model_id' : model.id,
                    'asset_type_id'  : asset_type_id,
                    'rack_id'        : rack.id,
                    'create_time'    : int(time.time()),
                    'last_modified'  : int(time.time()),
                    'expiration_time': exp_time,
                    'come_from'      : 1
                })

                if created:
                    for item1 in rackno:
                        item1.assetid = assetid
                        item1.save()
                    if asset_type_id == 9:
                        rack, created = Rack.objects.get_or_create(name=assetid, room_id=room.id, defaults={
                            'height': 20,
                            'valid': 0,
                            'ctime': int(time.time()),
                        })


                    lists.append(row)

                    CB_asset = {
                        'assetid':  asset.assetid,
                        'service_tag'    : asset.service_tag,
                        'asset_type_id'  : asset.asset_type_id,
                        'asset_model_id' : asset.asset_model_id,
                        'create_time'    : asset.create_time,
                        'last_modified'  : asset.last_modified,
                        'expiration_time': asset.expiration_time,
                    }
                    happen_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    body = {
                        "user": request.user.username,
                        "type": "asset",
                        "action": "import",
                        "index": asset.assetid,
                        "message": json.dumps(CB_asset, ensure_ascii=False),
                        "level": "change",
                        "happen_time": happen_time
                    }
                    url = CMDBAPI_URL + 'change/'
                    httpcall2(url, method="POST", body=body, username=CMDBAPI_USER, password=CMDBAPI_PASS)
                else:
                    errors.append({'assetid': row, 'info': '该记录已存在，无需重新录入。请检查'})

            for item in errors:
                result.append('%s - %s' % (item['assetid'], item['info']))

            info = " 成功录入%s台, %s台有问题, 请检查" % (len(lists),len(errors))
            result_str = "<br />".join(result)
    request.session['cur_post'] = cur_session
    return my_render(request, 'cmdbv2/asset/assetlist.html', locals())


@login_required
def ipsegmentlist(request):
    room = Room.objects.all()
    return my_render(request, 'cmdbv2/asset/ipsegmentlist.html', locals())

@login_required
def racklist(request):
    room = Room.objects.all()
    return my_render(request, 'cmdbv2/asset/racklist.html', locals())

@login_required
def modellist(request):
    return my_render(request, 'cmdbv2/asset/assetmodellist.html', locals())

@login_required
def zonelist(request):
    arealist = Area.objects.all()
    return my_render(request, 'cmdbv2/asset/zonelist.html', locals())

@login_required
def repairlist(request):
    return my_render(request, 'cmdbv2/asset/repairlist.html', locals())

@login_required
@csrf_exempt
def assetchart(request, id, type, is_print):
    roomlist = Room.objects.all()
    rooms = Room.objects.filter(id = id)
    room = rooms[0] if rooms else Room.objects.get(id = 1)
    type_key = 0 if type == 'virtual' else 1
    racklist = Rack.objects.filter(room_id = room.id, valid = type_key).exclude(height__in = [100, 300, 500]).order_by('name')
    rack_id_all = [item.id for item in racklist]
    spacelist = RackSpace.objects.filter(rack_id__in = rack_id_all).exclude(assetid = '')
    height_all = [item.height for item in racklist]
    ips = IpTotal.objects.filter(type = 3, is_used = 1)
    mgmt_ips = IpTotal.objects.filter(type = 2, is_used = 1)
    asset_all = Asset.objects.filter(rack_id__in = rack_id_all)
    row_no = max(height_all) if height_all else 0
    col_no = len(racklist)
    assetlist = [[None for col in range(col_no)] for row in range(row_no)]
    for c,rack in enumerate(racklist):
        for s in spacelist:
            if rack.id == s.rack_id:
                for a in asset_all:
                    if a.assetid == s.assetid:
                        ip = ''
                        mgmt_ip = ''
                        for z in ips:
                            if z.asset_info == a.assetid:
                                ip = z.ip
                                break
                        for j in mgmt_ips:
                            if j.asset_info == a.assetid:
                                mgmt_ip = j.ip
                                break
                        assetlist[s.unit_no - 1][c] = {
                            'asset': a,
                            'ip': ip,
                            'mgmt_ip': mgmt_ip
                        }
                        break
        c = c + 1

    resultlist = []
    no_list = []
    for i in range(0,row_no):
        no_list.append(row_no - i)
        resultlist.append({
            'assets': assetlist[row_no - i - 1]
        })
    if int(is_print) == 0:
        return my_render(request, 'cmdbv2/asset/assetchart.html', locals())
    else:
        return my_render(request, 'cmdbv2/asset/assetchart_print.html', locals())


@login_required
@csrf_exempt
def pre_asset(request):
    asset_type = AssetType.objects.all()
    action = request.GET.get("action")
    page_get = int(request.GET.get("page", 1))

    if action is not None:
        if action == "export":
            cname = request.POST.get("cname")
            count = request.POST.get("count")
            asset_type_id = request.POST.get("asset_type_id")

            preasset = AssetPre.objects.filter(is_used=0, asset_type_id=asset_type_id)[:count]

            item_id = [item.id for item in preasset]
            AssetPre.objects.filter(id__in=item_id).update(is_used=1, cname=cname)

            response = HttpResponse(mimetype="text/csv")
            response['Content-Disposition'] = 'attachment; filename=pre_assetid.csv'
            writer = csv.writer(response)

            for item in preasset:
                writer.writerow([item.assetid])
            return response
        if action == "search":
            page_size = 50
            cname = request.REQUEST.get("cname1")
            if cname is not None:
                preasset = AssetPre.objects.filter(is_used=1, cname=cname)
                after_range_num = 5
                befor_range_num = 4
                try:
                    page = page_get
                    if page < 1:
                        page = 1
                except ValueError:
                    page = 1
                paginator = Paginator(preasset, page_size)

                try:
                    list = paginator.page(page)
                except(EmptyPage, InvalidPage, PageNotAnInteger):
                    list = paginator.page(paginator.num_pages)
                if page >= after_range_num:
                    page_range = paginator.page_range[page-after_range_num:page+befor_range_num]
                else:
                    page_range = paginator.page_range[0:int(page)+befor_range_num]
    return my_render(request, 'cmdbv2/asset/pre_asset.html', locals())

@login_required
def extranetip(request):
    room = Room.objects.all()
    return my_render(request, 'cmdbv2/asset/extranetip.html', locals())