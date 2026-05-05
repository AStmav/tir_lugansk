import logging
import asyncio
import socket
import smtplib
import json
from urllib import request as urllib_request
from urllib import error as urllib_error
from django.utils import timezone

from django.conf import settings
from django.core.mail import send_mail
from aiogram import Bot
from pages.models import NotificationRecipient, NotificationDelivery


logger = logging.getLogger(__name__)


class NotificationSendError(Exception):
    pass


class RetryableNotificationError(NotificationSendError):
    pass


class NonRetryableNotificationError(NotificationSendError):
    pass


def _delivery_key(inquiry, channel, recipient):
    return f"inquiry:{inquiry.id}|channel:{channel}|recipient:{recipient}"


def _log_delivery(inquiry, channel, recipient, status, error=""):
    key = _delivery_key(inquiry, channel, recipient)
    delivery, _created = NotificationDelivery.objects.get_or_create(
        idempotency_key=key,
        defaults={
            "inquiry": inquiry,
            "channel": channel,
            "recipient": recipient,
            "status": status,
            "attempt_count": 0,
        },
    )
    delivery.attempt_count += 1
    delivery.status = status
    delivery.last_error = (error or "")[:4000]
    if status == NotificationDelivery.STATUS_SENT:
        delivery.sent_at = timezone.now()
    delivery.save(
        update_fields=["attempt_count", "status", "last_error", "sent_at", "updated_at"]
    )


def get_email_recipients():
    # 1) Основной источник — получатели из админки (активные email)
    admin_recipients = list(
        NotificationRecipient.objects.filter(
            is_active=True,
            channel=NotificationRecipient.CHANNEL_EMAIL,
        ).values_list("value", flat=True)
    )
    if admin_recipients:
        return [email.strip() for email in admin_recipients if email and email.strip()]

    # 2) Fallback — значения из .env/settings
    recipients = getattr(settings, "NOTIFICATION_EMAIL_RECIPIENTS", [])
    if not recipients:
        return []
    return [email.strip() for email in recipients if email and email.strip()]


def get_telegram_targets():
    # 1) Основной источник — одна активная telegram-настройка из админки.
    rows = list(
        NotificationRecipient.objects.filter(
            is_active=True,
            channel=NotificationRecipient.CHANNEL_TELEGRAM,
        )
        .order_by("-updated_at", "-id")
        .values_list("value", "bot_token")
    )
    if rows:
        fallback_token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
        if len(rows) > 1:
            logger.warning(
                "Multiple active telegram recipients found (%s). Using only the newest one.",
                len(rows),
            )
        value, token = rows[0]
        chat_id = (value or "").strip()
        if chat_id:
            bot_token = (token or "").strip() or fallback_token
            return [(chat_id, bot_token)]
        return []

    # 2) Fallback — одиночная пара chat_id/token из .env/settings.
    token = (getattr(settings, "TELEGRAM_BOT_TOKEN", "") or "").strip()
    chat_id = (getattr(settings, "TELEGRAM_CHAT_ID", "") or "").strip()
    if token and chat_id:
        return [(chat_id, token)]
    return []


def get_max_targets():
    # 1) Основной источник — одна активная MAX-настройка из админки.
    rows = list(
        NotificationRecipient.objects.filter(
            is_active=True,
            channel=NotificationRecipient.CHANNEL_MAX,
        )
        .order_by("-updated_at", "-id")
        .values_list("value", "bot_token")
    )
    if rows:
        fallback_token = (getattr(settings, "MAX_BOT_TOKEN", "") or "").strip()
        if len(rows) > 1:
            logger.warning(
                "Multiple active MAX recipients found (%s). Using only the newest one.",
                len(rows),
            )
        owner_id, token = rows[0]
        owner_id = (owner_id or "").strip()
        if owner_id:
            bot_token = (token or "").strip() or fallback_token
            return [(owner_id, bot_token)]
        return []

    # 2) Fallback — одиночная пара owner_id/token из .env/settings.
    token = (getattr(settings, "MAX_BOT_TOKEN", "") or "").strip()
    owner_id = (getattr(settings, "MAX_OWNER_ID", "") or "").strip()
    if token and owner_id:
        return [(owner_id, token)]
    return []


