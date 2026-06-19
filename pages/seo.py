"""SEO-контекст для страниц приложения pages."""
from django.urls import reverse
from django.utils.html import strip_tags

from shop.seo import (
    build_canonical_url,
    build_seo_context,
    format_delivery_meta_phrase,
    format_page_title,
    truncate_meta_text,
)


def seo_home(request):
    return build_seo_context(
        request,
        title="TIR-Lugansk - Автозапчасти в Луганске | Каталог запчастей",
        description=(
            "Интернет-магазин автозапчастей TIR-Lugansk. Широкий ассортимент оригинальных "
            f"запчастей и аналогов от проверенных производителей. {format_delivery_meta_phrase(seed=1)}"
        ),
        keywords="автозапчасти, запчасти Луганск, автомагазин, автодетали, оригинальные запчасти, аналоги, TIR-Lugansk",
        canonical_url=reverse("pages:home"),
    )


def _description_from_page(page, fallback):
    if page and page.meta_description:
        return page.meta_description.strip()
    if page and page.content:
        return truncate_meta_text(strip_tags(page.content))
    return fallback


def seo_about(request, page=None):
    return build_seo_context(
        request,
        title=format_page_title(page.meta_title if page and page.meta_title else "О компании"),
        description=_description_from_page(
            page,
            "TIR-Lugansk — надёжный поставщик автозапчастей для грузовых автомобилей в Луганске.",
        ),
        canonical_url=reverse("pages:about"),
    )


def seo_contacts(request, page=None):
    return build_seo_context(
        request,
        title=format_page_title(page.meta_title if page and page.meta_title else "Контакты"),
        description=_description_from_page(
            page,
            "Контакты интернет-магазина TIR-Lugansk: телефон, адрес, график работы и способы связи.",
        ),
        canonical_url=reverse("pages:contacts"),
    )


def seo_cms_page(request, page):
    return build_seo_context(
        request,
        title=format_page_title(page.meta_title or page.title),
        description=_description_from_page(page, truncate_meta_text(page.title)),
        canonical_url=page.get_absolute_url(),
    )


def seo_useful_category(request, category, fallback_subtitle=""):
    description = truncate_meta_text(strip_tags(category.description)) if category.description else fallback_subtitle
    if not description:
        description = f"{category.title} — полезные материалы интернет-магазина TIR-Lugansk."
    return build_seo_context(
        request,
        title=format_page_title(category.title),
        description=description,
        canonical_url=category.get_absolute_url(),
    )


def seo_useful_section_fallback(request, title, subtitle=""):
    description = subtitle or f"{title} — полезные материалы интернет-магазина TIR-Lugansk."
    return build_seo_context(
        request,
        title=format_page_title(title),
        description=description,
        canonical_url=build_canonical_url(request),
    )


def seo_useful_post(request, post):
    description = truncate_meta_text(strip_tags(post.summary)) if post.summary else ""
    if not description and post.content:
        description = truncate_meta_text(strip_tags(post.content))
    if not description:
        description = f"{post.title} — материал раздела «Полезное» TIR-Lugansk."
    return build_seo_context(
        request,
        title=format_page_title(post.title),
        description=description,
        canonical_url=post.get_absolute_url(),
        og_type="article",
    )
