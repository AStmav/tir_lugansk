from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from pages.models import HelpfulMenuItem, PriceInquiry, UsefulCategory, UsefulPost
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


PUBLIC_PAGE_TEMPLATES = (
    "index.html",
    "catalog.html",
    "product.html",
    "about.html",
    "contacts.html",
    "page_detail.html",
    "useful_section.html",
    "useful_post_detail.html",
)


class PublicTemplateConsistencyTests(TestCase):
    """Общие include: меню «Полезное», favicon, подвал, счётчики."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.templates_dir = Path(settings.BASE_DIR) / "templates"

    def test_public_templates_use_shared_includes(self):
        required = (
            "includes/header_useful_menu.html",
            "includes/head_common.html",
            "includes/footer_links.html",
            "includes/analytics_scripts.html",
        )
        for name in PUBLIC_PAGE_TEMPLATES:
            content = (self.templates_dir / name).read_text(encoding="utf-8")
            for include_path in required:
                with self.subTest(template=name, include=include_path):
                    self.assertIn(include_path, content)

    def test_useful_section_has_no_hardcoded_legacy_menu(self):
        content = (self.templates_dir / "useful_section.html").read_text(encoding="utf-8")
        self.assertNotIn("{% url 'pages:news' %}", content)
        self.assertNotIn("{% url 'pages:catalogs' %}", content)
        self.assertNotIn("{% url 'pages:articles' %}", content)

    def test_helpful_menu_item_renders_on_home(self):
        category = UsefulCategory.objects.create(
            title="Тестовый раздел",
            slug="test-useful",
            is_active=True,
        )
        HelpfulMenuItem.objects.create(
            title="Тест меню",
            useful_category=category,
            url="/news/",
            is_active=True,
            order=1,
        )
        response = self.client.get(reverse("pages:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Тест меню")
        self.assertContains(response, reverse("pages:useful_category", kwargs={"slug": "test-useful"}))

    def test_useful_category_page_has_favicon_in_html(self):
        UsefulCategory.objects.update_or_create(
            slug="news",
            defaults={"title": "Новости", "is_active": True},
        )
        response = self.client.get(reverse("pages:useful_category", kwargs={"slug": "news"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "favicon")
        self.assertContains(response, "apple-touch-icon")

    def test_useful_legacy_url_redirects_to_short_url(self):
        UsefulCategory.objects.update_or_create(
            slug="codestmc",
            defaults={"title": "Коды номенклатуры", "is_active": True},
        )
        response = self.client.get(reverse("pages:useful_category_legacy", kwargs={"slug": "codestmc"}))
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response["Location"], reverse("pages:useful_category", kwargs={"slug": "codestmc"}))

    def test_new_useful_category_uses_short_url_by_default(self):
        category = UsefulCategory.objects.create(
            title="Коды",
            slug="codes",
            is_active=True,
        )
        response = self.client.get(reverse("pages:useful_category", kwargs={"slug": "codes"}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, category.title)
        self.assertEqual(category.get_absolute_url(), "/codes/")

    def test_useful_category_pagination(self):
        category = UsefulCategory.objects.create(
            title="Статьи тест",
            slug="articles-test",
            is_active=True,
            posts_per_page=2,
        )
        for index in range(5):
            UsefulPost.objects.create(
                category=category,
                title=f"Материал {index + 1}",
                summary=f"Текст {index + 1}",
                is_active=True,
            )

        first_page = self.client.get(reverse("pages:useful_category", kwargs={"slug": "articles-test"}))
        self.assertEqual(first_page.status_code, 200)
        self.assertContains(first_page, "Материал 1")
        self.assertContains(first_page, "Материал 2")
        self.assertNotContains(first_page, "Материал 3")
        self.assertContains(first_page, "pagination__current")

        second_page = self.client.get(
            reverse("pages:useful_category", kwargs={"slug": "articles-test"}) + "?page=2"
        )
        self.assertEqual(second_page.status_code, 200)
        self.assertContains(second_page, "Материал 3")
        self.assertNotContains(second_page, "Материал 1")

    def test_shop_urls_are_not_shadowed_by_useful_short_routes(self):
        response = self.client.get("/shop/catalog/")
        self.assertEqual(response.status_code, 200)
