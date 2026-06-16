"""
301-редиректы со старых URL сайта (assortment/, information/, company/).
"""
from django.http import HttpResponsePermanentRedirect
from django.urls import reverse

from .category_urls import resolve_legacy_category_slug


def _permanent(path):
    return HttpResponsePermanentRedirect(path)


def _information_target(path_key):
    """Целевой URL для /information/<path_key>/ (reverse вызывается лениво)."""
    mapping = {
        "": "pages:home",
        "news": ("pages:useful_category", {"slug": "news"}),
        "vacancy": "pages:contacts",
        "catalog": ("pages:useful_category", {"slug": "catalogs"}),
        "elektron-catalog": ("pages:useful_category", {"slug": "catalogs"}),
        "articles": ("pages:useful_category", {"slug": "articles"}),
        "articles-sto": ("pages:useful_category", {"slug": "articles"}),
        "price-lists": ("pages:useful_category", {"slug": "catalogs"}),
        "partners": "pages:about",
    }
    target = mapping.get(path_key)
    if target is None:
        return reverse("pages:home")
    if isinstance(target, tuple):
        return reverse(target[0], kwargs=target[1])
    return reverse(target)


def legacy_information_redirect(request, path=""):
    """Старый раздел /information/ → новые страницы."""
    key = (path or "").strip("/")
    target = _information_target(key)
    if request.GET:
        target = f"{target}?{request.GET.urlencode()}"
    return _permanent(target)


def legacy_assortment_redirect(request, path=""):
    """
    Старый каталог /assortment/ → /shop/catalog/ или /shop/category/<slug>/.
    """
    raw = (path or "").strip("/")
    if not raw:
        return _permanent(reverse("shop:catalog"))

    category_part = raw.split("/")[0]
    if category_part.endswith(".html") and "/" not in category_part:
        category_part = ""

    if not category_part:
        return _permanent(reverse("shop:catalog"))

    slug = resolve_legacy_category_slug(category_part)
    if slug:
        target = reverse("shop:category", kwargs={"category_slug": slug})
        if request.GET:
            target = f"{target}?{request.GET.urlencode()}"
        return _permanent(target)

    return _permanent(reverse("shop:catalog"))


def legacy_company_redirect(request):
    """Старый /company/ → О компании."""
    return _permanent(reverse("pages:about"))
