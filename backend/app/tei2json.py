# backend/app/tei2json.py
# Orchestrator：各ユーティリティを呼び出して最終的な JSON ペイロードを組み立てます。

import os
from .tei_utils import extract_jats_sections, extract_meta, extract_xml_figures
from .pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf

def convert_xml_to_json(xml_content: str, pdf_path: str = None) -> dict:
    """
    TEI/JATS XML コンテンツと（オプションで）PDF パスを受け取り、
    メタデータ・セクション・図（XML内＋PDF抽出）・表をまとめて JSON に変換する。
    """
    # 1. XML のパース
    from lxml import etree
    parser = etree.XMLParser(remove_comments=True, recover=True, ns_clean=True)
    root = etree.fromstring(xml_content.encode("utf-8"), parser)

    # 2. メタデータ抽出
    meta = extract_meta(root)

    # 3. セクション＋XML内キャプション抽出
    sections = extract_jats_sections(root)
    xml_figs = extract_xml_figures(root)

    # 4. PDF からの図表抽出
    pdf_figs, tables = [], []
    if pdf_path:
        pdf_figs = extract_figures_from_pdf(pdf_path)
        tables   = extract_tables_from_pdf(pdf_path)

    # 5. 結果をまとめる
    return {
        "meta":         meta,
        "sections":     sections,
        "xml_figures":  xml_figs,
        "figures":      pdf_figs,
        "tables":       tables,
    }