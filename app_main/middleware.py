from app_main.auth import get_request_user


class SessionUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.user = get_request_user(request.session)
        return self.get_response(request)
