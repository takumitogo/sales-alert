"""
HP URLからの正規化ドメイン抽出。技術設計書 3.4節「重複判定」に対応。

企業の重複判定は「HPドメインが一致する場合は同一企業として判定する」
（元設計書8章）というルールに基づき、www有無・パス・クエリを除去した
ドメインのみを比較キーとする。
"""

from urllib.parse import urlparse


def normalize_domain(url):
    """
    例:
      https://example.co.jp/            -> example.co.jp
      https://www.example.co.jp/company/ -> example.co.jp
    """
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path.split("/")[0]).lower()
    host = host.split(":")[0]  # ポート番号を除去
    if host.startswith("www."):
        host = host[4:]
    return host
