"""
定期実行バッチ本体。技術設計書4章「定期実行方式」に対応。

Render Cron Job から `python manage.py run_weekly_scan` として週次で呼び出す想定。
- 対象：monitoring_enabled=True かつ scan_interval_days 以上前回スキャンから経過した企業
- 冪等性：1社の処理が完了するたびに last_scanned_at を更新するため、
  途中で失敗しても未処理企業のみが次回実行時の対象になる。
- 1社の失敗が全体を止めないよう、企業単位で例外を捕捉する。
"""

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from companies.models import Company
from intel.pipeline import scan_company

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "監視企業を巡回し、Web公開情報の取得・スコアリング・通知を行う定期実行バッチ"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit", type=int, default=None,
            help="1回の実行で処理する企業数の上限（負荷分散・動作確認用）",
        )
        parser.add_argument(
            "--company-id", type=str, default=None,
            help="指定した企業IDのみを対象にする（動作確認用）",
        )

    def handle(self, *args, **options):
        now = timezone.now()

        if options["company_id"]:
            queryset = Company.objects.filter(id=options["company_id"])
        else:
            queryset = Company.objects.filter(monitoring_enabled=True).order_by(
                "last_scanned_at"
            )  # 未スキャン(None)・最も古いものから優先

        limit = options["limit"] or settings.CRAWLER_BATCH_SIZE
        processed = 0
        alert_count = 0
        error_count = 0

        for company in queryset.iterator():
            if not options["company_id"] and not company.is_due_for_scan(now):
                continue
            if processed >= limit:
                break
            processed += 1
            try:
                alerts = scan_company(company)
                alert_count += len(alerts)
                self.stdout.write(f"OK  {company.company_name}: 新規検知 {len(alerts)} 件")
            except Exception:
                error_count += 1
                logger.exception("scan_company failed for company_id=%s", company.id)
                self.stdout.write(self.style.ERROR(f"NG  {company.company_name}: 処理中にエラーが発生しました"))

        self.stdout.write(
            self.style.SUCCESS(
                f"完了: 処理企業数={processed} 新規アラート/要チェック={alert_count} エラー企業数={error_count}"
            )
        )
