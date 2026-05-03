from django.db.models import Count, Q

from .models import Category


def nav_root_categories(request):
    """Корневые категории для выпадающего меню: только с товарами in_stock, до 15 шт."""
    categories = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .annotate(
            products_count=Count(
                "product",
                filter=Q(product__in_stock=True),
                distinct=True,
            )
        )
        .filter(products_count__gt=0)
        .order_by("order", "name")[:15]
    )
    return {"nav_root_categories": categories}
