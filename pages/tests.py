from unittest.mock import AsyncMock, MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from pages.models import PriceInquiry
from pages.notifications import _build_body, send_inquiry_email_notification, send_inquiry_telegram_notification


class CallRequestCommentNotificationTests(TestCase):
    """Заявка на звонок: комментарий в БД и в тексте email / Telegram."""

    def test_build_body_call_inquiry_includes_comment(self):
        inquiry = PriceInquiry.objects.create(
            name="Иван",
            phone="+7 (999) 000-00-00",
            email="i@test.ru",
            comment="Перезвоните после 18:00, московское время",
            request_type="call",
        )
        body = _build_body(inquiry)
        self.assertIn("Тип заявки: Заявка на звонок", body)
        self.assertIn("Комментарий: Перезвоните после 18:00, московское время", body)

    @patch("pages.views.enqueue_inquiry_notifications")
    def test_call_request_post_persists_comment(self, _mock_enqueue):
        url = reverse("pages:call_request")
        comment = "Удобно звонить только по будням"
        response = self.client.post(
            url,
            {
                "userName": "Мария",
                "userPhone": "+7 (999) 111-22-33",
                "userEmail": "m@example.com",
                "comment": comment,
                "personal_data_consent": "1",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        inquiry = PriceInquiry.objects.order_by("-id").first()
        self.assertEqual(inquiry.request_type, "call")
        self.assertEqual(inquiry.comment, comment)
        self.assertIn(comment, _build_body(inquiry))
        self.assertTrue(inquiry.personal_data_consent)
        self.assertIsNotNone(inquiry.consent_at)

    @patch("pages.views.enqueue_inquiry_notifications")
    def test_call_request_requires_personal_data_consent(self, _mock_enqueue):
        url = reverse("pages:call_request")
        response = self.client.post(
            url,
            {
                "userName": "Мария",
                "userPhone": "+7 (999) 111-22-33",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["success"])
        self.assertEqual(PriceInquiry.objects.count(), 0)

    @patch("pages.notifications.get_email_recipients")
    @patch("pages.notifications.send_mail")
    def test_send_inquiry_email_includes_comment_for_call(self, mock_send_mail, mock_recipients):
        mock_recipients.return_value = ["notify@example.com"]
        mock_send_mail.return_value = 1
        inquiry = PriceInquiry.objects.create(
            name="Пётр",
            phone="+7 (999) 222-33-44",
            email="p@example.com",
            comment="Вопрос по доставке в регион",
            request_type="call",
        )
        self.assertTrue(send_inquiry_email_notification(inquiry))
        mock_send_mail.assert_called_once()
        kwargs = mock_send_mail.call_args.kwargs
        self.assertIn("Комментарий: Вопрос по доставке в регион", kwargs["message"])
        self.assertIn("Заявка на звонок", kwargs["message"])

    @patch("pages.notifications.get_telegram_targets")
    @patch("pages.notifications.Bot")
    def test_send_inquiry_telegram_includes_comment_for_call(self, mock_bot_cls, mock_targets):
        mock_targets.return_value = [("123456789", "fake-bot-token")]
        bot_instance = MagicMock()
        bot_instance.send_message = AsyncMock(return_value=True)
        bot_instance.session = MagicMock()
        bot_instance.session.close = AsyncMock()
        mock_bot_cls.return_value = bot_instance

        inquiry = PriceInquiry.objects.create(
            name="Анна",
            phone="+7 (999) 333-44-55",
            email="",
            comment="Оставьте сообщение в Telegram, если не дозвонитесь",
            request_type="call",
        )
        self.assertTrue(send_inquiry_telegram_notification(inquiry))
        bot_instance.send_message.assert_awaited_once()
        sent = bot_instance.send_message.await_args.kwargs["text"]
        self.assertIn("Комментарий: Оставьте сообщение в Telegram, если не дозвонитесь", sent)
        self.assertIn("Заявка на звонок", sent)
