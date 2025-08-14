from django.core.management.base import BaseCommand
from shop.models import Product, Brand


class Command(BaseCommand):
    help = 'Проверка количества товаров по брендам'

    def add_arguments(self, parser):
        parser.add_argument('--brand', type=str, help='Проверить конкретный бренд')

    def handle(self, *args, **options):
        brand_filter = options.get('brand')
        
        if brand_filter:
            # Проверяем конкретный бренд
            self.stdout.write(f'🔍 Поиск товаров бренда: {brand_filter}')
            
            # Поиск по названию бренда (case-insensitive)
            products = Product.objects.filter(brand__name__icontains=brand_filter)
            
            self.stdout.write(f'📦 Найдено товаров: {products.count()}')
            
            if products.exists():
                self.stdout.write('\n📋 Первые 10 товаров:')
                for i, product in enumerate(products[:10], 1):
                    self.stdout.write(f'{i}. {product.name} (TMP_ID: {product.tmp_id})')
        else:
            # Статистика по всем брендам
            self.stdout.write('📊 Статистика товаров по брендам:')
            
            brands = Brand.objects.all().order_by('name')
            
            for brand in brands:
                count = Product.objects.filter(brand=brand).count()
                if count > 0:
                    self.stdout.write(f'🏷️ {brand.name}: {count} товаров')
            
            total_products = Product.objects.count()
            self.stdout.write(f'\n📦 Всего товаров в базе: {total_products}') 