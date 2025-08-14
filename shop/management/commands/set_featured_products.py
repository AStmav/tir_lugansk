from django.core.management.base import BaseCommand
from shop.models import Product
import random


class Command(BaseCommand):
    help = 'Устанавливает случайные товары как популярные (featured) для отображения на главной странице'

    def add_arguments(self, parser):
        parser.add_argument(
            '--count', 
            type=int, 
            default=15,
            help='Количество товаров для установки как популярные (по умолчанию 15)'
        )
        parser.add_argument(
            '--clear-existing', 
            action='store_true',
            help='Сначала убрать флаг featured у всех товаров'
        )
        parser.add_argument(
            '--by-brand',
            type=str,
            help='Выбирать товары только определенного бренда'
        )

    def handle(self, *args, **options):
        count = options['count']
        clear_existing = options['clear_existing']
        by_brand = options.get('by_brand')

        # Очищаем существующие популярные товары если указан флаг
        if clear_existing:
            existing_featured = Product.objects.filter(is_featured=True).count()
            if existing_featured > 0:
                Product.objects.filter(is_featured=True).update(is_featured=False)
                self.stdout.write(f'🧹 Убран флаг "популярный" у {existing_featured} товаров')

        # Базовый queryset
        available_products = Product.objects.filter(in_stock=True)
        
        # Фильтруем по бренду если указан
        if by_brand:
            available_products = available_products.filter(brand__name__icontains=by_brand)
            self.stdout.write(f'🔍 Фильтруем товары бренда: {by_brand}')

        total_available = available_products.count()
        
        if total_available == 0:
            self.stdout.write(self.style.ERROR('❌ Нет доступных товаров для установки как популярные!'))
            return

        if total_available < count:
            self.stdout.write(self.style.WARNING(f'⚠️ Доступно только {total_available} товаров, будет установлено {total_available} как популярные'))
            count = total_available

        self.stdout.write(f'📊 Всего товаров в наличии: {total_available}')
        self.stdout.write(f'🎯 Будет установлено как популярные: {count}')

        # Получаем случайные товары
        # Используем order_by('?') для случайной выборки
        random_products = available_products.order_by('?')[:count]

        # Устанавливаем флаг is_featured
        updated_count = 0
        popular_brands = set()
        popular_categories = set()

        for product in random_products:
            product.is_featured = True
            product.save()
            updated_count += 1
            
            if product.brand:
                popular_brands.add(product.brand.name)
            if product.category:
                popular_categories.add(product.category.name)

            # Показываем первые 5 товаров для примера
            if updated_count <= 5:
                brand_name = product.brand.name if product.brand else 'Без бренда'
                category_name = product.category.name if product.category else 'Без категории'
                self.stdout.write(f'   ⭐ {product.name[:50]}... | {brand_name} | {category_name}')

        # Финальная статистика
        self.stdout.write(f'\n✅ ПОПУЛЯРНЫЕ ТОВАРЫ УСТАНОВЛЕНЫ!')
        self.stdout.write(f'   📦 Обновлено товаров: {updated_count}')
        self.stdout.write(f'   🏭 Уникальных брендов: {len(popular_brands)}')
        self.stdout.write(f'   📁 Уникальных категорий: {len(popular_categories)}')

        if popular_brands:
            self.stdout.write(f'\n🏭 Бренды в популярных товарах:')
            for brand in sorted(popular_brands):
                self.stdout.write(f'   • {brand}')

        if popular_categories:
            self.stdout.write(f'\n📁 Категории в популярных товарах:')
            for category in sorted(popular_categories):
                self.stdout.write(f'   • {category}')

        # Проверяем финальный результат
        final_featured_count = Product.objects.filter(is_featured=True, in_stock=True).count()
        self.stdout.write(f'\n🎉 Теперь на сайте будет отображаться {final_featured_count} популярных товаров!')
        self.stdout.write('🌐 Обновите главную страницу сайта для просмотра изменений')

        if final_featured_count > 0:
            self.stdout.write(self.style.SUCCESS('\n✅ Секция "Какие товары чаще всего покупаются?" теперь заполнена!'))
        else:
            self.stdout.write(self.style.ERROR('\n❌ Что-то пошло не так, популярные товары не установлены!'))