def _build_subject(inquiry):
    if inquiry.request_type == "price":
        return f"[Запрос цены] {inquiry.name} | {inquiry.product_name or 'Товар'}"
    return f"[Заявка на звонок] {inquiry.name}"


def _build_body(inquiry):
    lines = [
        "Поступила новая заявка с сайта.",
        "",
        f"Тип заявки: {inquiry.get_request_type_display()}",
        f"Имя: {inquiry.name}",
        f"Телефон: {inquiry.phone}",
        f"Email: {inquiry.email or 'не указан'}",
        f"Комментарий: {getattr(inquiry, 'comment', '') or 'не указан'}",
        f"Дата: {inquiry.created_at:%Y-%m-%d %H:%M:%S}",
    ]
    if inquiry.request_type == "price":
        lines.extend(
            [
                "",
                f"ID товара: {inquiry.product_id or '-'}",
                f"Название товара: {inquiry.product_name or '-'}",
                f"Код товара: {inquiry.product_code or '-'}",
            ]
        )
    return "\n".join(lines)


def _classify_email_exception(exc):
    non_retryable = (
        smtplib.SMTPAuthenticationError,
        smtplib.SMTPRecipientsRefused,
        smtplib.SMTPSenderRefused,
        smtplib.SMTPNotSupportedError,
    )
    retryable = (
        smtplib.SMTPServerDisconnected,
        smtplib.SMTPConnectError,
        smtplib.SMTPDataError,
        socket.timeout,
        TimeoutError,
        ConnectionError,
    )

    if isinstance(exc, non_retryable):
        return NonRetryableNotificationError(str(exc))
    if isinstance(exc, retryable):
        return RetryableNotificationError(str(exc))

    if isinstance(exc, smtplib.SMTPException):
        return RetryableNotificationError(str(exc))
    if isinstance(exc, OSError):
        return RetryableNotificationError(str(exc))
    return NonRetryableNotificationError(str(exc))


def send_inquiry_email_notification(inquiry):
    recipients = get_email_recipients()
    if not recipients:
        logger.warning("Email recipients are empty, skip inquiry notification.")
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_EMAIL,
            "<no-email-recipients>",
            NotificationDelivery.STATUS_SKIPPED,
            "No active email recipients in admin and .env fallback is empty.",
        )
        return False

    subject = _build_subject(inquiry)
    body = _build_body(inquiry)

    at_least_one_sent = False
    last_error = ""
    try:
        for recipient in recipients:
            try:
                sent = send_mail(
                    subject=subject,
                    message=body,
                    from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
                    recipient_list=[recipient],
                    fail_silently=False,
                )
                if sent:
                    at_least_one_sent = True
                    _log_delivery(
                        inquiry,
                        NotificationRecipient.CHANNEL_EMAIL,
                        recipient,
                        NotificationDelivery.STATUS_SENT,
                    )
                else:
                    _log_delivery(
                        inquiry,
                        NotificationRecipient.CHANNEL_EMAIL,
                        recipient,
                        NotificationDelivery.STATUS_FAILED,
                        "SMTP backend returned 0 sent messages.",
                    )
            except Exception as per_recipient_exc:
                last_error = str(per_recipient_exc)
                _log_delivery(
                    inquiry,
                    NotificationRecipient.CHANNEL_EMAIL,
                    recipient,
                    NotificationDelivery.STATUS_FAILED,
                    last_error,
                )
                logger.exception(
                    "Failed to send inquiry #%s email notification to %s: %s",
                    inquiry.id,
                    recipient,
                    per_recipient_exc,
                )
        if at_least_one_sent:
            logger.info(
                "Inquiry #%s email notification sent to %s",
                inquiry.id,
                ", ".join(recipients),
            )
            return True
        logger.warning("Inquiry #%s email notification was not sent.", inquiry.id)
        return False
    except Exception as exc:
        last_error = str(exc)
        for recipient in recipients:
            _log_delivery(
                inquiry,
                NotificationRecipient.CHANNEL_EMAIL,
                recipient,
                NotificationDelivery.STATUS_FAILED,
                last_error,
            )
        logger.exception("Failed to send inquiry #%s email notification: %s", inquiry.id, exc)
        return False


