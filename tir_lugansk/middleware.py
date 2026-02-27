"""
Middleware: доступ к админке только при обращении по разрешённому хосту (IP сервера).
"""
from django.http import HttpResponseForbidden


class AdminOnlyFromAllowedHostsMiddleware:
    """
    Блокирует доступ к /admin/, если запрос пришёл не с хоста из ADMIN_ALLOWED_HOSTS.
    Используется, чтобы админка была доступна только по IP сервера (например 45.130.42.65:8000),
    а по домену (tir-lugansk.ru) — нет.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        allowed = getattr(settings, 'ADMIN_ALLOWED_HOSTS', None)
        if allowed is not None and request.path.startswith('/admin/'):
            host = request.get_host().split(':')[0]  # без порта для сравнения
            allowed_plain = [h.split(':')[0] for h in allowed]
            if host not in allowed_plain:
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1><p>Доступ к админ-панели разрешён только по IP сервера.</p>'
                )
        return self.get_response(request)
