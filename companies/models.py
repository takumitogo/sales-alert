import uuid

from django.conf import settings
from django.db import models


class Company(models.Model):
    """
    監視対象企業。技術設計書 2.3節 companies に対応。
    domain で重複判定。scan_interval_days で将来の企業別監視頻度変更に対応。
    """

    CATEGORY_LOST = "lost"
    CATEGORY_PAST_DEAL = "past_deal"
    CATEGORY_INACTIVE = "inactive"
    CATEGORY_PROSPECT = "prospect"
    CATEGORY_OTHER = "other"
    CATEGORY_CHOICES = [
        (CATEGORY_LOST, "失注"),
        (CATEGORY_PAST_DEAL, "過去取引"),
        (CATEGORY_INACTIVE, "長期未接触"),
        (CATEGORY_PROSPECT, "営業候補"),
        (CATEGORY_OTHER, "その他"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="companies"
    )
    company_name = models.CharField("企業名", max_length=255)
    hp_url = models.URLField("企業HP URL", max_length=500)
    domain = models.CharField("正規化ドメイン", max_length=255, db_index=True)
    category = models.CharField("区分", max_length=20, choices=CATEGORY_CHOICES, default=CATEGORY_OTHER)
    past_proposed_product = models.TextField("過去提案商材", blank=True)
    lost_reason = models.TextField("失注理由", blank=True)
    last_contact_date = models.DateField("最終接触日", null=True, blank=True)
    assigned_rep = models.CharField("担当者", max_length=100, blank=True)
    memo = models.TextField("メモ", blank=True)
    monitoring_enabled = models.BooleanField("監視ON/OFF", default=True)
    scan_interval_days = models.PositiveSmallIntegerField("監視間隔日数", default=7)
    last_scanned_at = models.DateTimeField("直近スキャン日時", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "監視対象企業"
        verbose_name_plural = "監視対象企業"
        constraints = [
            models.UniqueConstraint(fields=["organization", "domain"], name="uniq_org_domain"),
        ]
        indexes = [models.Index(fields=["organization", "monitoring_enabled"])]

    def __str__(self):
        return self.company_name

    def is_due_for_scan(self, now):
        if not self.monitoring_enabled:
            return False
        if self.last_scanned_at is None:
            return True
        from datetime import timedelta

        return now - self.last_scanned_at >= timedelta(days=self.scan_interval_days)


class CsvImportBatch(models.Model):
    """CSV一括登録バッチ履歴。技術設計書 2.3節 csv_import_batches に対応。"""

    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_PROCESSING, "処理中"),
        (STATUS_COMPLETED, "完了"),
        (STATUS_FAILED, "失敗"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="csv_import_batches"
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="csv_import_batches"
    )
    original_filename = models.CharField(max_length=255)
    column_mapping = models.JSONField(default=dict, blank=True)
    total_rows = models.PositiveIntegerField(default=0)
    success_rows = models.PositiveIntegerField(default=0)
    duplicate_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "CSV登録履歴"
        verbose_name_plural = "CSV登録履歴"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.original_filename} ({self.created_at:%Y-%m-%d})"


class CsvImportRow(models.Model):
    """CSV行単位の処理結果。技術設計書 2.3節 csv_import_rows に対応（デバッグ・エラー追跡用）。"""

    RESULT_SUCCESS = "success"
    RESULT_DUPLICATE_SKIPPED = "duplicate_skipped"
    RESULT_DUPLICATE_UPDATED = "duplicate_updated"
    RESULT_ERROR = "error"
    RESULT_CHOICES = [
        (RESULT_SUCCESS, "登録成功"),
        (RESULT_DUPLICATE_SKIPPED, "重複のためスキップ"),
        (RESULT_DUPLICATE_UPDATED, "重複のため更新"),
        (RESULT_ERROR, "エラー"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(CsvImportBatch, on_delete=models.CASCADE, related_name="rows")
    row_number = models.PositiveIntegerField()
    raw_data = models.JSONField(default=dict)
    result_status = models.CharField(max_length=20, choices=RESULT_CHOICES)
    error_message = models.TextField(blank=True)

    class Meta:
        verbose_name = "CSV取込行"
        verbose_name_plural = "CSV取込行"
        ordering = ["row_number"]
