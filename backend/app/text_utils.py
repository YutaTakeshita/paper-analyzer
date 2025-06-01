import re
import os

def sanitize_filename(title_str, fallback_name="untitled_document", max_length=200, extension=".pdf"):
    if not title_str or not str(title_str).strip():
        sanitized_base = fallback_name
    else:
        sanitized_base = str(title_str)
        sanitized_base = re.sub(r'[\n\t\r]+', ' ', sanitized_base)
        sanitized_base = re.sub(r'[\\/*?:"<>|]', '', sanitized_base) # 不正文字除去
        sanitized_base = sanitized_base.strip()
        sanitized_base = re.sub(r'\.+', '.', sanitized_base) # 連続するピリオドを1つに
        sanitized_base = sanitized_base.strip('.') # 先頭と末尾のピリオドを除去
        sanitized_base = re.sub(r'[\s_]+', '_', sanitized_base) # 空白やアンダースコアを単一アンダースコアに
        if not sanitized_base or all(c == '_' for c in sanitized_base):
            sanitized_base = fallback_name

    effective_max_length = max_length - len(extension)
    if effective_max_length <= 0:
        raise ValueError(f"max_length ({max_length}) is too short for the extension ('{extension}').")

    if len(sanitized_base) > effective_max_length:
        sanitized_base = sanitized_base[:effective_max_length]

    sanitized_base = sanitized_base.rstrip('_').rstrip('.') # 末尾のアンダースコアやピリオドを除去
    if not sanitized_base:
        sanitized_base = fallback_name
        if len(sanitized_base) > effective_max_length:
            sanitized_base = sanitized_base[:effective_max_length]

    return f"{sanitized_base}{extension}"

# このスクリプトを直接実行した際のテストコード
if __name__ == '__main__':
    print("sanitize_filename 関数のテスト:")
    test_titles = [
        "This is a: Test Title / with? invalid*chars.",
        "Another Title\nWith Newlines\tAnd Tabs",
        "  Leading and trailing spaces  ",
        "Short",
        "",
        None,
        "very_long_title_" + ("L" * 250), # 非常に長いタイトル
        "a/b\\c:d*e?f\"g<h>i|j",
        "   ", # 空白のみ
        "___", # アンダースコアのみ
        "タイトルに日本語が含まれる場合：大丈夫？",
        "Test with .period.in.name"
    ]

    for title in test_titles:
        original_title_repr = repr(title) # Noneや空文字列を分かりやすく表示
        sanitized = sanitize_filename(title_str=title)
        print(f"Original: {original_title_repr:<50} -> Sanitized: '{sanitized}' (Length: {len(sanitized)})")

    print("\nフォールバック名と最大長のテスト:")
    print(f"Sanitized (fallback): '{sanitize_filename(None, fallback_name='custom_fallback', max_length=20)}'")
    print(f"Sanitized (long fallback): '{sanitize_filename(None, fallback_name='a_very_very_long_fallback_name_that_exceeds_limits', max_length=30)}'")

    try:
        print("\n拡張子が長すぎる場合のテスト:")
        sanitize_filename("test", max_length=3, extension=".longext")
    except ValueError as e:
        print(f"  エラー発生 (意図通り): {e}")