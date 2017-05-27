from rest_framework import permissions
from models import AuthUser
# from rest_framework.authtoken.models import Token


class AppPermission(permissions.BasePermission):

    def has_permission(self, request, view):
        if request.user is None:
            return False
        if request.user.is_superuser:
            return True
        try:
            user = AuthUser.objects.get(username=request.user)
        except AuthUser.DoesNotExist:
            return False
        if user.is_app == 1:
            return True
        else:
            return False


