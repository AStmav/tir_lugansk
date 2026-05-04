from .models import Category


def nav_root_categories(request):
    """Корневые категории для выпадающего меню: как заведены в БД (активные, без родителя)."""
    categories = (
        Category.objects.filter(parent__isnull=True, is_active=True)
        .order_by("order", "name")[:15]
    )
    return {"nav_root_categories": categories}
