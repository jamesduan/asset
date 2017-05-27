# -*- coding: utf-8 -*-
'''
    @description:

    @copyright:     ©2016 yihaodian.com
    @author:        edward
    @since:         16-12-27
    @version:       0.2
'''
from settings import API_SERVER_BY_IP, LOCAL_CMDB_INFO_FILE
import socket, urllib2, time
from xml.dom import minidom


def getNetworkIp():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    s.connect(('<broadcast>', 0))
    ip = s.getsockname()[0]
    first_ip = ip.split(".")
    if first_ip[0] != '10':
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.connect(('10.4.1.249', 0))
        ip = s.getsockname()[0]
    return ip


hostip = getNetworkIp()
# hostip = "10.4.1.249"

uri = API_SERVER_BY_IP + hostip + "/?format=xml"

req = urllib2.Request(uri)
req.add_header('Authorization', 'Basic cHVwcGV0OmJPQ1JDVTFs')
try:
    f = urllib2.urlopen(req)
except urllib2.URLError, e:
    pass
else:
    content = f.read
    xmldoc = minidom.parse(f)
    assetid = xmldoc.getElementsByTagName('assetid')
    site_id = xmldoc.getElementsByTagName('site_id')
    site_name = xmldoc.getElementsByTagName('site_name')
    app_id = xmldoc.getElementsByTagName('app_id')
    app_name = xmldoc.getElementsByTagName('app_name')
    mgmt_ip = xmldoc.getElementsByTagName('mgmt_ip')
    server_status_name = xmldoc.getElementsByTagName('server_status_name')
    rack_name = xmldoc.getElementsByTagName('rack_name')
    rack_position = xmldoc.getElementsByTagName('rack_position')
    room = xmldoc.getElementsByTagName('room')
    app_type_id = xmldoc.getElementsByTagName('app_type_id')
    server_env_name = xmldoc.getElementsByTagName('server_env_name')
    server_type_id = xmldoc.getElementsByTagName('server_type_id')
    ycc_code = xmldoc.getElementsByTagName('ycc_code')
    ycc_idc = xmldoc.getElementsByTagName('ycc_idc')

    if assetid[0].firstChild is not None:
        assetid_str = assetid[0].firstChild.nodeValue
    else:
        assetid_str = ''

    if site_id[0].firstChild is not None:
        site_id_str = str(site_id[0].firstChild.nodeValue)
    else:
        site_id_str = ''

    if site_name[0].firstChild is not None:
        site_name_str = site_name[0].firstChild.nodeValue
    else:
        site_name_str = ''

    if app_id[0].firstChild is not None:
        app_id_str = str(app_id[0].firstChild.nodeValue)
    else:
        app_id_str = ''

    if app_name[0].firstChild is not None:
        app_name_str = app_name[0].firstChild.nodeValue
    else:
        app_name_str = ''

    if mgmt_ip[0].firstChild is not None:
        mgmt_ip_str = mgmt_ip[0].firstChild.nodeValue
    else:
        mgmt_ip_str = ''

    if server_status_name[0].firstChild is not None:
        server_status_name_str = server_status_name[0].firstChild.nodeValue
    else:
        server_status_name_str = ''

    if rack_name[0].firstChild is not None:
        rack_name_str = rack_name[0].firstChild.nodeValue
    else:
        rack_name_str = ''

    # if rack_position[0].firstChild is not None:
    rack_position_str = ''
    # else:
    #   rack_position_str = ''

    if room[0].firstChild is not None:
        room_str = room[0].firstChild.nodeValue
    else:
        room_str = ''

    if app_type_id[0].firstChild is not None:
        app_type_id_str = app_type_id[0].firstChild.nodeValue
    else:
        app_type_id_str = ''

    if server_env_name[0].firstChild is not None:
        server_env_name_str = server_env_name[0].firstChild.nodeValue
    else:
        server_env_name_str = ''

    if server_type_id[0].firstChild is not None:
        server_type_id_str = server_type_id[0].firstChild.nodeValue
    else:
        server_type_id_str = ''

    if ycc_code[0].firstChild is not None:
        ycc_code_str = ycc_code[0].firstChild.nodeValue
    else:
        ycc_code_str = ''

    if ycc_idc[0].firstChild is not None:
        ycc_idc_str = ycc_idc[0].firstChild.nodeValue
    else:
        ycc_idc_str = ''

    ycc_env_name_str = server_env_name_str
    if ycc_env_name_str == 'stagging':
        ycc_env_name_str = 'staging'

    current_time = str(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    current_date = str(time.strftime('%Y-%m-%d', time.localtime(time.time())))
    CURRENT_HISTORY_FILE = '/cmdb/output/history/cmdb.%s.log' % current_date

    # print assetid_str
    # print site_id_str
    # print site_name_str
    # print app_id_str
    # print app_name_str
    # print mgmt_ip_str
    # print server_status_name_str
    # print rack_position_str
    # print room_str
    # print current_time

    content = '\n'.join([
        'assetid:' + assetid_str,
        'SiteID:' + site_id_str,
        'SiteName:' + site_name_str,
        'AppID:' + app_id_str,
        'AppName:' + app_name_str,
        'ManageIP:' + mgmt_ip_str,
        'ServerStatus:' + server_status_name_str,
        'RackName:' + rack_name_str,
        'RackNo:' + rack_position_str,
        'IDC:' + room_str,
        'AppType:' + app_type_id_str,
        'ServerEnv:' + server_env_name_str,
        'ServerTypeID:' + server_type_id_str,
        'YccZone:' + ycc_code_str,
        'YccEnv:' + ycc_env_name_str,
        'YccIDC:' + ycc_idc_str,
        'Updated:' + current_time,
    ])

    # assetid[0].firstChild.nodeValue
    file_object = open(LOCAL_CMDB_INFO_FILE, 'w')
    file_object.write(content.encode("UTF-8"))
    file_object.close()

    log_content = '%s\n%s\n%s\n\n\n' % (current_time, '-' * 20, content)

    log_object = open(CURRENT_HISTORY_FILE, 'a')
    log_object.write(log_content.encode("UTF-8"))
    log_object.close()
