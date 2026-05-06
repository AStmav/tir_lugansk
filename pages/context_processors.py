from django.utils import timezone
from django.db.models import Q

from .models import HeaderNotice


def header_notice(request):
    now = timezone.now()
    notice = (
        HeaderNotice.objects.filter(is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .order_by("-updated_at")
        .first()
    )
    return {"header_notice": notice}
