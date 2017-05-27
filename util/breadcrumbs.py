# encoding:utf-8

from cmdb.models import WebMenu

def get_breadcrumbs_navigator(menu_id):
    navigator = None
    try:
        menu = WebMenu.objects.exclude(status=0).get(id=menu_id)
        navigator = [dict(name=menu.name, url=menu.url, doc_url=menu.doc_url)]
        father = menu.top
    except WebMenu.DoesNotExist:
        father = None
    while father:
        navigator.insert(0, dict(name=father.name, url=father.url, doc_url=father.doc_url))
        try:
            father = father.top
        except WebMenu.DoesNotExist:
            father = None
    return navigator

