from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """テンプレート内で辞書を変数キーで参照するためのフィルタ（CSV列マッピング画面で使用）。"""
    if not dictionary:
        return None
    return dictionary.get(key)
