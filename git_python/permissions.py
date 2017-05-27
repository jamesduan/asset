from rest_framework import permissions
from assetv2.settingsapi import GIT


class BootShPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None:
            return False
        if request.method == 'GET' or request.user.is_superuser:
            return True
        group_list = request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        return True if GIT['BOOT_SH']['GROUP_ID'] in group_id_list else False