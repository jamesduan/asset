from rest_framework import permissions
from assetv2.settingsapi import GROUP_ID


def permission(request, group_name_list, is_api=False):
    if request.user is None:
        return False
    if request.user.is_superuser or (is_api and request.method == 'GET'):
        return True
    group_list = request.user.groups.values()
    group_id_list = [group['id'] for group in group_list]
    return True if set([GROUP_ID[group_name] for group_name in group_name_list]) & set(group_id_list) else False


class PathConfigAdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return permission(request, ['PATH_CONFIG_ADMIN'], True)


class HudsonJobAdminPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return permission(request, ['HUDSON_JOB_ADMIN'], True)

# class DeployProcessPatternAdminPermission(permissions.BasePermission):
#    def has_permission(self, request, view):
#        return permission(request,['DEPLOY_PROCESS_PATTERN_ADMIN'],True)

class DeployPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None:
            return False
        if request.user.is_superuser:
            return True
        group_list = request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        return True if GROUP_ID['DEPLOY'] in group_id_list else False

class StgListCreatePermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'POST':
            if request.user is None:
                return False
            if request.user.is_superuser:
                return True
            group_list = request.user.groups.values()
            group_id_list = [group['id'] for group in group_list]
            return True if GROUP_ID['DEPLOY'] in group_id_list else False
        if request.method == 'GET':
            return True

class RebootPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None:
            return False
        if request.user.is_superuser:
            return True
        group_list = request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        return True if GROUP_ID['REBOOT'] in group_id_list else False

class StgDeployPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method == 'GET':
            return True
        else:
            if request.user is None:
                return False
            if request.user.is_superuser:
                return True
            group_list = request.user.groups.values()
            group_id_list = [group['id'] for group in group_list]
            return True if GROUP_ID['STG_DEPLOY'] in group_id_list else False
