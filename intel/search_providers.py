"""
検索プロバイダ抽象化。技術設計書 3.1節Step2・3.2節「特定サービスに依存しない設計」に対応。

SearchProvider インターフェースを実装したクラスを差し替え可能にすることで、
Google News RSS が使えなくなった場合や、将来 Brave Search API 等の有償プロバイダを
追加する場合にも、パイプライン側のコードを変更せずに済む構成にしている。
"""

import urllib.parse
from abc import ABC, abstractmethod

import feedparser

from .crawler import extract_published_at_from_struct, fetch_url


class SearchProvider(ABC):
    name = "base"

    @abstractmethod
    def search(self, company, query):
        """[{"url", "title", "published_at", "source_domain"}, ...] を返す。"""
        raise NotImplementedError


class GoogleNewsRSSProvider(SearchProvider):
    """
    Google News の公開RSSフィードを利用する（APIキー不要・無料）。
    技術設計書3.2節のとおり、Bing Search API・Google Custom Search JSON APIの
    無料枠が使えなくなったことを踏まえ、まずはこの無料公開RSSを既定プロバイダとする。
    """

    name = "google_news_rss"
    BASE_URL = "https://news.google.com/rss/search"

    def search(self, company, query):
        params = {"q": query, "hl": "ja", "gl": "JP", "ceid": "JP:ja"}
        url = f"{self.BASE_URL}?{urllib.parse.urlencode(params)}"
        ok, body = fetch_url(url, company=company, source_type="other_web")
        if not ok or not body:
            return []
        parsed = feedparser.parse(body)
        results = []
        for entry in parsed.entries[:10]:
            published_at = extract_published_at_from_struct(getattr(entry, "published_parsed", None))
            results.append({
                "url": entry.get("link"),
                "title": entry.get("title", ""),
                "published_at": published_at,
                "source_domain": urllib.parse.urlparse(entry.get("link", "")).netloc,
            })
        return results


def get_enabled_providers():
    """
    有効な検索プロバイダの一覧を返す。将来 settings や組織単位の設定で
    プロバイダを切り替えられるよう、この関数を差し替えポイントにしている。
    """
    return [GoogleNewsRSSProvider()]
