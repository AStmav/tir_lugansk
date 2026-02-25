"""
Валидатор структуры DBF файлов

Этот модуль содержит логику проверки соответствия загруженных DBF файлов
ожидаемым структурам данных перед импортом.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict

try:
    from dbfread import DBF
except ImportError:
    DBF = None

from ..dbf_schemas import DBF_SCHEMAS

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """
    Результат валидации DBF файла
    
    Attributes:
        is_valid: Прошел ли файл валидацию
        message: Сообщение о результате валидации
        found_fields: Список полей, найденных в файле
        missing_fields: Список отсутствующих обязательных полей
        record_count: Количество записей в файле
        suggested_type: Предложенный тип файла (если текущий не подходит)
        warnings: Список предупреждений
        errors: Список ошибок
    """
    is_valid: bool = False
    message: str = ''
    found_fields: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    record_count: int = 0
    suggested_type: Optional[str] = None
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    
    def to_dict(self):
        """Конвертация в словарь для JSON"""
        return {
            'is_valid': self.is_valid,
            'message': self.message,
            'found_fields': self.found_fields,
            'missing_fields': self.missing_fields,
            'record_count': self.record_count,
            'suggested_type': self.suggested_type,
            'warnings': self.warnings,
            'errors': self.errors
        }


class DBFValidator:
    """
    Валидатор структуры DBF файлов
    
    Проверяет соответствие загруженного файла ожидаемой структуре
    на основе схем из dbf_schemas.py
    """
    
    def __init__(self):
        """Инициализация валидатора"""
        if not DBF:
            raise ImportError(
                "Модуль dbfread не установлен. "
                "Установите: pip install dbfread"
            )
    
    def validate_file(self, file_path: str, expected_type: str) -> ValidationResult:
        """
        Главная функция валидации файла
        
        Args:
            file_path: Путь к DBF файлу
            expected_type: Ожидаемый тип ('brands', 'products', 'analogs')
            
        Returns:
            ValidationResult: Результат валидации
        """
        result = ValidationResult()
        
        # 1. Проверка существования файла
        if not os.path.exists(file_path):
            result.is_valid = False
            result.message = f"❌ Файл не найден: {file_path}"
            result.errors.append("Файл не существует")
            logger.error(f"Файл не найден: {file_path}")
            return result
        
        # 2. Проверка расширения
        if not file_path.lower().endswith('.dbf'):
            result.is_valid = False
            result.message = "❌ Файл должен иметь расширение .dbf"
            result.errors.append("Неверное расширение файла")
            return result
        
        # 3. Получение схемы
        schema = DBF_SCHEMAS.get(expected_type)
        if not schema:
            result.is_valid = False
            result.message = f"❌ Неизвестный тип файла: {expected_type}"
            result.errors.append(f"Тип '{expected_type}' не поддерживается")
            return result
        
        # 4. Чтение структуры DBF
        try:
            file_fields = self.get_file_fields(file_path)
            result.found_fields = file_fields
            logger.info(f"Найдено полей в файле: {len(file_fields)}")
        except Exception as e:
            result.is_valid = False
            result.message = f"❌ Ошибка чтения файла: {str(e)}"
            result.errors.append(f"Ошибка чтения: {str(e)}")
            logger.error(f"Ошибка чтения DBF: {e}")
            return result
        
        # 5. Проверка обязательных полей
        missing = self.check_required_fields(file_fields, schema)
        result.missing_fields = missing
        
        if missing:
            result.is_valid = False
            result.message = self._format_error_message(missing, schema, file_fields)
            
            # Предложить альтернативный тип
            result.suggested_type = self.suggest_file_type(file_fields)
            
            logger.warning(f"Отсутствуют обязательные поля: {missing}")
            return result
        
        # 6. Подсчет записей
        try:
            result.record_count = self.get_record_count(file_path)
            logger.info(f"Записей в файле: {result.record_count}")
        except Exception as e:
            result.warnings.append(f"Не удалось подсчитать записи: {e}")
        
        # 7. Проверка диапазона записей
        if result.record_count > 0:
            if result.record_count < schema['min_records']:
                result.warnings.append(
                    f"⚠️ Мало записей: {result.record_count} "
                    f"(ожидается минимум {schema['min_records']})"
                )
            
            if result.record_count > schema['max_records']:
                result.warnings.append(
                    f"⚠️ Много записей: {result.record_count} "
                    f"(обычно до {schema['max_records']}). "
                    f"Возможно, это файл другого типа?"
                )
        
        # 8. Успех!
        result.is_valid = True
        result.message = (
            f"✅ Файл соответствует типу '{schema['name']}'\n"
            f"📊 Найдено записей: {result.record_count:,}\n"
            f"📋 Обнаружено полей: {len(file_fields)}"
        )
        
        logger.info(f"Валидация успешна: {expected_type}, записей: {result.record_count}")
        
        return result
    
    def get_file_fields(self, file_path: str) -> List[str]:
        """
        Извлекает список полей из DBF файла
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            list: Список названий полей
        """
        try:
            table = DBF(file_path, load=False)  # Не загружаем данные, только структуру
            fields = table.field_names
            logger.debug(f"Поля файла: {fields}")
            return fields
        except Exception as e:
            logger.error(f"Ошибка чтения полей: {e}")
            raise
    
    def check_required_fields(self, file_fields: List[str], schema: Dict) -> List[str]:
        """
        Проверяет наличие обязательных полей
        
        Args:
            file_fields: Список полей в файле
            schema: Схема ожидаемой структуры
            
        Returns:
            list: Список отсутствующих обязательных полей
        """
        missing_fields = []
        required_fields = schema['required_fields']
        field_aliases = schema.get('field_aliases', {})
        
        # Приводим все поля файла к uppercase для сравнения
        file_fields_upper = [f.upper() for f in file_fields]
        
        for required_field in required_fields:
            # Проверяем основное название
            if required_field.upper() in file_fields_upper:
                continue
            
            # Проверяем альтернативные названия
            aliases = field_aliases.get(required_field, [])
            found = any(alias.upper() in file_fields_upper for alias in aliases)
            
            if not found:
                missing_fields.append(required_field)
        
        return missing_fields
    
    def suggest_file_type(self, file_fields: List[str]) -> Optional[str]:
        """
        Автоматически предлагает тип файла на основе найденных полей
        
        Args:
            file_fields: Список полей в файле
            
        Returns:
            str: Предложенный тип или None
        """
        file_fields_upper = [f.upper() for f in file_fields]
        best_match = None
        best_score = 0
        
        for file_type, schema in DBF_SCHEMAS.items():
            score = 0
            required_fields = schema['required_fields']
            field_aliases = schema.get('field_aliases', {})
            
            # Подсчитываем совпадения
            for required_field in required_fields:
                if required_field.upper() in file_fields_upper:
                    score += 2  # Основное поле = 2 балла
                    continue
                
                # Проверяем aliases
                aliases = field_aliases.get(required_field, [])
                if any(alias.upper() in file_fields_upper for alias in aliases):
                    score += 1  # Альтернатива = 1 балл
            
            if score > best_score:
                best_score = score
                best_match = file_type
        
        # Возвращаем только если уверенность > 50%
        total_required = len(DBF_SCHEMAS[best_match]['required_fields']) * 2
        if best_score >= total_required * 0.5:
            return best_match
        
        return None
    
    def get_record_count(self, file_path: str) -> int:
        """
        Подсчитывает количество записей в файле
        
        Args:
            file_path: Путь к файлу
            
        Returns:
            int: Количество записей
        """
        try:
            table = DBF(file_path, load=False)
            return len(table)
        except Exception as e:
            logger.error(f"Ошибка подсчета записей: {e}")
            return 0
    
    def get_sample_records(self, file_path: str, count: int = 3) -> List[Dict]:
        """
        Возвращает примеры первых записей из файла
        
        Args:
            file_path: Путь к файлу
            count: Количество записей
            
        Returns:
            list: Список словарей с данными
        """
        try:
            table = DBF(file_path)
            samples = []
            for i, record in enumerate(table):
                if i >= count:
                    break
                samples.append(dict(record))
            return samples
        except Exception as e:
            logger.error(f"Ошибка получения примеров: {e}")
            return []
    
    def _format_error_message(
        self, 
        missing_fields: List[str], 
        schema: Dict,
        file_fields: List[str]
    ) -> str:
        """
        Форматирует сообщение об ошибке валидации
        
        Args:
            missing_fields: Отсутствующие поля
            schema: Схема файла
            file_fields: Найденные поля
            
        Returns:
            str: Форматированное сообщение
        """
        message = f"❌ Файл НЕ соответствует типу '{schema['name']}'\n\n"
        message += "📋 Отсутствуют обязательные поля:\n"
        
        for field in missing_fields:
            aliases = schema.get('field_aliases', {}).get(field, [])
            if aliases:
                aliases_str = ', '.join(aliases[:3])  # Показываем первые 3
                message += f"   • {field} (или {aliases_str})\n"
            else:
                message += f"   • {field}\n"
        
        message += f"\n🔍 Найденные поля в файле:\n"
        message += f"   {', '.join(file_fields[:10])}"  # Показываем первые 10
        if len(file_fields) > 10:
            message += f"... (+{len(file_fields) - 10} еще)"
        
        # Предложение
        suggested = self.suggest_file_type(file_fields)
        if suggested and suggested != schema:
            suggested_schema = DBF_SCHEMAS[suggested]
            message += f"\n\n💡 Похоже, это файл типа '{suggested_schema['name']}'"
        
        return message

