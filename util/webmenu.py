import collections
from cmdb.models import WebMenu
import breadcrumbs

# from the table of "web_menu" in database
# Must be equal to the field 'id' of db
MENU_ID_MAIN_MENU = 186
MENU_ID_MONITOR_BASE = 6
# MENU_ID_MONITOR_BUSINESS = 7
# MENU_ID_MONITOR_LOG = 8
MENU_ID_EVENT_ALARM = 11
MENU_ID_CONFIG_BASE_INFO = 12
MENU_ID_CONFIG_IDC = 13
MENU_ID_CONFIG_SERVER = 14
MENU_ID_CONFIG_DEPLOY = 15
#MENU_ID_ANALYSIS_QA = 17
#MENU_ID_ANALYSIS_COST = 19
#MENU_ID_OTHER_KPI = 23
#MENU_ID_OTHER_CONTAINER = 24
MENU_ID_RIGHT_MENU = 161
MENU_ID_CHANGE_SYS = 164

MENU_ID_DEPLOY_YCC = 88
MENU_ID_DEPLOY_PRE_CONFIG = 89
MENU_ID_DEPLOY_RECORD = 238
MENU_ID_DEPLOY_ANALYSIS = 239

MENU_ID_ACCIDENT_CENTER = 257

# get the sub menu of the given menu id
def get_dynamic_web_menu(menu_id):
     menu_dict = collections.OrderedDict()
     if not menu_id:
         return menu_dict
     menus = WebMenu.objects.filter(top_id=menu_id, status=1).order_by('-weight')

     for menu in menus.all():
         menu_name =  menu.name
         menu_url = menu.url
         menu_icon = menu.icon
         # print "menu.id: %d, menu_name:%s, menu_url:%s" % (menu.id, menu_name, menu_url)

         if menu_url:
             menu_new_tab = menu.new_tab
             menu_content = {"flag": False, "value": menu_url, "icon": menu_icon, "new_tab": menu_new_tab}
             menu_dict[menu_name] = menu_content
         else:
            # url is none, the menu of next level
            id = menu.id
            sub_dict = get_dynamic_web_menu(id)
            menu_content = {"flag": True, "value": sub_dict, "icon": menu_icon}
            menu_dict[menu_name] = menu_content
     return menu_dict


def get_menu_name(menu_id):
    try:
        menu = WebMenu.objects.get(pk=menu_id)
        menu_name = menu.name
    except WebMenu.DoesNotExist:
        menu_name = ""
    # print "menu name:%s" %menu_name
    return menu_name

# get all menu: including main menu, function menu, the menu on the right
def get_all_menu(function_menu_id):
    # get main menu
    main_menu = get_dynamic_web_menu(MENU_ID_MAIN_MENU)

    # get function menu
    title_name = get_menu_name(function_menu_id)
    function_menu_body = get_dynamic_web_menu(function_menu_id)
    function_menu = {"title": title_name, "body": function_menu_body}

    # get the menu on the right
    right_menu = get_dynamic_web_menu(MENU_ID_RIGHT_MENU)

    menus = {"main": main_menu, "function_menu": function_menu, "right_menu": right_menu}
    return menus


# redirect url
def get_actual_url(request):
    origin_query_string = request.META.get('QUERY_STRING', 'unkown')
    # print "query string:%s" %origin_query_string
    host_address = request.get_host()

    index = origin_query_string.find("url=")
    actual_url = ''
    if index != -1:
        origin_query_string = origin_query_string[index+4:]
        http_flag = origin_query_string.find("http://")
        if http_flag != -1:
            actual_url = origin_query_string
        else:
            actual_url = "http://" + host_address + origin_query_string
            # print "actual url:%s" %(actual_url)
    return actual_url


# get web parent menu id
def get_web_parent_menu_id(menu_id):
    try:
        menu = WebMenu.objects.exclude(status=0).get(id=menu_id)
        menu = menu.top
    except Exception:
        menu = None

    while menu:
        # url is not null
        if menu.url:
            return menu.id

        try:
            menu = menu.top
        except Exception:
            menu = None

    return


# url --> menu
def get_menu_id(request):
    menu_id = None
    full_path = request.get_full_path()

    # print "full path:%s" % full_path
    rows = WebMenu.objects.exclude(status=0).filter(url__endswith=full_path)
    for row in rows:
        icon = row.icon
        if icon and len(rows) > 1:
            continue
        menu_id = row.id
        break

    # menu status == invisible
    if not menu_id:
        real_path = request.path
        # print "real path:%s" % real_path
        rows = WebMenu.objects.exclude(status=0).filter(url__endswith=real_path)
        for row in rows:
            if row.status == 2:
                menu_id = row.id
                break
    # print "menu id: %s" % menu_id
    return  menu_id


# the second parameter is depreciated.
def get_menu_breadcrumbs(request, default_menu_id=MENU_ID_MAIN_MENU):
    menu_id = request.GET.get('menu_id', '')

    need_bread = True
    if not menu_id:
        new_menu_id = get_menu_id(request)
        if not new_menu_id:
            menu_id = default_menu_id
            if menu_id == MENU_ID_MAIN_MENU:
                need_bread = False
        else:
            menu_id = new_menu_id

    parent_menu_id = get_web_parent_menu_id(menu_id)

    # print "menu id:%s, parent:%s" %(menu_id, parent_menu_id)
    all_menu = get_all_menu(parent_menu_id)
    if need_bread:
        bread_crumbs = breadcrumbs.get_breadcrumbs_navigator(menu_id)
    else:
        bread_crumbs = None
    # print "all:%s" % all_menu
    # print "bread:%s" % bread_crumbs
    return all_menu, bread_crumbs

