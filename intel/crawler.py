"""
直接クロール（一次情報取得）実装。技術設計書 3.1節Step1 / 3.3節（クロール礼儀）/
3.4節（エラー処理）に対応。

- robots.txt を都度キャッシュしながら尊重する。
- 同一ドメインへの最小アクセス間隔を空ける。
- タイムアウト・リトライ（指数バックオフ）・サーキットブレーカー（連続失敗ドメインの除外）を実装する。
- すべての試行を CrawlLog に記録する。
"""

import hashlib
import re
import time
import urllib.robotparser
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from django.conf import settings

from .models import CrawlLog

# ニュース・IR・採用等を示すリンクを見つけるためのキーワード（リンクテキスト・href両方に対して判定）
INTERESTING_LINK_PATTERNS = [
    "news", "お知らせ", "ニュース", "press", "プレスリリース", "release",
    "ir", "投資家", "採用", "recruit", "careers", "キャリア", "人事",
    "topics", "トピックス", "information", "お知らせ一覧",
]

SOURCE_TYPE_PATH_RULES = [
    (("ir", "investor"), "ir"),
    (("recruit", "career", "saiyo", "採用"), "official_recruit"),
    (("news", "press", "release", "topics", "info"), "official_press"),
]


class RobotsCache:
    """robots.txt をドメインごとにキャッシュし、Disallow判定・Crawl-delay取得を行う。"""

    def __init__(self):
        self._cache = {}

    def _get_parser(self, base_url):
        origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
        if origin not in self._cache:
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(urljoin(origin, "/robots.txt"))
            try:
                parser.read()
            except Exception:
                parser = None  # robots.txt取得失敗時はアクセス許可扱い（過度な制限を避ける）
            self._cache[origin] = parser
        return self._cache[origin]

    def can_fetch(self, url, user_agent):
        parser = self._get_parser(url)
        if parser is None:
            return True
        try:
            return parser.can_fetch(user_agent, url)
        except Exception:
            return True

    def crawl_delay(self, url, user_agent):
        parser = self._get_parser(url)
        if parser is None:
            return None
        try:
            return parser.crawl_delay(user_agent)
        except Exception:
            return None


class DomainRateLimiter:
    """同一ドメインへの最小アクセス間隔を保証する簡易レートリミッター。"""

    def __init__(self, min_interval_seconds):
        self.min_interval = min_interval_seconds
        self._last_access = {}

    def wait(self, domain):
        last = self._last_access.get(domain)
        if last is not None:
            elapsed = time.monotonic() - last
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
        self._last_access[domain] = time.monotonic()


class CircuitBreaker:
    """特定ドメインへのアクセスが連続して失敗した場合、一時的にクロール対象から除外する。"""

    def __init__(self, failure_threshold):
        self.failure_threshold = failure_threshold
        self._failures = {}
        self._open = set()

    def is_open(self, domain):
        return domain in self._open

    def record_success(self, domain):
        self._failures[domain] = 0

    def record_failure(self, domain):
        self._failures[domain] = self._failures.get(domain, 0) + 1
        if self._failures[domain] >= self.failure_threshold:
            self._open.add(domain)


robots_cache = RobotsCache()
rate_limiter = DomainRateLimiter(settings.CRAWLER_MIN_DOMAIN_INTERVAL_SECONDS)
circuit_breaker = CircuitBreaker(settings.CRAWLER_CIRCUIT_BREAKER_FAILURES)


def _log(company, source_type, url, status, http_status=None, error="", duration_ms=None):
    CrawlLog.objects.create(
        company=company, source_type=source_type or "", target_url=url or "",
        status=status, http_status_code=http_status, error_message=error, duration_ms=duration_ms,
    )


