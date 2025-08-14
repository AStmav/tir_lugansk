from django.core.management.base import BaseCommand
from django.db import transaction
from shop.models import Product, ProductImage, ProductAnalog, OeKod, Category, Brand
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Очистка товаров и связанных данных из базы данных'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep-categories', 
            action='store_true',
            help='Сохранить категории (не удалять)'
        )
        parser.add_argument(
            '--keep-brands', 
            action='store_true',
            help='Сохранить бренды (не удалять)'
        )
        parser.add_argument(
            '--confirm', 
            action='store_true',
            help='Подтвердить удаление без интерактивного запроса'
        )

    def handle(self, *args, **options):
        keep_categories = options.get('keep_categories', False)
        keep_brands = options.get('keep_brands', False)
        confirm = options.get('confirm', False)

        # Подсчитываем что будет удалено
        products_count = Product.objects.count()
        images_count = ProductImage.objects.count()
        analogs_count = ProductAnalog.objects.count()
        oe_count = OeKod.objects.count()
        categories_count = Category.objects.count()
        brands_count = Brand.objects.count()

        self.stdout.write('📊 СТАТИСТИКА БАЗЫ ДАННЫХ:')
        self.stdout.write(f'   📦 Товаров: {products_count}')
        self.stdout.write(f'   🖼️ Изображений товаров: {images_count}')
        self.stdout.write(f'   🔗 Аналогов товаров: {analogs_count}')
        self.stdout.write(f'   🏷️ OE кодов: {oe_count}')
        self.stdout.write(f'   📁 Категорий: {categories_count}')
        self.stdout.write(f'   🏭 Брендов: {brands_count}')

        if products_count == 0:
            self.stdout.write(self.style.SUCCESS('✅ База данных уже пуста!'))
            return

        self.stdout.write(f'\n⚠️ ПЛАН УДАЛЕНИЯ:')
        self.stdout.write(f'   🗑️ Товары: {products_count} (будут удалены)')
        self.stdout.write(f'   🗑️ Изображения: {images_count} (будут удалены)')
        self.stdout.write(f'   🗑️ Аналоги: {analogs_count} (будут удалены)')
        self.stdout.write(f'   🗑️ OE коды: {oe_count} (будут удалены)')
        
        if keep_categories:
            self.stdout.write(f'   💾 Категории: {categories_count} (сохранятся)')
        else:
            self.stdout.write(f'   🗑️ Категории: {categories_count} (будут удалены)')
            
        if keep_brands:
            self.stdout.write(f'   💾 Бренды: {brands_count} (сохранятся)')
        else:
            self.stdout.write(f'   🗑️ Бренды: {brands_count} (будут удалены)')

        if not confirm:
            self.stdout.write(f'\n❗ ВНИМАНИЕ: Это действие нельзя отменить!')
            
            response = input('\nПродолжить удаление? (yes/no): ')
            if response.lower() not in ['yes', 'y', 'да', 'д']:
                self.stdout.write(self.style.WARNING('❌ Операция отменена'))
                return

        self.stdout.write(f'\n🚀 Начинаем очистку базы данных...')
        logger.info("Начинаем очистку базы данных")

        try:
            with transaction.atomic():
                # Удаляем в правильном порядке (от зависимых к независимым)
                
                # 1. Удаляем изображения товаров
                if images_count > 0:
                    deleted_images = ProductImage.objects.all().delete()[0]
                    self.stdout.write(f'✅ Удалено изображений: {deleted_images}')
                    logger.info(f"Удалено изображений товаров: {deleted_images}")

                # 2. Удаляем аналоги товаров
                if analogs_count > 0:
                    deleted_analogs = ProductAnalog.objects.all().delete()[0]
                    self.stdout.write(f'✅ Удалено аналогов: {deleted_analogs}')
                    logger.info(f"Удалено аналогов товаров: {deleted_analogs}")

                # 3. Удаляем OE коды
                if oe_count > 0:
                    deleted_oe = OeKod.objects.all().delete()[0]
                    self.stdout.write(f'✅ Удалено OE кодов: {deleted_oe}')
                    logger.info(f"Удалено OE кодов: {deleted_oe}")

                # 4. Удаляем товары
                if products_count > 0:
                    deleted_products = Product.objects.all().delete()[0]
                    self.stdout.write(f'✅ Удалено товаров: {deleted_products}')
                    logger.info(f"Удалено товаров: {deleted_products}")

                # 5. Удаляем категории (если не сохраняем)
                if not keep_categories and categories_count > 0:
                    deleted_categories = Category.objects.all().delete()[0]
                    self.stdout.write(f'✅ Удалено категорий: {deleted_categories}')
                    logger.info(f"Удалено категорий: {deleted_categories}")

                # 6. Удаляем бренды (если не сохраняем)
                if not keep_brands and brands_count > 0:
                    deleted_brands = Brand.objects.all().delete()[0]
                    self.stdout.write(f'✅ Удалено брендов: {deleted_brands}')
                    logger.info(f"Удалено брендов: {deleted_brands}")

            # Финальная статистика
            final_products = Product.objects.count()
            final_categories = Category.objects.count()
            final_brands = Brand.objects.count()

            self.stdout.write(f'\n🎉 ОЧИСТКА ЗАВЕРШЕНА!')
            self.stdout.write(f'📊 ИТОГОВАЯ СТАТИСТИКА:')
            self.stdout.write(f'   📦 Товаров осталось: {final_products}')
            self.stdout.write(f'   📁 Категорий осталось: {final_categories}')
            self.stdout.write(f'   🏭 Брендов осталось: {final_brands}')

            if final_products == 0:
                self.stdout.write(self.style.SUCCESS('\n✅ База данных товаров полностью очищена!'))
                self.stdout.write('🚀 Теперь можно запускать импорт DBF файлов')
            else:
                self.stdout.write(self.style.WARNING(f'\n⚠️ Остались товары: {final_products}'))

            logger.info(f"Очистка завершена. Товаров: {final_products}, Категорий: {final_categories}, Брендов: {final_brands}")

        except Exception as e:
            error_msg = f'Ошибка при очистке базы данных: {str(e)}'
            self.stdout.write(self.style.ERROR(f'❌ {error_msg}'))
            logger.error(error_msg)
            raise
