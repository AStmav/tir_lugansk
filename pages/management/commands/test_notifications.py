from dataclasses import dataclass, field
from datetime import datetime

from django.core.management.base import BaseCommand

from pages.notifications import (
    send_inquiry_email_notification,
    send_inquiry_telegram_notification,
)


@dataclass
class DummyInquiry:
    id: str
    name: str
    phone: str
    email: str
    request_type: str
    product_id: str = ""
    product_name: str = ""
    product_code: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def get_request_type_display(self):
        return "Запрос цены товара" if self.request_type == "price" else "Заявка на звонок"


class Command(BaseCommand):
    help = "Send test notification to email and/or telegram."

    def add_arguments(self, parser):
        parser.add_argument(
            "--type",
            choices=["call", "price"],
            default="call",
            help="Inquiry type for test payload.",
        )
        parser.add_argument(
            "--name",
            default="Тестовый клиент",
            help="Client name in test payload.",
        )
        parser.add_argument(
            "--phone",
            default="+7 (900) 000-00-00",
            help="Client phone in test payload.",
        )
        parser.add_argument(
            "--email",
            default="test@example.com",
            help="Client email in test payload.",
        )
        parser.add_argument(
            "--only-email",
            action="store_true",
            help="Send only email notification.",
        )
        parser.add_argument(
            "--only-telegram",
            action="store_true",
            help="Send only telegram notification.",
        )

    def handle(self, *args, **options):
        if options["only_email"] and options["only_telegram"]:
            self.stderr.write("Нельзя использовать одновременно --only-email и --only-telegram.")
            return

        inquiry_type = options["type"]
        inquiry = DummyInquiry(
            id="TEST",
            name=options["name"],
            phone=options["phone"],
            email=options["email"],
            request_type=inquiry_type,
            product_id="TEST-ID-001" if inquiry_type == "price" else "",
            product_name="Тестовый товар" if inquiry_type == "price" else "",
            product_code="TEST-CODE-001" if inquiry_type == "price" else "",
            created_at=datetime.now(),
        )

        send_email = not options["only_telegram"]
        send_telegram = not options["only_email"]

        results = {}
        if send_email:
            results["email"] = send_inquiry_email_notification(inquiry)
        if send_telegram:
            results["telegram"] = send_inquiry_telegram_notification(inquiry)

        for channel, success in results.items():
            if success:
                self.stdout.write(self.style.SUCCESS(f"{channel}: OK"))
            else:
                self.stdout.write(self.style.WARNING(f"{channel}: FAILED"))

