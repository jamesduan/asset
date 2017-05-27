from rest_framework import permissions
from assetv2.settingsapi import GROUP_ID

class RotaPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None:
            return False
        if request.user.is_superuser:
            return True
        group_list = request.user.groups.values()
        group_id_list = [group['id'] for group in group_list]
        return True if GROUP_ID['ROTA'] in group_id_list else False

# class ActivityPermission(permissions.BasePermission):
#     def has_permission(self, request, view):
#         if request.user is None:
#             return False
#         if request.user.is_superuser:
#             return True
#         group_list = request.user.groups.values()
#         group_id_list = [group['id'] for group in group_list]
#         return True if GROUP_ID['ROTA'] in group_id_list else False