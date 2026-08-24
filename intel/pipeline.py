"""
1社分の「取得→スコアリング→保存→通知」パイプライン。技術設計書 4章の定期実行方式から
呼び出される中核ロジック。

- Step1: 直接クロール（crawler.crawl_company_site）
- Step2: RSS検索（search_providers）
- 重複判定（company, url のUNIQUE制約 + 事前チェック）
- ルールベーススコアリング（scoring.score_document）
- 閾値判定（Alert作成）とメール送信（emailing.send_alert_email）
"""

import logging
from urllib.parse import urlparse

from django.utils import timezone

from .crawler import classify_external_source_type, content_hash, crawl_company_site
from .emailing import send_alert_email
from .models import Alert, SearchKeyword, SearchQueryTemplate, SourceTypeScore, WebDocument
from .scoring import classify_alert_level, score_document
from .search_providers import get_enabled_providers

logger = logging.getLogger(__name__)


def _collect_raw_documents(company):
    documents = []

    try:
        documents.extend(crawl_company_site(company))
    except Exception:
        logger.exception("direct crawl failed for company_id=%s", company.id)

    query_templates = SearchQueryTemplate.objects.filter(organization=company.organization, enabled=True)
    providers = get_enabled_providers()
    for qt in query_templates:
        query = f"{company.company_name} {qt.query_suffix}".strip()
        for provider in providers:
            try:
                for result in provider.search(company, query):
                    if not result.get("url"):
                        continue
                    documents.append({
                        "url": result["url"],
                        "title": result.get("title", ""),
                        "text": result.get("title", ""),  # RSSはタイトルのみ取得（本文は取得しない）
                        "published_at": result.get("published_at"),
                        "source_type": classify_external_source_type(result.get("source_domain"), company.domain),
                    })
            except Exception:
                logger.exception(
                    "search provider %s failed for company_id=%s query=%r", provider.name, company.id, query
                )
    return documents


def scan_company(company):
    """
    1社を巡回してWebDocument/Alertを作成し、必要ならメール送信する。
    戻り値：作成された Alert のリスト。
    """
    org = company.organization
    keyword_qs = list(SearchKeyword.objects.filter(organization=org, enabled=True))
    source_score_map = {
        s.source_type: s.score_bonus for s in SourceTypeScore.objects.filter(organization=org)
    }
    notif = getattr(org, "notification_settings", None)
    alert_threshold = notif.alert_threshold_score if notif else 80
    watch_threshold = notif.watch_threshold_score if notif else 60

    created_alerts = []
    raw_documents = _collect_raw_documents(company)

    # URL正規化(簡易)：末尾スラッシュ差異を吸収
    seen_in_batch = set()
    for doc in raw_documents:
        url = (doc.get("url") or "").strip().rstrip("/")
        if not url or url in seen_in_batch:
            continue
        seen_in_batch.add(url)

        if WebDocument.objects.filter(company=company, url=url).exists():
            continue  # 過去取得済みURL -> 再登録・再通知しない

        text_for_scoring = f"{doc.get('title', '')} {doc.get('text', '')}"
        result = score_document(
            text=text_for_scoring,
            source_type=doc.get("source_type", "other_web"),
            keyword_qs=keyword_qs,
            source_score_map=source_score_map,
            published_at=doc.get("published_at"),
        )

        try:
            web_doc = WebDocument.objects.create(
                company=company,
                source_type=doc.get("source_type", "other_web"),
                title=(doc.get("title") or url)[:500],
                url=url,
                domain=urlparse(url).netloc,
                published_at=doc.get("published_at"),
                content_hash=content_hash(doc.get("text", "")),
                raw_text=(doc.get("text") or "")[:8000],
                matched_keywords=result.matched_keywords,
                keyword_score=result.keyword_score,
                source_score=result.source_score,
                freshness_score=result.freshness_score,
                total_score=result.total_score,
            )
        except Exception:
            # UNIQUE制約違反（並行実行等）や予期しないデータ不整合で1件失敗しても
            # バッチ全体を止めない。
            logger.exception("failed to save web_document url=%s company_id=%s", url, company.id)
            continue

        level = classify_alert_level(result.total_score, alert_threshold, watch_threshold)
        if level in (Alert.LEVEL_ALERT, Alert.LEVEL_WATCH):
            alert = Alert.objects.create(
                web_document=web_doc, organization=org, company=company,
                score=result.total_score, alert_level=level,
            )
            created_alerts.append(alert)
            if level == Alert.LEVEL_ALERT:
                try:
                    send_alert_email(alert)
                except Exception:
                    logger.exception("failed to send alert email for alert_id=%s", alert.id)

    company.last_scanned_at = timezone.now()
    company.save(update_fields=["last_scanned_at"])
    return created_alerts
