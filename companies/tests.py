from django.test import TestCase
from django.urls import reverse

from accounts.models import Organization, User
from companies.csv_utils import decode_csv_bytes, guess_mapping, parse_csv_text
from intel.bootstrap import seed_defaults_for_organization

from .models import Company


class CsvMappingGuessTests(TestCase):
    def test_guesses_company_name_and_hp_variants(self):
        # 元設計書7章：「会社名」「企業名」「法人名」「顧客名」等はすべて企業名候補として扱う
        for header_name in ["会社名", "企業名", "法人名", "顧客名"]:
            guesses = guess_mapping([header_name, "URL"])
            self.assertEqual(guesses["company_name"], header_name)

    def test_guesses_hp_url_variants(self):
        for header_name in ["HP", "URL", "Webサイト", "ホームページ"]:
            guesses = guess_mapping(["企業名", header_name])
            self.assertEqual(guesses["hp_url"], header_name)

    def test_no_guess_for_unrelated_column(self):
        guesses = guess_mapping(["企業名", "HP", "備考欄その他"])
        self.assertIsNone(guesses.get("assigned_rep"))


class CsvParsingTests(TestCase):
    def test_parse_csv_text_skips_blank_rows(self):
        text = "企業名,HP\n株式会社ABC,https://abc.example.com\n\n株式会社DEF,https://def.example.com\n"
        header, rows = parse_csv_text(text)
        self.assertEqual(header, ["企業名", "HP"])
        self.assertEqual(len(rows), 2)

    def test_decode_csv_bytes_handles_utf8_and_shift_jis(self):
        utf8_bytes = "企業名,HP\n".encode("utf-8")
        self.assertIn("企業名", decode_csv_bytes(utf8_bytes))
        sjis_bytes = "企業名,HP\n".encode("cp932")
        self.assertIn("企業名", decode_csv_bytes(sjis_bytes))


class CsvImportFlowTests(TestCase):
    """アップロード→マッピング確認→登録の一連のHTTPフローを検証する。"""

    def setUp(self):
        self.org = Organization.objects.create(company_name="テスト株式会社")
        seed_defaults_for_organization(self.org)
        self.user = User.objects.create_user(email="owner@example.com", password="testpass123", name="担当太郎", organization=self.org)
        self.client.force_login(self.user)

    def _csv_file(self, content):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile("companies.csv", content.encode("utf-8"), content_type="text/csv")

    def test_upload_then_confirm_creates_companies(self):
        content = "企業名,HP,区分\n株式会社ABC,https://abc.example.com/,失注\n株式会社DEF,https://def.example.com/,営業候補\n"
        resp = self.client.post(reverse("companies:csv_upload"), {"csv_file": self._csv_file(content)})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "列マッピングの確認")

        import base64

        csv_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        resp2 = self.client.post(reverse("companies:csv_upload"), {
            "confirm_mapping": "1",
            "csv_b64": csv_b64,
            "original_filename": "companies.csv",
            "duplicate_policy": "skip",
            "map_company_name": "企業名",
            "map_hp_url": "HP",
            "map_category": "区分",
        }, follow=True)
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(Company.objects.filter(organization=self.org).count(), 2)
        abc = Company.objects.get(company_name="株式会社ABC")
        self.assertEqual(abc.category, Company.CATEGORY_LOST)
        self.assertEqual(abc.domain, "abc.example.com")

    def test_duplicate_domain_is_skipped_by_default(self):
        Company.objects.create(
            organization=self.org, company_name="既存ABC", hp_url="https://abc.example.com/",
            domain="abc.example.com",
        )
        content = "企業名,HP\n株式会社ABC,https://www.abc.example.com/company/\n"
        import base64

        csv_b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        self.client.post(reverse("companies:csv_upload"), {
            "confirm_mapping": "1", "csv_b64": csv_b64, "original_filename": "companies.csv",
            "duplicate_policy": "skip", "map_company_name": "企業名", "map_hp_url": "HP",
        })
        self.assertEqual(Company.objects.filter(organization=self.org).count(), 1)
        self.assertEqual(Company.objects.get().company_name, "既存ABC")


class CompanyLimitTests(TestCase):
    def test_free_plan_company_limit_enforced_on_manual_create(self):
        from django.test import override_settings

        org = Organization.objects.create(company_name="テスト株式会社")
        user = User.objects.create_user(email="owner2@example.com", password="testpass123", name="担当花子", organization=org)
        self.client.force_login(user)
        with override_settings(FREE_PLAN_COMPANY_LIMIT=1):
            Company.objects.create(organization=org, company_name="1社目", hp_url="https://a.example.com/", domain="a.example.com")
            resp = self.client.post(reverse("companies:create"), {
                "company_name": "2社目", "hp_url": "https://b.example.com/", "category": "other",
                "monitoring_enabled": "on", "scan_interval_days": 7,
            }, follow=True)
            self.assertEqual(Company.objects.filter(organization=org).count(), 1)
            self.assertContains(resp, "上限")