def send_inquiry_telegram_notification(inquiry):
    targets = get_telegram_targets()
    if not targets:
        logger.warning("Telegram config is empty, skip inquiry notification.")
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_TELEGRAM,
            "<no-telegram-targets>",
            NotificationDelivery.STATUS_SKIPPED,
            "No active telegram recipients and .env fallback is empty.",
        )
        return False

    message = _build_body(inquiry)
    at_least_one_sent = False

    for chat_id, token in targets:
        if not token:
            logger.warning(
                "Inquiry #%s telegram target %s skipped: missing bot token.",
                inquiry.id,
                chat_id,
            )
            continue
        try:
            async def _send():
                bot = Bot(token=token)
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        disable_web_page_preview=True,
                    )
                    return True
                finally:
                    await bot.session.close()

            result = asyncio.run(_send())
            if result:
                at_least_one_sent = True
                _log_delivery(
                    inquiry,
                    NotificationRecipient.CHANNEL_TELEGRAM,
                    chat_id,
                    NotificationDelivery.STATUS_SENT,
                )
                logger.info("Inquiry #%s telegram notification sent to %s.", inquiry.id, chat_id)
            else:
                _log_delivery(
                    inquiry,
                    NotificationRecipient.CHANNEL_TELEGRAM,
                    chat_id,
                    NotificationDelivery.STATUS_FAILED,
                    "Telegram API returned non-success result.",
                )
                logger.warning(
                    "Inquiry #%s telegram notification not sent to %s.",
                    inquiry.id,
                    chat_id,
                )
        except Exception as exc:
            _log_delivery(
                inquiry,
                NotificationRecipient.CHANNEL_TELEGRAM,
                chat_id,
                NotificationDelivery.STATUS_FAILED,
                str(exc),
            )
            logger.exception(
                "Failed to send inquiry #%s telegram notification to %s: %s",
                inquiry.id,
                chat_id,
                exc,
            )

    return at_least_one_sent


def send_inquiry_max_notification(inquiry):
    targets = get_max_targets()
    if not targets:
        logger.warning("MAX config is empty, skip inquiry notification.")
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_MAX,
            "<no-max-targets>",
            NotificationDelivery.STATUS_SKIPPED,
            "No active MAX recipients and .env fallback is empty.",
        )
        return False

    at_least_one_sent = False
    for owner_id, token in targets:
        result = send_inquiry_max_to_target(inquiry, owner_id, token)
        at_least_one_sent = at_least_one_sent or result
    return at_least_one_sent


def send_inquiry_notifications(inquiry):
    results = {
        "email": send_inquiry_email_notification(inquiry),
        "telegram": send_inquiry_telegram_notification(inquiry),
        "max": send_inquiry_max_notification(inquiry),
    }
    return results


def send_inquiry_email_to_recipient(inquiry, recipient, raise_on_error=False):
    recipient = (recipient or "").strip()
    if not recipient:
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_EMAIL,
            "<empty-recipient>",
            NotificationDelivery.STATUS_SKIPPED,
            "Empty email recipient.",
        )
        return False

    subject = _build_subject(inquiry)
    body = _build_body(inquiry)
    try:
        sent = send_mail(
            subject=subject,
            message=body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
            recipient_list=[recipient],
            fail_silently=False,
        )
        if sent:
            _log_delivery(
                inquiry,
                NotificationRecipient.CHANNEL_EMAIL,
                recipient,
                NotificationDelivery.STATUS_SENT,
            )
            logger.info("Inquiry #%s email notification sent to %s", inquiry.id, recipient)
            return True
        error_text = "SMTP backend returned 0 sent messages."
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_EMAIL,
            recipient,
            NotificationDelivery.STATUS_FAILED,
            error_text,
        )
        if raise_on_error:
            raise RetryableNotificationError(error_text)
        return False
    except Exception as exc:
        classified_exc = _classify_email_exception(exc)
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_EMAIL,
            recipient,
            NotificationDelivery.STATUS_FAILED,
            str(classified_exc),
        )
        logger.exception(
            "Failed to send inquiry #%s email notification to %s: %s",
            inquiry.id,
            recipient,
            exc,
        )
        if raise_on_error:
            raise classified_exc from exc
        return False


