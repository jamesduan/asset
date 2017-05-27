from rest_framework import permissions
from assetv2.settingsapi import YCC_GROUP_ID, GROUP_ID, YCC_ENV


def permission(request, group_name_list, is_api=False):
    if request.user is None:
        return False
    if request.user.is_superuser or (is_api and request.method == 'GET') or YCC_ENV == 'test':
        return True
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    return True if set([GROUP_ID[group_name] for group_name in group_name_list]) & set(group_id_list) else False


# class YCCPermission(permissions.BasePermission):
#     def has_permission(self, request, view):
#         if YCC_ENV == 'test':
#             return True
#         group_list = request.user.groups.values()
#         group_id_list = [group['id'] for group in group_list]
#         return True if YCC_GROUP_ID in group_id_list else False


class YccAdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return permission(request, ['YCC_ADMIN'], True)


class YccCommitPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return permission(request, ['COMMIT', 'YCC_ADMIN'], True)


class YccGroupStatusPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'PATCH' and request.DATA.get('op') == 'rmvaudit':
            return permission(request, ['COMMIT', 'YCC_ADMIN'], True)
        return permission(request, ['YCC_ADMIN'], True)