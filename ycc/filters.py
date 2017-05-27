from rest_framework import filters
from util.utils import get_app_id_filter_by_request_user,get_domains_id_by_request_user


class ConfigInfoFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        app_id_list = get_app_id_filter_by_request_user(request)
        return queryset.filter(group_status__group__app_id__in=app_id_list)


class ConfigGroupFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        app_id_list = get_app_id_filter_by_request_user(request)
        return queryset.filter(app_id__in=app_id_list)


class ConfigGroupStatusFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        app_id_list = get_app_id_filter_by_request_user(request)
        return queryset.filter(group__app_id__in=app_id_list)

class ConfigExceptionFilterBackend(filters.BaseFilterBackend):
    def filter_queryset(self, request, queryset, view):
        limit=request.GET.get('limit')
        if limit=='1':
            domain_id_list = get_domains_id_by_request_user(request)
            return queryset.filter(domain__in=domain_id_list)
        else:
            return queryset