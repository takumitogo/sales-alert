"""
営業機会スコア算出ロジック。元設計書13〜16章 / 技術設計書2.1節に対応。

- キーワード点数：組織ごとの SearchKeyword（enabled=True）を本文・タイトルに対して
  部分一致でチェックし、該当したものすべてを加点する。
- 情報ソース加点：SourceTypeScore（組織ごと）から source_type に応じた加点。
- 情報鮮度加点：settings.FRESHNESS_SCORE_RULES（経過日数に応じた加点。公開日不明なら0点）。
- 合計は 100点を上限とする（元設計書16章の計算例に準拠）。
"""

from dataclasses import dataclass, field
from datetime import datetime

from django.conf import settings


@dataclass
class ScoreResult:
    keyword_score: int
    matched_keywords: list = field(default_factory=list)  # [{"keyword": str, "score": int}, ...]
    source_score: int = 0
    freshness_score: int = 0

    @property
    def total_score(self):
        return min(self.keyword_score + self.source_score + self.freshness_score, 100)


def score_keywords(text, keyword_qs):
    """
    キーワードは単純な部分文字列一致で判定する（日本語形態素解析は行わない）。
    例：キーワード「部署新設」は「新規事業推進部を新設」のような言い換え表現には一致しない。
    MVPでは意図的にシンプルな実装とし、精度向上（形態素解析・同義語展開等）は
    将来の改善課題とする。
    """
    text_lower = (text or "").lower()
    matched = []
    total = 0
    for kw in keyword_qs:
        if kw.keyword.lower() in text_lower:
            matched.append({"keyword": kw.keyword, "score": kw.score})
            total += kw.score
    return total, matched


def score_source(source_type, source_score_map):
    return source_score_map.get(source_type, 0)


def score_freshness(published_at, now=None):
    """published_at が None（公開日不明）の場合は0点とする。"""
    if published_at is None:
        return 0
    now = now or datetime.now(published_at.tzinfo) if published_at.tzinfo else datetime.now()
    days = (now - published_at).days
    for rule in settings.FRESHNESS_SCORE_RULES:
        if days <= rule["max_days"]:
            return rule["score"]
    return 0


def score_document(text, source_type, keyword_qs, source_score_map, published_at, now=None):
    keyword_score, matched = score_keywords(text, keyword_qs)
    source_score = score_source(source_type, source_score_map)
    freshness_score = score_freshness(published_at, now=now)
    return ScoreResult(
        keyword_score=keyword_score,
        matched_keywords=matched,
        source_score=source_score,
        freshness_score=freshness_score,
    )


def classify_alert_level(total_score, alert_threshold, watch_threshold):
    if total_score >= alert_threshold:
        return "alert"
    if total_score >= watch_threshold:
        return "watch"
    return "history"
