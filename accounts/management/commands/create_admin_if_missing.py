"""
Render無料プランにはShell/One-Off Jobsがなく、`manage.py createsuperuser`を
対話的に実行できない。そのため、環境変数からDjango Admin用の管理者アカウントを
冪等に作成/権限付与するコマンドを用意する。

環境変数 ADMIN_EMAIL / ADMIN_PASSWORD が未設定の場合は何もせず正常終了する
（ビルドコマンドに常時組み込んでもデプロイを失敗させない）。

使い方（ビルドコマンドに追加する場合の例）:
    python manage.py migrate && python manage.py create_admin_if_missing
"""

import os

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import NotificationSettings, Organization, User
from intel.bootstrap import seed_defaults_for_organization


class Command(BaseCommand):
    help = "環境変数(ADMIN_EMAIL / ADMIN_PASSWORD)からDjango Admin用の管理者アカウントを作成する。"

    def handle(self, *args, **options):
        email = os.environ.get("ADMIN_EMAIL", "").strip()
        password = os.environ.get("ADMIN_PASSWORD", "")
        name = os.environ.get("ADMIN_NAME", "管理者").strip() or "管理者"
        company_name = os.environ.get("ADMIN_COMPANY_NAME", "ブレイブワーク").strip() or "ブレイブワーク"

        if not email or not password:
            self.stdout.write(
                "ADMIN_EMAIL / ADMIN_PASSWORD が未設定のため、管理者アカウント作成をスキップしました。"
            )
            return

        existing = User.objects.filter(email__iexact=email).first()
        if existing:
            changed = False
            if not existing.is_staff:
                existing.is_staff = True
                changed = True
            if not existing.is_superuser:
                existing.is_superuser = True
                changed = True
            if changed:
                existing.save(update_fields=["is_staff", "is_superuser"])
                self.stdout.write(self.style.SUCCESS(f"既存ユーザー {email} に管理者権限を付与しました。"))
            else:
                self.stdout.write(f"ユーザー {email} は既に管理者権限を持っています。変更なし。")
            return

        with transaction.atomic():
            organization = Organization.objects.create(company_name=company_name)
            user = User.objects.create_superuser(
                email=email, password=password, name=name, organization=organization,
            )
            NotificationSettings.objects.create(organization=organization, notify_email=email)
            seed_defaults_for_organization(organization)

        self.stdout.write(self.style.SUCCESS(f"管理者アカウント {user.email} を新規作成しました。"))
