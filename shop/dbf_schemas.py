"""
Схемы структур DBF файлов для валидации

Этот модуль содержит описания ожидаемых структур для каждого типа импортируемых файлов.
Используется для валидации загруженных DBF файлов перед импортом.
"""

# Схемы для валидации DBF файлов
DBF_SCHEMAS = {
    'brands': {
        'name': 'Бренды',
        'description': 'Производители автозапчастей (~2,800 записей)',
        'command': 'import_brands_dbf',
        
        # Обязательные поля (должны присутствовать)
        'required_fields': ['ID_BRENB', 'NAME'],
        
        # Опциональные поля (могут присутствовать)
        'optional_fields': ['DESCRIPTION', 'COUNTRY', 'WEBSITE'],
        
        # Альтернативные названия для полей (учитывается регистр и варианты)
        'field_aliases': {
            'ID_BRENB': ['ID_brenb', 'Id_brenb', 'id_brenb', 'ID_BREND', 'ID_brend', 'Id_brend', 'id_brend', 'ID_brand', 'BRAND_ID', 'ID_BRAND'],
            'NAME': ['name', 'Name', 'BRAND_NAME', 'Brand_name', 'BrandName']
        },
        
        # Ожидаемый диапазон количества записей
        'min_records': 10,  # Минимум записей для валидности
        'max_records': 50000,  # Предупреждение если больше (возможно это не бренды)
        
        # Примеры полей для справки
        'example_data': {
            'ID_brend': 'B001',
            'NAME': 'Bosch'
        }
    },
    
    'products': {
        'name': 'Товары',
        'description': 'Номенклатура автозапчастей (~200,000 записей)',
        'command': 'import_dbf',
        
        # Обязательные поля
        'required_fields': ['TMP_ID', 'NAME', 'PROPERTY_P', 'PROPERTY_T'],
        
        # Опциональные поля
        'optional_fields': [
            'PROPERTY_A',  # Дополнительный номер
            'PROPERTY_M',  # Применяемость
            'PROPERTY_C',  # Кросс-код
            'SECTION_ID',  # Категория
            'PRICE',
            'QUANTITY'
        ],
        
        # Альтернативные названия
        'field_aliases': {
            'TMP_ID': ['tmp_id', 'Id_tovar', 'PRODUCT_ID', 'ID', 'ProductID'],
            'NAME': ['name', 'Name', 'PRODUCT_NAME', 'ProductName'],
            'PROPERTY_P': ['property_p', 'BRAND_ID', 'BrandID', 'Id_brend'],
            'PROPERTY_T': ['property_t', 'CATALOG_NUMBER', 'CatalogNumber', 'ArticleNumber'],
            'PROPERTY_A': ['property_a', 'ADDITIONAL_NUMBER', 'AdditionalNumber'],
            'SECTION_ID': ['section_id', 'CATEGORY_ID', 'CategoryID']
        },
        
        # Ожидаемый диапазон
        'min_records': 100,
        'max_records': 500000,
        
        # Примеры
        'example_data': {
            'TMP_ID': '12345',
            'NAME': 'Фильтр масляный',
            'PROPERTY_P': 'B001',
            'PROPERTY_T': '0451103079'
        }
    },
    
    'analogs': {
        'name': 'OE Аналоги',
        'description': 'Кроссы и аналоги запчастей (~450,000 записей)',
        'command': 'import_oe_analogs_dbf',
        
        # Обязательные поля
        'required_fields': ['ID_oe', 'NAME', 'ID_TOVAR'],
        
        # Опциональные поля
        'optional_fields': [
            'NAME_STR',  # Очищенный номер (ИСПРАВЛЕНО: было Name_STR)
            'ID_BRENB'   # ID производителя аналога (ИСПРАВЛЕНО: было ID_BREND)
        ],
        
        # Альтернативные названия
        'field_aliases': {
            'ID_oe': ['id_oe', 'OE_ID', 'Id_oe', 'OEID', 'AnalogID', 'ID_OE'],
            'NAME': ['name', 'Name', 'OE_NUMBER', 'OeNumber', 'AnalogNumber'],
            'ID_TOVAR': ['id_tovar', 'PRODUCT_ID', 'Id_tovar', 'ProductID', 'TMP_ID'],
            'ID_BRENB': ['ID_brenb', 'id_brenb', 'ID_BREND', 'ID_brend', 'id_brend', 'BRAND_ID', 'Id_brend', 'BrandID'],
            'NAME_STR': ['Name_STR', 'name_str', 'NAME_CLEAN', 'CleanNumber']
        },
        
        # Ожидаемый диапазон
        'min_records': 100,
        'max_records': 1000000,
        
        # Примеры
        'example_data': {
            'ID_oe': 'OE12345',
            'NAME': '04E115561H',
            'ID_TOVAR': '12345',
            'ID_BREND': 'B001'
        }
    }
}


def get_schema(file_type):
    """
    Получить схему по типу файла
    
    Args:
        file_type: Тип файла ('brands', 'products', 'analogs')
        
    Returns:
        dict: Схема файла или None
    """
    return DBF_SCHEMAS.get(file_type)


def get_all_file_types():
    """
    Получить список всех поддерживаемых типов файлов
    
    Returns:
        list: Список кортежей (код, название) для использования в choices
    """
    return [
        (file_type, schema['name'])
        for file_type, schema in DBF_SCHEMAS.items()
    ]


def get_file_type_description(file_type):
    """
    Получить описание типа файла
    
    Args:
        file_type: Тип файла
        
    Returns:
        str: Описание или пустая строка
    """
    schema = get_schema(file_type)
    return schema['description'] if schema else ''


def get_required_fields_display(file_type):
    """
    Получить строку с обязательными полями для отображения
    
    Args:
        file_type: Тип файла
        
    Returns:
        str: Строка вида "ID_brend, NAME"
    """
    schema = get_schema(file_type)
    if schema:
        return ', '.join(schema['required_fields'])
    return ''


# Для использования в Django choices
FILE_TYPE_CHOICES = [
    ('brands', 'Бренды (ID_brend, NAME)'),
    ('products', 'Товары (TMP_ID, PROPERTY_P, PROPERTY_T)'),
    ('analogs', 'OE Аналоги (ID_oe, ID_TOVAR, ID_BREND)'),
]

