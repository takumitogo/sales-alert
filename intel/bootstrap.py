"""
新規組織作成時のデフォルトデータ投入。

技術設計書 2.1節の方針どおり、キーワード点数・情報源加点・検索クエリテンプレートは
組織ごとに編集可能なテーブルとして持たせ、組織作成時に元設計書13/14/11章のデフォルト
値をコピーする。
"""

from .models import (
    DEFAULT_KEYWORD_SCORES,
    DEFAULT_QUERY_SUFFIXES,
    DEFAULT_SOURCE_SCORES,
    SearchKeyword,
    SearchQueryTemplate,
    SourceTypeScore,
)


def seed_defaults_for_organization(organization):
    SearchKeyword.objects.bulk_create(
        [
            SearchKeyword(organization=organization, keyword=kw, score=score)
            for kw, score in DEFAULT_KEYWORD_SCORES
        ]
    )
    SourceTypeScore.objects.bulk_create(
        [
            SourceTypeScore(organization=organization, source_type=st, score_bonus=score)
            for st, score in DEFAULT_SOURCE_SCORES
        ]
    )
    SearchQueryTemplate.objects.bulk_create(
        [
            SearchQueryTemplate(organization=organization, query_suffix=suffix)
            for suffix in DEFAULT_QUERY_SUFFIXES
        ]
    )
