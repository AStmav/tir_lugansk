from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Optional


DEFAULT_IMPORT_SETTINGS: Dict[str, Any] = {
    'header_row': 1,
    'data_start_row': 2,
    'columns': {},
    'fixed_brand_id': None,
}


@dataclass
class ParsedPriceRow:
    row_number: int
    article: str
    brand: str
    price: Optional[Decimal]
    quantity: int
    external_id: str


@dataclass
class RowSkip:
    row_number: int
    reason: str
    article: str = ''
    brand: str = ''


@dataclass
class ImportStats:
    total: int = 0
    updated: int = 0
    skipped: int = 0
    errors: List[RowSkip] = field(default_factory=list)
