from django.core.management.base import BaseCommand
from shop.models import Product, Brand, Category


class Command(BaseCommand):
    help = 'ПОЛНАЯ ОЧИСТКА всех товаров, брендов и категорий'

    def add_arguments(self, parser):
        parser.add_argument('--confirm', action='store_true', help='Подтверждение очистки')

    def handle(self, *args, **options):
        if not options.get('confirm'):
            self.stdout.write(self.style.ERROR('⚠️  ВНИМАНИЕ! ЭТА КОМАНДА УДАЛИТ ВСЕ ДАННЫЕ!'))
            self.stdout.write('Для подтверждения добавьте флаг --confirm')
            return

        # Считаем что будем удалять
        products_count = Product.objects.count()
        brands_count = Brand.objects.count()
        categories_count = Category.objects.count()

        self.stdout.write(f'🗑️  УДАЛЯЕМ:')
        self.stdout.write(f'   📦 Товаров: {products_count}')
        self.stdout.write(f'   🏷️  Брендов: {brands_count}')
        self.stdout.write(f'   📁 Категорий: {categories_count}')

        # Удаляем всё
        Product.objects.all().delete()
        self.stdout.write(f'✅ Удалено товаров: {products_count}')

        Brand.objects.all().delete()
        self.stdout.write(f'✅ Удалено брендов: {brands_count}')

        Category.objects.all().delete()
        self.stdout.write(f'✅ Удалено категорий: {categories_count}')

        self.stdout.write(self.style.SUCCESS('🎉 БАЗА ДАННЫХ ПОЛНОСТЬЮ ОЧИЩЕНА!'))
        self.stdout.write('Теперь можно делать чистый импорт:') 