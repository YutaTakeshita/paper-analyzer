# backend/app/tei_utils.py
import re
from typing import List, Dict
from lxml import etree
from app.meta_utils import extract_meta as extract_meta_from_meta_utils
from collections import defaultdict

_NS_RE = re.compile(r'\s+xmlns(:\w+)?="[^"]+"')

# XML Namespaceを削除する正規表現
def _strip_namespaces(xml: str) -> str:
    return _NS_RE.sub('', xml)

def extract_meta(root: etree._Element) -> Dict:
    """
    Delegate meta extraction to meta_utils.extract_meta.
    """
    return extract_meta_from_meta_utils(root)

def extract_jats_sections(root: etree._Element) -> List[Dict]:
    """
    <sec> 要素から見出しと本文を抽出して返却。
    """
    sections = []
    body = root.find('.//body')
    if body is not None:
        for sec in body.findall('sec'):
            head = sec.findtext('title') or ''
            text = ' '.join(sec.itertext())
            sections.append({'head': head.strip(), 'text': text.strip()})
    return sections

def extract_jats_references(root: etree._Element) -> List[Dict]:
    """
    <ref> 要素から参考文献を抽出して返却。
    """
    refs = []
    for ref in root.findall('.//ref'):
        ref_id   = ref.get('id')
        ref_text = ' '.join(ref.itertext()).strip()
        refs.append({'id': ref_id, 'text': ref_text})
    return refs


# New function: extract_figures_by_section
def extract_figures_by_section(root: etree._Element) -> Dict[str, List[Dict]]:
    """
    <sec> 配下の <fig> 要素をセクション見出しごとにマッピングして返す。
    { section_title: [ { "id": str, "caption": str }, ... ], ... }
    """
    mapping = defaultdict(list)
    body = root.find('.//body')
    if body is not None:
        for sec in body.findall('sec'):
            title = sec.findtext('title') or "__no_title__"
            for fig in sec.findall('.//fig'):
                fig_id = fig.get('id')
                cap_el = fig.find('caption')
                caption = " ".join(cap_el.itertext()).strip() if cap_el is not None else ""
                mapping[title].append({"id": fig_id, "caption": caption})
    return dict(mapping)