def send_inquiry_telegram_to_target(inquiry, chat_id, token):
    chat_id = (chat_id or "").strip()
    token = (token or "").strip()
    if not chat_id or not token:
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_TELEGRAM,
            chat_id or "<empty-chat-id>",
            NotificationDelivery.STATUS_SKIPPED,
            "Missing telegram chat_id or bot token.",
        )
        return False

    message = _build_body(inquiry)
    try:
        async def _send():
            bot = Bot(token=token)
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text=message,
                    disable_web_page_preview=True,
                )
                return True
            finally:
                await bot.session.close()

        result = asyncio.run(_send())
        if result:
            _log_delivery(
                inquiry,
                NotificationRecipient.CHANNEL_TELEGRAM,
                chat_id,
                NotificationDelivery.STATUS_SENT,
            )
            logger.info("Inquiry #%s telegram notification sent to %s.", inquiry.id, chat_id)
            return True

        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_TELEGRAM,
            chat_id,
            NotificationDelivery.STATUS_FAILED,
            "Telegram API returned non-success result.",
        )
        return False
    except Exception as exc:
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_TELEGRAM,
            chat_id,
            NotificationDelivery.STATUS_FAILED,
            str(exc),
        )
        logger.exception(
            "Failed to send inquiry #%s telegram notification to %s: %s",
            inquiry.id,
            chat_id,
            exc,
        )
        return False


def send_inquiry_max_to_target(inquiry, owner_id, token):
    owner_id = (owner_id or "").strip()
    token = (token or "").strip()
    if not owner_id or not token:
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_MAX,
            owner_id or "<empty-owner-id>",
            NotificationDelivery.STATUS_SKIPPED,
            "Missing MAX owner_id or bot token.",
        )
        return False

    message = _build_body(inquiry)
    api_base = (getattr(settings, "MAX_API_BASE_URL", "") or "").rstrip("/")
    if not api_base:
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_MAX,
            owner_id,
            NotificationDelivery.STATUS_FAILED,
            "MAX_API_BASE_URL is empty.",
        )
        return False

    url = f"{api_base}/bot{token}/sendMessage"
    payload = json.dumps({"chat_id": owner_id, "text": message}).encode("utf-8")
    req = urllib_request.Request(
        url=url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=15) as response:
            status_code = getattr(response, "status", None) or response.getcode()
            if 200 <= status_code < 300:
                _log_delivery(
                    inquiry,
                    NotificationRecipient.CHANNEL_MAX,
                    owner_id,
                    NotificationDelivery.STATUS_SENT,
                )
                logger.info("Inquiry #%s MAX notification sent to %s.", inquiry.id, owner_id)
                return True

            _log_delivery(
                inquiry,
                NotificationRecipient.CHANNEL_MAX,
                owner_id,
                NotificationDelivery.STATUS_FAILED,
                f"MAX API returned HTTP {status_code}",
            )
            return False
    except (urllib_error.URLError, urllib_error.HTTPError, TimeoutError, OSError) as exc:
        _log_delivery(
            inquiry,
            NotificationRecipient.CHANNEL_MAX,
            owner_id,
            NotificationDelivery.STATUS_FAILED,
            str(exc),
        )
        logger.exception(
            "Failed to send inquiry #%s MAX notification to %s: %s",
            inquiry.id,
            owner_id,
            exc,
        )
        return False
