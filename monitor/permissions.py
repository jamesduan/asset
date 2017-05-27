from rest_framework import permissions
from assetv2.settingsapi import GROUP_ID


SAFE_METHOD = ['GET']

class EventPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        return True


class AlarmPermission(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.user is None:
            return False
        if request.user.is_superuser or request.method in SAFE_METHOD:
            return True

