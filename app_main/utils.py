def is_moderator(request)->bool:
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return True
    return False


def is_no_loader(request)->bool:
    if request.session.get('no_loader', False):
        return True
    return False