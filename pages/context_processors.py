from django.utils import timezone
from django.db.models import Q

from .constants import PERSONAL_DATA_POLICY_SLUG
from .models import HeaderNotice, HelpfulMenuItem


def header_notice(request):
    now = timezone.now()
    notice = (
        HeaderNotice.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .order_by("-updated_at")
        .first()
    )
    #helpful_menu_items = HelpfulMenuItem.objects.filter(is_active=True).order_by("order", "title")
    helpful_menu_items = (
        HelpfulMenuItem.objects.filter(is_active=True)
        .select_related("useful_category")
        .order_by("order", "title")
    )
    return {
        "header_notice": notice,
        "helpful_menu_items": helpful_menu_items,
        "privacy_policy_slug": PERSONAL_DATA_POLICY_SLUG,
    }
