# backend/app/meta_utils.py
# メタデータ専用ロジック

from lxml import etree
from typing import List, Dict

def normalize_authors(raw_authors: List[str]) -> List[str]:
    """
    著者名リストを整形して返す（例：姓・名の並び替えなど）。
    """
    # 実装例
    return [name.strip() for name in raw_authors]

def extract_meta(root: etree._Element) -> Dict:
    """
    tei_utils.extract_meta と重複しないように、
    本当にメタデータ専用に切り出したい場合に利用。
    """
    # タイトル、ジャーナル、著者などを抽出
    return {
        "title": None,
        "authors": [],
        # …
    }