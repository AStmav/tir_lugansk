from django.core.management.base import BaseCommand
from shop.models import Product
import random


class Command(BaseCommand):
    help = 'Устанавливает флаги is_featured и is_new для случайных товаров'

    def add_arguments(self, parser):
        parser.add_argument(
            '--featured', 
            type=int, 
            default=15,
            help='Количество популярных товаров'
        )
        parser.add_argument(
            '--new', 
            type=int, 
            default=15,
            help='Количество новых товаров'
        )

    def handle(self, *args, **options):
        featured_count = options['featured']
        new_count = options['new']
        
        # Получаем все товары
        all_products = list(Product.objects.filter(in_stock=True))
        
        if len(all_products) < featured_count + new_count:
            self.stdout.write(
                self.style.WARNING(
                    f'В базе только {len(all_products)} товаров, но запрошено {featured_count + new_count}'
                )
            )
            featured_count = min(featured_count, len(all_products) // 2)
            new_count = min(new_count, len(all_products) - featured_count)
        
        # Сбрасываем все флаги
        Product.objects.all().update(is_featured=False, is_new=False)
        
        # Выбираем случайные товары для популярных
        featured_products = random.sample(all_products, featured_count)
        featured_ids = [p.id for p in featured_products]
        
        # Оставшиеся товары для новых (исключаем уже выбранные популярные)
        remaining_products = [p for p in all_products if p.id not in featured_ids]
        new_products = random.sample(remaining_products, min(new_count, len(remaining_products)))
        new_ids = [p.id for p in new_products]
        
        # Обновляем флаги
        Product.objects.filter(id__in=featured_ids).update(is_featured=True)
        Product.objects.filter(id__in=new_ids).update(is_new=True)
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно установлено:\n'
                f'- {len(featured_ids)} популярных товаров\n'
                f'- {len(new_ids)} новых товаров'
            )
        )
        
        # Показываем примеры
        self.stdout.write('\nПопулярные товары:')
        for product in featured_products[:5]:
            self.stdout.write(f'  - {product.name}')
            
        self.stdout.write('\nНовые товары:')
        for product in new_products[:5]:
            self.stdout.write(f'  - {product.name}') 