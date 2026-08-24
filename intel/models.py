import uuid

from django.conf import settings
from django.db import models


SOURCE_TYPE_CHOICES = [
    ("official_hp", "企業公式HP"),
    ("ir", "IR"),
    ("official_recruit", "公式採用ページ"),
    ("official_press", "公式プレスリリース"),
    ("industry_media", "業界メディア"),
    ("other_web", "その他Web記事"),
]

DEFAULT_KEYWORD_SCORES = [
    ("営業強化", 35), ("新規顧客", 35), ("販路拡大", 30), ("新市場", 30), ("新規事業", 30),
    ("新サービス", 25), ("新組織", 25), ("部署新設", 25), ("DX推進", 25), ("資金調達", 25),
    ("M&A", 25), ("新社長", 20), ("新拠点", 20), ("AI活用", 20), ("組織改編", 20),
    ("新役員", 15), ("業務提携", 15), ("新工場", 15), ("採用強化", 15),
]

DEFAULT_SOURCE_SCORES = [
    ("official_hp", 20), ("ir", 20), ("official_recruit", 15),
    ("official_press", 15), ("industry_media", 10), ("other_web", 5),
]

DEFAULT_QUERY_SUFFIXES = [
    "", "新規事業", "新サービス", "組織改編", "人事", "DX", "AI", "業務提携",
    "M&A", "資金調達", "採用", "営業", "新拠点", "中期経営計画",
]


class SearchKeyword(models.Model):
    """営業機会判定キーワードと点数（組織ごとに編集可能）。技術設計書 2.3節 search_keywords。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="search_keywords"
    )
    keyword = models.CharField(max_length=50)
    score = models.PositiveSmallIntegerField()
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "監視キーワード"
        verbose_name_plural = "監視キーワード"
        constraints = [
            models.UniqueConstraint(fields=["organization", "keyword"], name="uniq_org_keyword"),
        ]
        ordering = ["-score"]

    def __str__(self):
        return f"{self.keyword} ({self.score}点)"


class SearchQueryTemplate(models.Model):
    """検索クエリテンプレート（組織ごとに追加・変更可能）。技術設計書 2.3節 search_query_templates。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="query_templates"
    )
    query_suffix = models.CharField(max_length=100, blank=True, help_text="空欄なら社名のみで検索")
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "検索クエリテンプレート"
        verbose_name_plural = "検索クエリテンプレート"

    def __str__(self):
        return self.query_suffix or "(社名のみ)"


class SourceTypeScore(models.Model):
    """情報ソース種別ごとの加点（組織ごとに編集可能）。技術設計書 2.3節 source_type_scores。"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "accounts.Organization", on_delete=models.CASCADE, related_name="source_type_scores"
    )
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES)
    score_bonus = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "情報ソース加点"
        verbose_name_plural = "情報ソース加点"
        constraints = [
            models.UniqueConstraint(fields=["organization", "source_type"], name="uniq_org_source_type"),
        ]

    def __str__(self):
        return f"{self.get_source_type_display()} (+{self.score_bonus})"


class WebDocument(models.Model):
    """
    取得したWeb公開情報（新着情報）。技術設計書 2.3節 web_documents。
    (company, url) の UNIQUE 制約で「過去取得済みURLの再通知防止」を保証する。
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="web_documents")
    source_type = models.CharField(max_length=30, choices=SOURCE_TYPE_CHOICES)
    title = models.CharField(max_length=500, blank=True)
    url = models.URLField(max_length=1000)
    domain = models.CharField(max_length=255, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    first_detected_at = models.DateTimeField(auto_now_add=True)
    content_hash = models.CharField(max_length=64, blank=True, db_index=True)
    raw_text = models.TextField(blank=True)
    matched_keywords = models.JSONField(default=list, blank=True)
    keyword_score = models.PositiveSmallIntegerField(default=0)
    source_score = models.PositiveSmallIntegerField(default=0)
    freshness_score = models.PositiveSmallIntegerField(default=0)
    total_score = models.PositiveSmallIntegerField(default=0)
    notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "検知情報"
        verbose_name_plural = "検知情報"
        constraints = [
            models.UniqueConstraint(fields=["company", "url"], name="uniq_company_url"),
        ]
        ordering = ["-first_detected_at"]

    def __str__(self):
        return f"{self.title[:40]} ({self.total_score}点)"


class Alert(models.Model):
    """アラート・通知履歴。技術設計書 2.3節 alerts。"""

    LEVEL_ALERT = "alert"
    LEVEL_WATCH = "watch"
    LEVEL_HISTORY = "history"
    LEVEL_CHOICES = [
        (LEVEL_ALERT, "営業機会アラート（80点以上）"),
        (LEVEL_WATCH, "要チェック（60〜79点）"),
        (LEVEL_HISTORY, "履歴（59点以下）"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    web_document = models.OneToOneField(WebDocument, on_delete=models.CASCADE, related_name="alert")
    organization = models.ForeignKey("accounts.Organization", on_delete=models.CASCADE, related_name="alerts")
    company = models.ForeignKey("companies.Company", on_delete=models.CASCADE, related_name="alerts")
    score = models.PositiveSmallIntegerField()
    alert_level = models.CharField(max_length=10, choices=LEVEL_CHOICES)
    email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "アラート"
        verbose_name_plural = "アラート"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.company_name}: {self.score}点"


class Feedback(models.Model):
    """ユーザー評価（👍／👎）。技術設計書 2.3節 feedback。将来のAI精度改善用データとして蓄積。"""

    RATING_USEFUL = "useful"
    RATING_NOT_USEFUL = "not_useful"
    RATING_CHOICES = [
        (RATING_USEFUL, "役に立った"),
        (RATING_NOT_USEFUL, "不要だった"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    web_document = models.ForeignKey(WebDocument, on_delete=models.CASCADE, related_name="feedback_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="feedback_entries")
    rating = models.CharField(max_length=15, choices=RATING_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "フィードバック"
        verbose_name_plural = "フィードバック"
        constraints = [
            models.UniqueConstraint(fields=["web_document", "user"], name="uniq_doc_user_feedback"),
        ]


class CrawlLog(models.Model):
    """クロール実行ログ（運用監視・エラー追跡用）。技術設計書 2.3節 crawl_logs。"""

    STATUS_SUCCESS = "success"
    STATUS_ERROR = "error"
    STATUS_TIMEOUT = "timeout"
    STATUS_SKIPPED_ROBOTS = "skipped_robots"
    STATUS_SKIPPED_RATE_LIMIT = "skipped_rate_limit"
    STATUS_SKIPPED_CIRCUIT_OPEN = "skipped_circuit_open"
    STATUS_CHOICES = [
        (STATUS_SUCCESS, "成功"),
        (STATUS_ERROR, "エラー"),
        (STATUS_TIMEOUT, "タイムアウト"),
        (STATUS_SKIPPED_ROBOTS, "robots.txtにより除外"),
        (STATUS_SKIPPED_RATE_LIMIT, "レート制御により待機"),
        (STATUS_SKIPPED_CIRCUIT_OPEN, "連続失敗によりスキップ"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    company = models.ForeignKey(
        "companies.Company", on_delete=models.SET_NULL, null=True, blank=True, related_name="crawl_logs"
    )
    source_type = models.CharField(max_length=30, blank=True)
    target_url = models.URLField(max_length=1000, blank=True)
    status = models.CharField(max_length=25, choices=STATUS_CHOICES)
    http_status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "クロールログ"
        verbose_name_plural = "クロールログ"
        ordering = ["-created_at"]
