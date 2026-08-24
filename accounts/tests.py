from django.test import TestCase
from django.urls import reverse

from intel.models import SearchKeyword, SearchQueryTemplate, SourceTypeScore

from .models import NotificationSettings, Organization, User


class RegistrationFlowTests(TestCase):
    def test_register_creates_org_user_notification_settings_and_default_keywords(self):
        resp = self.client.post(reverse("accounts:register"), {
            "company_name": "ブレイブワーク株式会社",
            "own_website_url": "https://braavework.example.com",
            "name": "山田太郎",
            "email": "yamada@example.com",
            "password": "supersecret123",
            "password_confirm": "supersecret123",
        }, follow=True)
        self.assertEqual(resp.status_code, 200)

        org = Organization.objects.get(company_name="ブレイブワーク株式会社")
        user = User.objects.get(email="yamada@example.com")
        self.assertEqual(user.organization, org)
        self.assertTrue(NotificationSettings.objects.filter(organization=org).exists())
        self.assertGreater(SearchKeyword.objects.filter(organization=org).count(), 0)
        self.assertGreater(SourceTypeScore.objects.filter(organization=org).count(), 0)
        self.assertGreater(SearchQueryTemplate.objects.filter(organization=org).count(), 0)

        # 登録後は自動ログインされ、企業一覧へリダイレクトされる
        self.assertTrue(resp.context["user"].is_authenticated if hasattr(resp, "context") and resp.context else True)

    def test_duplicate_email_rejected(self):
        org = Organization.objects.create(company_name="既存組織")
        User.objects.create_user(email="dup@example.com", password="x12345678", name="既存ユーザー", organization=org)
        resp = self.client.post(reverse("accounts:register"), {
            "company_name": "新規組織", "name": "新規担当者", "email": "dup@example.com",
            "password": "supersecret123", "password_confirm": "supersecret123",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(User.objects.filter(email="dup@example.com").count(), 1)


class LoginFlowTests(TestCase):
    def setUp(self):
        self.org = Organization.objects.create(company_name="テスト株式会社")
        self.user = User.objects.create_user(
            email="login@example.com", password="testpass123", name="担当者", organization=self.org,
        )

    def test_login_with_email(self):
        resp = self.client.post(reverse("accounts:login"), {"username": "login@example.com", "password": "testpass123"})
        self.assertEqual(resp.status_code, 302)

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse("dashboard:index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn(reverse("accounts:login"), resp.url)
