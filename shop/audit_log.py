"""
Аудит критических действий: запись в logs/audit.log.
Формат строки: действие | user | объект/детали (без паролей и персональных данных).
"""
import logging

_audit_logger = None


def _get_audit_logger():
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = logging.getLogger('audit')
    return _audit_logger


def _user_repr(user):
    if user is None:
        return '—'
    if getattr(user, 'is_anonymous', True):
        return '—'
    return str(user) or getattr(user, 'username', '—')


def log_audit(action, user=None, user_repr=None, detail=None, **extra):
    """
    Пишет одну строку в audit.log.
    action — тип события (product_created, product_updated, product_deleted, import_uploaded, import_started, import_completed, import_failed, import_cancelled).
    user — request.user или None.
    user_repr — строка «кто» (если вызов из потока без request.user).
    detail — краткое описание (название товара, имя файла, причина ошибки и т.п.).
    extra — доп. пары ключ=значение для строки (object_id, file_type, file_size и т.д.).
    """
    logger = _get_audit_logger()
    who = user_repr if user_repr is not None else _user_repr(user)
    parts = [action, who]
    if detail:
        parts.append(str(detail)[:500])
    for k, v in extra.items():
        if v is not None:
            parts.append(f'{k}={v}')
    message = ' | '.join(parts)
    logger.info(message)
