from rest_framework import permissions


class IsValid4VM(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.username == 'ticket'