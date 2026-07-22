from django.contrib.syndication.views import Feed
from django.conf import settings
from django.utils.feedgenerator import Rss201rev2Feed
from django.utils.html import strip_tags
from io import StringIO
from xml.dom import minidom

from .models import Product


class PrettyRssFeed(Rss201rev2Feed):
    def root_attributes(self):
        attrs = super().root_attributes()
        attrs["xmlns:atom"] = "http://www.w3.org/2005/Atom"
        return attrs

    def add_root_elements(self, handler):
        super().add_root_elements(handler)
        feed_url = (self.feed.get("feed_url") or "").strip()
        if feed_url:
            handler.addQuickElement(
                "atom:link",
                "",
                {
                    "href": feed_url,
                    "rel": "self",
                    "type": "application/rss+xml",
                },
            )

    def write(self, outfile, encoding):
        buffer = StringIO()
        super().write(buffer, encoding)
        xml_content = buffer.getvalue()

        try:
            pretty_xml = minidom.parseString(xml_content.encode(encoding)).toprettyxml(
                indent="    ",
                encoding=encoding,
            )
            pretty_text = pretty_xml.decode(encoding)
        except Exception:
            pretty_text = xml_content

        outfile.write(pretty_text)


class CatalogUpdatesFeed(Feed):
    feed_type = PrettyRssFeed
    title = "tir-lugansk.ru"
    description = "TIR-LUGANSK - запчасти для грузовиков и прицепов"
    item_guid_is_permalink = True

    @property
    def _base_url(self):
        site_url = (getattr(settings, "SITE_URL", "") or "").strip()
        return site_url.rstrip("/") if site_url else "http://tir-lugansk.ru"

    def link(self):
        return self._base_url

    def feed_url(self):
        return f"{self._base_url}/rss.xml"

    def items(self):
        return (
            Product.objects.filter(in_stock=True)
            .select_related("brand", "category")
            .order_by("-updated_at")[:200]
        )

    def item_title(self, item):
        return item.name

    def item_description(self, item):
        def _clean(value):
            return strip_tags(value or "").strip()

        parts = ["ХАРАКТЕРИСТИКИ", ""]

        if item.brand_id and item.brand and item.brand.name:
            parts.append(f"Производитель {item.brand.name}")
        if item.catalog_number:
            parts.append(f"Каталожный номер {item.catalog_number}")
        if item.code:
            parts.append(f"Код {item.code}")
        if item.price is not None:
            parts.append(f"Цена {item.price:.0f} руб.")
        parts.append("В наличии" if item.in_stock else "Под заказ")

        applicability = _clean(item.applicability)
        if applicability:
            parts.append(f"Применяемость {applicability}")

        # Если характеристик мало, оставляем только очищенное описание (как fallback).
        if len(parts) <= 3:
            return _clean(item.description)

        # Формат "как в старой ленте": только блок характеристик, без доп. абзацев.
        return "\n".join(parts).strip()

    def item_link(self, item):
        return f"{self._base_url}{item.get_absolute_url()}"

    def item_guid(self, item):
        return self.item_link(item)

    def item_pubdate(self, item):
        return item.updated_at

    def item_categories(self, item):
        return [item.category.name] if item.category_id and item.category else []
