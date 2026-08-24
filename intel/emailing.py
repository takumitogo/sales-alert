"""
アラートメール送信。技術設計書5章 / 元設計書18章の本文フォーマットに対応。
Gmail SMTP を想定しているが、EMAIL_BACKEND は環境変数で切り替え可能。
"""

from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils import timezone

from companies.models import Company

SOURCE_TYPE_LABELS = dict([
    ("official_hp", "公式HP"),
    ("ir", "IR"),
    ("official_recruit", "公式採用ページ"),
    ("official_press", "公式プレスリリース"),
    ("industry_media", "業界メディア"),
    ("other_web", "その他Web記事"),
])

CATEGORY_LABELS = dict(Company.CATEGORY_CHOICES)


def send_alert_email(alert):
    document = alert.web_document
    company = alert.company
    org = alert.organization
    notif = getattr(org, "notification_settings", None)
    if not notif or not notif.notify_email:
        return False

    admin_url = f"{settings.SITE_BASE_URL}/companies/{company.id}/"
    subject = f"【営業機会アラート｜{alert.score}点】{company.company_name}"
    body = render_to_string("emails/alert_email.txt", {
        "company": company,
        "document": document,
        "alert": alert,
        "matched_keywords": document.matched_keywords,
        "source_type_label": SOURCE_TYPE_LABELS.get(document.source_type, "その他Web記事"),
        "category_label": CATEGORY_LABELS.get(company.category, "その他"),
        "admin_url": admin_url,
    })
    send_mail(
        subject=subject,
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[notif.notify_email],
        fail_silently=False,
    )
    alert.email_sent = True
    alert.email_sent_at = timezone.now()
    alert.save(update_fields=["email_sent", "email_sent_at"])
    return True
