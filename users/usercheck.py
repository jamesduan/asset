import urlparse
import json
from functools import wraps
from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.utils.decorators import available_attrs
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from rest_framework.authtoken.models import Token


PASSWD = 'yihaodian'


def login_check(request):
    sess_id = request.COOKIES.get('sessID')
    if not sess_id:
        logout(request)
        return False
    from django.db import connection
    cursor = connection.cursor()
    sql = "SELECT user_name, user_info FROM `db_auth`.`user_session` WHERE session_id='%s'" % sess_id
    cursor.execute(sql)
    item = cursor.fetchone()
    if not item:
        logout(request)
        return False
    username, userinfo = item
    mail = json.loads(userinfo).get('mail', '')
    if not User.objects.filter(username=username).exists():
        user = User.objects.create_user(username, mail, PASSWD)
    else:
        user = User.objects.get(username=username)
    Token.objects.get_or_create(user=user)
    user.backend = "django.contrib.auth.backends.ModelBackend"
    if request.user.is_authenticated():
        if request.user.username != username:
            logout(request)
            login(request, user)
    else:
        login(request, user)
    return True


def request_passes_test(test_func, login_url=None, redirect_field_name='redirectURL'):

    def decorator(view_func):
        @wraps(view_func, assigned=available_attrs(view_func))
        def _wrapped_view(request, *args, **kwargs):
            if test_func(request):
                return view_func(request, *args, **kwargs)
            path = request.build_absolute_uri()
            # If the login url is the same scheme and net location then just
            # use the path as the "next" url.
            login_scheme, login_netloc = urlparse.urlparse(login_url or
                                                        settings.LOGIN_URL)[:2]
            current_scheme, current_netloc = urlparse.urlparse(path)[:2]
            if ((not login_scheme or login_scheme == current_scheme) and
                (not login_netloc or login_netloc == current_netloc)):
                path = request.get_full_path()
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(path, login_url, redirect_field_name)
        return _wrapped_view
    return decorator

login_required = request_passes_test(login_check)
