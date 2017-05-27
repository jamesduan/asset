from rest_framework import permissions
from django.conf import settings
from views import is_valid_and_is_dba


def permission(request, group_name_list):
    if request.user is None:
        return False
    if request.user.is_superuser:
        return True
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    return True if set([settings.GROUP_ID.get(group_name) for group_name in group_name_list]) & set(group_id_list) else False


class DBAPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return permission(request, ['DB_ADMIN'])


def is_dba(request):
    if request.user is None:
        return False

    # return True  # debug_fxc
    user_name = request.user.username
    return is_valid_and_is_dba(user_name)[1]


class DnsPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None:
            return False

        user_name = request.user.username

        # return True  # debug_fxc
        return is_valid_and_is_dba(user_name)[0]
