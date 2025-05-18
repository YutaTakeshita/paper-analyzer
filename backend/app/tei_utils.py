# backend/app/tei_utils.py
# TEI/JATS XML 解析ロジック：

import re
from typing import List, Dict
from lxml import etree

_NS_RE = re.compile(r'\s+xmlns(:\w+)?="[^"]+"')

def _strip_namespaces(xml: str) -> str:
    return _NS_RE.sub('', xml)

def extract_meta(root: etree._Element) -> Dict:
    """
    <article-meta> 以下からタイトル・著者・発行年・巻・頁を抽出して返す。
    """
    # 実装：title-group/article-title, contrib-group などを走査
    meta_root = root.find('.//article-meta') or root
    # ...
    return {
        "title":   None,
        "journal": None,
        "issued":  None,
        "authors": [],
        "volume":  None,
        "fpage":   None,
        "lpage":   None,
    }

def extract_jats_sections(root: etree._Element) -> List[Dict]:
    """
    <sec> 要素から見出しと本文を抽出し、
    [{"head": str, "text": str}, ...] のリストで返す。
    """
    sections = []
    body = root.find('.//body')
    if body is not None:
        for sec in body.findall('sec'):
            head = sec.findtext('title') or ""
            text = " ".join(sec.itertext())
            sections.append({"head": head.strip(), "text": text.strip()})
    return sections

def extract_xml_figures(root: etree._Element) -> List[Dict]:
    """
    <fig> 要素から id とキャプションを抽出して返す。
    """
    figs = []
    for fig in root.findall('.//fig'):
        fig_id = fig.get('id')
        cap_el = fig.find('caption')
        cap = " ".join(cap_el.itertext()) if cap_el is not None else ""
        figs.append({"id": fig_id, "caption": cap.strip()})
    return figs


def extract_jats_references(root: etree._Element) -> List[Dict]:
    """
    <ref> 要素から参考文献の情報を抽出し、
    [{"id": str, "text": str}, ...] のリストで返す。
    """
    refs = []
    for ref in root.findall('.//ref'):
        ref_id = ref.get('id')
        ref_text = " ".join(ref.itertext()).strip()
        refs.append({"id": ref_id, "text": ref_text})
    return refs