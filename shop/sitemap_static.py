"""
Сборка sitemap в статические XML-файлы (для cron).
"""
from __future__ import annotations

import logging
from pathlib import Path

from django.conf import settings
from django.contrib.sitemaps.views import SitemapIndexItem
from django.contrib.sitemaps.views import sitemap as django_sitemap_view
from django.template.response import TemplateResponse
from django.test import RequestFactory

from shop.sitemaps import SITEMAPS

logger = logging.getLogger(__name__)


def sitemap_section_filename(section: str, page: int = 1) -> str:
    if page <= 1:
        return f"sitemap-{section}.xml"
    return f"sitemap-{section}-p{page}.xml"


def sitemap_public_url(domain: str, section: str, page: int = 1) -> str:
    scheme = "https" if getattr(settings, "SITEMAP_USE_HTTPS", True) else "http"
    return f"{scheme}://{domain}/{sitemap_section_filename(section, page)}"


def build_sitemap_request(domain: str, path: str = "/", query: str | None = None):
    factory = RequestFactory()
    url = path if not query else f"{path}?{query}"
    request = factory.get(url)
    request.META["HTTP_HOST"] = domain
    request.META["SERVER_NAME"] = domain.split(":")[0]
    if getattr(settings, "SITEMAP_USE_HTTPS", True):
        request.META["wsgi.url_scheme"] = "https"
    return request


def atomic_write(target: Path, content: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = target.with_suffix(target.suffix + ".tmp")
    tmp_path.write_bytes(content)
    tmp_path.replace(target)


def _render_section_xml(domain: str, section: str, page: int) -> bytes:
    query = f"p={page}" if page > 1 else None
    request = build_sitemap_request(domain, query=query)
    response = django_sitemap_view(
        request,
        sitemaps=SITEMAPS,
        section=section,
    )
    response.render()
    return response.content


def _render_index_xml(domain: str) -> bytes:
    sites = []
    for section, sitemap_class in SITEMAPS.items():
        site = sitemap_class()
        lastmod = site.get_latest_lastmod()
        for page in range(1, site.paginator.num_pages + 1):
            sites.append(
                SitemapIndexItem(sitemap_public_url(domain, section, page), lastmod)
            )

    request = build_sitemap_request(domain)
    response = TemplateResponse(
        request,
        "sitemap_index.xml",
        {"sitemaps": sites},
        content_type="application/xml",
    )
    response.render()
    return response.content


def _clear_generated_files(output_dir: Path) -> None:
    if not output_dir.exists():
        return
    for path in output_dir.iterdir():
        if path.name == "sitemap.xml" or (
            path.name.startswith("sitemap-") and path.name.endswith(".xml")
        ):
            path.unlink()


def build_sitemaps(
    output_dir: Path | None = None,
    domain: str | None = None,
) -> dict:
    """
    Сгенерировать sitemap.xml и дочерние карты в output_dir.
    Возвращает статистику: files, urls (приблизительно), elapsed не включён.
    """
    output_dir = Path(output_dir or settings.SITEMAP_OUTPUT_DIR)
    domain = domain or settings.SITEMAP_CANONICAL_DOMAIN

    _clear_generated_files(output_dir)

    written = []
    url_count = sum(sitemap_class().paginator.count for sitemap_class in SITEMAPS.values())

    for section, sitemap_class in SITEMAPS.items():
        site = sitemap_class()
        for page in range(1, site.paginator.num_pages + 1):
            content = _render_section_xml(domain, section, page)
            filename = sitemap_section_filename(section, page)
            target = output_dir / filename
            atomic_write(target, content)
            written.append(filename)

    index_content = _render_index_xml(domain)
    atomic_write(output_dir / "sitemap.xml", index_content)
    written.append("sitemap.xml")

    stats = {
        "output_dir": str(output_dir),
        "domain": domain,
        "files": written,
        "file_count": len(written),
        "url_count": url_count,
    }
    logger.info(
        "Sitemap собран: %s файлов, ~%s URL → %s",
        stats["file_count"],
        stats["url_count"],
        output_dir,
    )
    return stats


def read_static_sitemap(filename: str) -> bytes | None:
    """Прочитать готовый XML с диска, если файл существует."""
    if not filename.endswith(".xml") or ".." in filename or "/" in filename:
        return None
    path = Path(settings.SITEMAP_OUTPUT_DIR) / filename
    if path.is_file():
        return path.read_bytes()
    return None
