from django.contrib import admin, messages

from intel.models import Alert
from intel.pipeline import scan_company

from .models import Company, CsvImportBatch, CsvImportRow


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("company_name", "domain", "category", "organization", "monitoring_enabled", "last_scanned_at")
    list_filter = ("category", "monitoring_enabled")
    search_fields = ("company_name", "domain")
    actions = ["run_scan_now"]

    @admin.action(description="選択した企業を今すぐスキャンする")
    def run_scan_now(self, request, queryset):
        """
        Render無料プランにはShell/One-Off Jobsがなく、週次バッチ(run_weekly_scan)を
        オンデマンドで実行できない。動作確認のため、管理画面から選択した企業だけ
        即座にスキャンできるようにするアクション。
        """
        scanned = 0
        alert_count = 0
        watch_count = 0
        errors = []

        for company in queryset:
            try:
                alerts = scan_company(company)
            except Exception as exc:  # noqa: BLE001 - 1社の失敗で他社の処理を止めない
                errors.append(f"{company.company_name}: {exc}")
                continue
            scanned += 1
            alert_count += sum(1 for a in alerts if a.alert_level == Alert.LEVEL_ALERT)
            watch_count += sum(1 for a in alerts if a.alert_level == Alert.LEVEL_WATCH)

        summary = f"{scanned}社のスキャンが完了しました（アラート{alert_count}件・要チェック{watch_count}件）。"
        if alert_count:
            summary += "アラート該当分は通知メールを送信しました。"

        if errors:
            self.message_user(
                request,
                summary + f" 失敗: {len(errors)}社（" + " / ".join(errors) + "）",
                level=messages.WARNING,
            )
        else:
            self.message_user(request, summary, level=messages.SUCCESS)


class CsvImportRowInline(admin.TabularInline):
    model = CsvImportRow
    extra = 0


@admin.register(CsvImportBatch)
class CsvImportBatchAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "organization", "status", "total_rows", "success_rows", "error_rows", "created_at")
    inlines = [CsvImportRowInline]
