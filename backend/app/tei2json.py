# backend/app/tei2json.py
# Orchestrator：各ユーティリティを呼び出して最終的な JSON ペイロードを組み立てます。

import os
from .tei_utils import extract_jats_sections, extract_meta, extract_jats_references, extract_figures_by_section
from .pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf

def convert_xml_to_json(xml_content: str, pdf_path: str = None) -> dict:
    from lxml import etree
    parser = etree.XMLParser(remove_comments=True, recover=True, ns_clean=True)
    try:
        root = etree.fromstring(xml_content.encode('utf-8'), parser)
    except Exception as e:
        raise ValueError(f"TEI XML parse error: {e}")
    if root is None:
        raise ValueError("TEI XML parse error: root is None")

    meta       = extract_meta(root)
    sections   = extract_jats_sections(root)
    # TEI XML 内の <fig> をセクション見出しごとにマッピング
    fig_map = extract_figures_by_section(root)
    # 各セクションの辞書に fig_map から対応する図表情報を追加
    for sec in sections:
        title = sec.get("head") or "__no_title__"
        sec["figures"] = fig_map.get(title, [])

    references = extract_jats_references(root)

    pdf_figs, tables = [], []
    if pdf_path:
        pdf_figs = extract_figures_from_pdf(pdf_path)
        tables   = extract_tables_from_pdf(pdf_path)

    return {
        'meta':       meta,
        'sections':   sections,
        'references': references,
        'figures':    pdf_figs,
        'tables':     tables,
    }
