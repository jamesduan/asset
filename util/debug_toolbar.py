def show_toolbar(request):
    try:
        user = request.user
    except:
        return False
    if user is None:
        return False
    return user.is_superuser
