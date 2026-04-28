import logging

from celery import shared_task

from .models import PriceInquiry
from .notifications import (
    NonRetryableNotificationError,
    RetryableNotificationError,
    get_email_recipients,
    get_max_targets,
    get_telegram_targets,
    send_inquiry_email_to_recipient,
    send_inquiry_max_to_target,
    send_inquiry_telegram_to_target,
)


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2, default_retry_delay=10)
def notify_inquiry_email_recipient(self, inquiry_id, recipient):
    try:
        inquiry = PriceInquiry.objects.get(id=inquiry_id)
    except PriceInquiry.DoesNotExist:
        logger.warning("notify_inquiry_email_recipient: inquiry %s not found", inquiry_id)
        return {"status": "skipped", "reason": "inquiry_not_found"}

    try:
        result = send_inquiry_email_to_recipient(
            inquiry,
            recipient,
            raise_on_error=True,
        )
        return {"status": "done", "channel": "email", "recipient": recipient, "ok": result}
    except NonRetryableNotificationError as exc:
        logger.error(
            "notify_inquiry_email_recipient non-retryable error for inquiry %s recipient %s: %s",
            inquiry_id,
            recipient,
            exc,
        )
        return {
            "status": "failed",
            "channel": "email",
            "recipient": recipient,
            "reason": "non_retryable_error",
            "error": str(exc),
        }
    except RetryableNotificationError as exc:
        if self.request.retries >= self.max_retries:
            logger.error(
                "notify_inquiry_email_recipient retries exhausted for inquiry %s recipient %s: %s",
                inquiry_id,
                recipient,
                exc,
            )
            return {
                "status": "failed",
                "channel": "email",
                "recipient": recipient,
                "reason": "retries_exhausted",
                "error": str(exc),
            }
        countdown = 10 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        logger.exception(
            "notify_inquiry_email_recipient failed for inquiry %s recipient %s: %s",
            inquiry_id,
            recipient,
            exc,
        )
        if self.request.retries >= self.max_retries:
            return {
                "status": "failed",
                "channel": "email",
                "recipient": recipient,
                "reason": "unexpected_retries_exhausted",
                "error": str(exc),
            }
        countdown = 10 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def notify_inquiry_telegram_target(self, inquiry_id, chat_id, token):
    try:
        inquiry = PriceInquiry.objects.get(id=inquiry_id)
    except PriceInquiry.DoesNotExist:
        logger.warning("notify_inquiry_telegram_target: inquiry %s not found", inquiry_id)
        return {"status": "skipped", "reason": "inquiry_not_found"}

    try:
        result = send_inquiry_telegram_to_target(inquiry, chat_id, token)
        return {"status": "done", "channel": "telegram", "chat_id": chat_id, "ok": result}
    except Exception as exc:
        logger.exception(
            "notify_inquiry_telegram_target failed for inquiry %s target %s: %s",
            inquiry_id,
            chat_id,
            exc,
        )
        raise self.retry(exc=exc)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def notify_inquiry_max_target(self, inquiry_id, owner_id, token):
    try:
        inquiry = PriceInquiry.objects.get(id=inquiry_id)
    except PriceInquiry.DoesNotExist:
        logger.warning("notify_inquiry_max_target: inquiry %s not found", inquiry_id)
        return {"status": "skipped", "reason": "inquiry_not_found"}

    try:
        result = send_inquiry_max_to_target(inquiry, owner_id, token)
        return {"status": "done", "channel": "max", "owner_id": owner_id, "ok": result}
    except Exception as exc:
        logger.exception(
            "notify_inquiry_max_target failed for inquiry %s target %s: %s",
            inquiry_id,
            owner_id,
            exc,
        )
        raise self.retry(exc=exc)


def enqueue_inquiry_notifications(inquiry_id):
    # Отдельная задача на каждый email получатель
    email_recipients = get_email_recipients()
    for recipient in email_recipients:
        notify_inquiry_email_recipient.delay(inquiry_id, recipient)

    # Для Telegram в текущем проекте используется одна цель (канал+бот)
    tg_targets = get_telegram_targets()
    if tg_targets:
        chat_id, token = tg_targets[0]
        notify_inquiry_telegram_target.delay(inquiry_id, chat_id, token)

    # Для MAX в текущем проекте используется одна цель (owner_id+bot)
    max_targets = get_max_targets()
    if max_targets:
        owner_id, token = max_targets[0]
        notify_inquiry_max_target.delay(inquiry_id, owner_id, token)
