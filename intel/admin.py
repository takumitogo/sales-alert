from django.contrib import admin

from .models import Alert, CrawlLog, Feedback, SearchKeyword, SearchQueryTemplate, SourceTypeScore, WebDocument


@admin.register(SearchKeyword)
class SearchKeywordAdmin(admin.ModelAdmin):
    list_display = ("keyword", "score", "enabled", "organization")
    list_filter = ("enabled",)


@admin.register(SearchQueryTemplate)
class SearchQueryTemplateAdmin(admin.ModelAdmin):
    list_display = ("query_suffix", "enabled", "organization")


@admin.register(SourceTypeScore)
class SourceTypeScoreAdmin(admin.ModelAdmin):
    list_display = ("source_type", "score_bonus", "organization")


@admin.register(WebDocument)
class WebDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "total_score", "source_type", "published_at", "notified")
    list_filter = ("source_type", "notified")
    search_fields = ("title", "url")


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display = ("company", "score", "alert_level", "email_sent", "created_at")
    list_filter = ("alert_level", "email_sent")


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("web_document", "user", "rating", "created_at")


@admin.register(CrawlLog)
class CrawlLogAdmin(admin.ModelAdmin):
    list_display = ("target_url", "company", "status", "http_status_code", "duration_ms", "created_at")
    list_filter = ("status",)
