"""
CSV一括登録の列マッピングロジック。技術設計書/元設計書 7章に対応。

列名が完全一致していなくても、候補語リストとの部分一致でシステム項目を推測し、
アップロード後のマッピング確認画面でユーザーに選ばせる。
"""

import csv
import io

FIELD_DEFS = [
    # (field_key, ラベル, 必須か, 候補語リスト)
    ("company_name", "企業名", True, ["会社名", "企業名", "法人名", "顧客名", "取引先名", "社名"]),
    ("hp_url", "企業HP URL", True, ["hp", "url", "webサイト", "ホームページ", "web", "サイト", "homepage"]),
    ("category", "区分", False, ["区分", "分類", "ステータス", "status"]),
    ("past_proposed_product", "過去提案商材", False, ["過去提案商材", "提案商材", "商材", "product"]),
    ("lost_reason", "失注理由", False, ["失注理由", "理由", "reason"]),
    ("last_contact_date", "最終接触日", False, ["最終接触日", "接触日", "最終連絡日", "contact"]),
    ("assigned_rep", "担当者", False, ["担当者", "担当", "営業担当", "rep"]),
    ("memo", "メモ", False, ["メモ", "備考", "note", "memo"]),
]

CATEGORY_LABEL_TO_KEY = {
    "失注": "lost",
    "過去取引": "past_deal",
    "長期未接触": "inactive",
    "営業候補": "prospect",
    "その他": "other",
}


def guess_mapping(header_row):
    """各システム項目に最も一致しそうなCSV列名を推測して {field_key: column_name} を返す。"""
    guesses = {}
    normalized_headers = {h: h.strip().lower() for h in header_row}
    for field_key, _label, _required, candidates in FIELD_DEFS:
        match = None
        for h, norm in normalized_headers.items():
            for cand in candidates:
                if cand.lower() in norm or norm in cand.lower():
                    match = h
                    break
            if match:
                break
        guesses[field_key] = match
    return guesses


def parse_csv_text(text):
    """CSVテキストをパースし (header_row, list_of_row_dicts) を返す。文字コードはUTF-8/CP932両対応。"""
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return [], []
    header = rows[0]
    data_rows = []
    for row in rows[1:]:
        if not any(cell.strip() for cell in row):
            continue
        # 列数が足りない行はNoneパディングする
        padded = row + [""] * (len(header) - len(row))
        data_rows.append(dict(zip(header, padded)))
    return header, data_rows


def decode_csv_bytes(raw_bytes):
    for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
        try:
            return raw_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw_bytes.decode("utf-8", errors="replace")
