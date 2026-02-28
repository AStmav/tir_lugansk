"""
Middleware: доступ к админке только при обращении по разрешённому хосту (IP сервера).
"""
from django.http import HttpResponseForbidden, HttpResponseRedirect


def _get_client_host(request):
    """Хост из запроса (с учётом прокси). Без порта для сравнения."""
    raw = (
        request.META.get('HTTP_X_FORWARDED_HOST') or
        request.META.get('HTTP_HOST') or
        ''
    )
    host = raw.split(',')[0].strip().split(':')[0]
    return host


def _is_admin_allowed_host(request):
    from django.conf import settings
    allowed = getattr(settings, 'ADMIN_ALLOWED_HOSTS', None)
    if not allowed:
        return True
    host = _get_client_host(request)
    allowed_plain = [h.split(':')[0] for h in allowed]
    return host in allowed_plain


class AllowHttpForAdminHostsMiddleware:
    """
    Не редиректить на HTTPS, если запрос идёт по хосту из ADMIN_ALLOWED_HOSTS
    (например http://45.130.42.65/admin/). Иначе при SECURE_SSL_REDIRECT=True
    браузер уходит на https://IP, где часто нет сертификата, и доступ к админке ломается.
    Редирект на HTTPS делаем только для остальных хостов (доменов).
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        if not getattr(settings, 'ADMIN_ALLOWED_HOSTS', None):
            return self.get_response(request)
        if request.is_secure():
            return self.get_response(request)
        if _is_admin_allowed_host(request):
            return self.get_response(request)
        # Редирект на HTTPS для не-IP хостов (доменов)
        url = request.build_absolute_uri(request.get_full_path())
        if url.startswith('http://'):
            url = 'https://' + url[7:]
            return HttpResponseRedirect(url, status=301)
        return self.get_response(request)


class AdminOnlyFromAllowedHostsMiddleware:
    """
    Блокирует доступ к /admin/, если запрос пришёл не с хоста из ADMIN_ALLOWED_HOSTS.
    Админка доступна только по IP сервера (например http://45.130.42.65/admin/),
    по домену (tir-lugansk.ru) — 403.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        allowed = getattr(settings, 'ADMIN_ALLOWED_HOSTS', None)
        if allowed is not None and request.path.startswith('/admin/'):
            if not _is_admin_allowed_host(request):
                return HttpResponseForbidden(
                    '<h1>403 Forbidden</h1><p>Доступ к админ-панели разрешён только по IP сервера (например http://45.130.42.65/admin/).</p>'
                )
        return self.get_response(request)