def fetch_url(url, company=None, source_type=None):
    """
    1URLを取得する。robots.txt・レート制御・サーキットブレーカー・リトライを一括で扱う。
    戻り値: (成功フラグ, レスポンステキストまたはNone)
    """
    domain = urlparse(url).netloc

    if circuit_breaker.is_open(domain):
        _log(company, source_type, url, CrawlLog.STATUS_SKIPPED_CIRCUIT_OPEN)
        return False, None

    user_agent = settings.CRAWLER_USER_AGENT
    if not robots_cache.can_fetch(url, user_agent):
        _log(company, source_type, url, CrawlLog.STATUS_SKIPPED_ROBOTS)
        return False, None

    delay = robots_cache.crawl_delay(url, user_agent)
    if delay:
        rate_limiter.min_interval = max(rate_limiter.min_interval, delay)
    rate_limiter.wait(domain)

    attempt = 0
    while attempt <= settings.CRAWLER_MAX_RETRIES:
        start = time.monotonic()
        try:
            resp = httpx.get(
                url,
                headers={"User-Agent": user_agent},
                timeout=settings.CRAWLER_REQUEST_TIMEOUT_SECONDS,
                follow_redirects=True,
            )
            duration_ms = int((time.monotonic() - start) * 1000)
            if resp.status_code >= 400:
                _log(company, source_type, url, CrawlLog.STATUS_ERROR, resp.status_code, "", duration_ms)
                circuit_breaker.record_failure(domain)
                return False, None
            _log(company, source_type, url, CrawlLog.STATUS_SUCCESS, resp.status_code, "", duration_ms)
            circuit_breaker.record_success(domain)
            return True, resp.text
        except httpx.TimeoutException:
            duration_ms = int((time.monotonic() - start) * 1000)
            attempt += 1
            if attempt > settings.CRAWLER_MAX_RETRIES:
                _log(company, source_type, url, CrawlLog.STATUS_TIMEOUT, None, "timeout", duration_ms)
                circuit_breaker.record_failure(domain)
                return False, None
            time.sleep(2 ** attempt)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            _log(company, source_type, url, CrawlLog.STATUS_ERROR, None, str(exc), duration_ms)
            circuit_breaker.record_failure(domain)
            return False, None
    return False, None


PRESS_RELEASE_AGGREGATOR_DOMAINS = ("prtimes.jp", "atpress.ne.jp", "kyodonewsprwire.jp")


def classify_external_source_type(article_domain, company_domain):
    """
    RSS等で見つかった記事の情報ソース種別を推定する（技術設計書3.1節Step2）。
    自社ドメインと一致すればプレスリリース相当、主要プレスリリース配信サイトであれば
    同様に扱い、それ以外は「その他Web記事」として控えめに分類する
    （個別メディアの格付けは今回のMVPでは行わず、将来の拡張ポイントとする）。
    """
    if not article_domain:
        return "other_web"
    if company_domain and article_domain.endswith(company_domain):
        return "official_press"
    if any(article_domain.endswith(d) for d in PRESS_RELEASE_AGGREGATOR_DOMAINS):
        return "official_press"
    return "other_web"


def classify_source_type_from_path(url):
    path = urlparse(url).path.lower()
    for keywords, source_type in SOURCE_TYPE_PATH_RULES:
        if any(k in path for k in keywords):
            return source_type
    return "official_hp"


def extract_published_at(soup):
    time_tag = soup.find("time")
    if time_tag and time_tag.get("datetime"):
        parsed = _try_parse_datetime(time_tag["datetime"])
        if parsed:
            return parsed
    meta = soup.find("meta", attrs={"property": "article:published_time"})
    if meta and meta.get("content"):
        parsed = _try_parse_datetime(meta["content"])
        if parsed:
            return parsed
    return None


def extract_published_at_from_struct(struct_time):
    """feedparser の published_parsed（time.struct_time）をdatetimeに変換する。"""
    if not struct_time:
        return None
    try:
        return datetime(*struct_time[:6], tzinfo=timezone.utc)
    except Exception:
        return None


def _try_parse_datetime(value):
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value[:19] if "T" in value else value[:10], fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def normalize_text_for_hash(text):
    collapsed = re.sub(r"\s+", " ", text or "").strip()
    return collapsed


def content_hash(text):
    return hashlib.sha256(normalize_text_for_hash(text).encode("utf-8")).hexdigest()


def find_interesting_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    base_domain = urlparse(base_url).netloc
    found = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(strip=True) or ""
        combined = f"{href} {text}".lower()
        if any(pat in combined for pat in INTERESTING_LINK_PATTERNS):
            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc == base_domain:
                found[full_url] = text
    return found


def extract_page(url, html):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else url
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)[:8000]
    published_at = extract_published_at(soup)
    return {
        "title": title,
        "text": text,
        "published_at": published_at,
        "source_type": classify_source_type_from_path(url),
    }


def crawl_company_site(company, max_subpages=5):
    """
    企業公式サイトの直接クロール（技術設計書3.1節 Step1）。
    トップページを取得し、ニュース/IR/採用等らしきリンクを最大 max_subpages 件フォローする。
    戻り値: [{"url", "title", "text", "published_at", "source_type"}, ...]
    """
    documents = []
    ok, html = fetch_url(company.hp_url, company=company, source_type="official_hp")
    if not ok or not html:
        return documents

    top_page = extract_page(company.hp_url, html)
    documents.append({"url": company.hp_url, **top_page})

    links = find_interesting_links(company.hp_url, html)
    for sub_url in list(links.keys())[:max_subpages]:
        ok, sub_html = fetch_url(sub_url, company=company, source_type="official_press")
        if ok and sub_html:
            documents.append({"url": sub_url, **extract_page(sub_url, sub_html)})

    return documents
