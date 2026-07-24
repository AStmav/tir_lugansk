from django.core.management.base import BaseCommand

from shop.models import ProductOffer
from shop.warehouse_price.service import sync_product_from_offers


class Command(BaseCommand):
    help = (
        'Пересчитать Product.price / stock_quantity / in_stock '
        'из активных ProductOffer (после старых импортов без синка).'
    )

    def handle(self, *args, **options):
        product_ids = (
            ProductOffer.objects.filter(is_active=True, warehouse__is_active=True)
            .values_list('product_id', flat=True)
            .distinct()
        )
        count = 0
        for product_id in product_ids.iterator():
            sync_product_from_offers(product_id)
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Обновлено товаров: {count}'))
