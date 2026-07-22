import re
from typing import Any, Dict, List, Optional


def column_letter_to_index(letter: str) -> Optional[int]:
    letter = (letter or '').strip().upper()
    if not letter or not re.fullmatch(r'[A-Z]+', letter):
        return None
    index = 0
    for char in letter:
        index = index * 26 + (ord(char) - ord('A') + 1)
    return index - 1


def resolve_column_index(ref: str, header_cells: List[str]) -> Optional[int]:
    ref = (ref or '').strip()
    if not ref:
        return None
    if ref.isdigit():
        return int(ref)
    letter_index = column_letter_to_index(ref)
    if letter_index is not None:
        return letter_index
    ref_lower = ref.lower()
    for idx, header in enumerate(header_cells):
        if header and header.strip().lower() == ref_lower:
            return idx
    for idx, header in enumerate(header_cells):
        if header and ref_lower in header.strip().lower():
            return idx
    return None


def build_column_indexes(column_map: Dict[str, str], header_cells: List[str]) -> Dict[str, int]:
    indexes: Dict[str, int] = {}
    for field_name, ref in (column_map or {}).items():
        if not ref:
            continue
        idx = resolve_column_index(str(ref), header_cells)
        if idx is not None:
            indexes[field_name] = idx
    return indexes
