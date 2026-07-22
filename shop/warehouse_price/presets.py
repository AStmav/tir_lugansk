"""
Готовые шаблоны маппинга прайсов для формы «Загрузить прайс».

preset='custom' — ручные поля формы / сохранённый import_settings склада.
"""
from typing import Any, Dict, List, Optional, Tuple


PRESET_CUSTOM = 'custom'

# Ключ → человекочитаемое имя и настройки импорта
IMPORT_PRESETS: Dict[str, Dict[str, Any]] = {
    'kt_center': {
        'label': 'КТ Центр (CSV)',
        'description': 'Наименование;Производитель;Обозначение;Остаток;Цена',
        'settings': {
            'header_row': 1,
            'data_start_row': 2,
            'columns': {
                'article': 'Обозначение',
                'brand': 'Производитель',
                'price': 'Цена',
                'qty': 'Остаток',
            },
            'fixed_brand_id': None,
        },
    },
    'price_a': {
        'label': 'Прайс-А (XLSX)',
        'description': 'Заголовок на 5-й строке: Код, Бренд, Цена, Остаток, Код ID',
        'settings': {
            'header_row': 5,
            'data_start_row': 6,
            'columns': {
                'article': 'Код',
                'brand': 'Бренд',
                'price': 'Цена',
                'qty': 'Остаток',
                'external_id': 'Код ID',
            },
            'fixed_brand_id': None,
        },
    },
    'forum_auto': {
        'label': 'Forum Auto (XLSX)',
        'description': 'Заголовок на 3-й строке: № ПРОИЗВ., ГРУППА, ЦЕНА, НАЛичие',
        'settings': {
            'header_row': 3,
            'data_start_row': 4,
            'columns': {
                'article': '№ ПРОИЗВ.',
                'brand': 'ГРУППА',
                'price': 'ЦЕНА, РУБ',
                'qty': 'НАЛичие',
            },
            'fixed_brand_id': None,
        },
    },
}


def preset_choices() -> List[Tuple[str, str]]:
    choices = [(PRESET_CUSTOM, 'Свой (ручной маппинг)')]
    for key, meta in IMPORT_PRESETS.items():
        choices.append((key, meta['label']))
    return choices


def get_preset_settings(preset_key: str) -> Optional[Dict[str, Any]]:
    meta = IMPORT_PRESETS.get(preset_key or '')
    if not meta:
        return None
    settings = dict(meta['settings'])
    settings['columns'] = dict(meta['settings'].get('columns') or {})
    settings['preset'] = preset_key
    return settings


def settings_to_form_initial(settings: Dict[str, Any]) -> Dict[str, Any]:
    """import_settings → initial для WarehousePriceUploadForm."""
    columns = (settings or {}).get('columns') or {}
    return {
        'header_row': int((settings or {}).get('header_row') or 1),
        'data_start_row': int((settings or {}).get('data_start_row') or 2),
        'col_article': columns.get('article', ''),
        'col_brand': columns.get('brand', ''),
        'col_price': columns.get('price', ''),
        'col_qty': columns.get('qty', ''),
        'col_external_id': columns.get('external_id', ''),
        'fixed_brand': (settings or {}).get('fixed_brand_id'),
    }


def match_preset_key(settings: Dict[str, Any]) -> str:
    """Если сохранённый маппинг совпадает с шаблоном — вернуть его ключ."""
    if not settings:
        return PRESET_CUSTOM
    stored = settings.get('preset')
    if stored and stored in IMPORT_PRESETS:
        return stored

    header = int(settings.get('header_row') or 0)
    data_start = int(settings.get('data_start_row') or 0)
    columns = dict(settings.get('columns') or {})
    for key, meta in IMPORT_PRESETS.items():
        ps = meta['settings']
        if int(ps['header_row']) != header or int(ps['data_start_row']) != data_start:
            continue
        pc = ps.get('columns') or {}
        if all(columns.get(k) == v for k, v in pc.items()):
            return key
    return PRESET_CUSTOM


def presets_for_js() -> Dict[str, Dict[str, Any]]:
    """Данные для JS: ключ → поля формы."""
    payload: Dict[str, Dict[str, Any]] = {}
    for key, meta in IMPORT_PRESETS.items():
        payload[key] = settings_to_form_initial(meta['settings'])
        payload[key]['description'] = meta.get('description', '')
    return payload
