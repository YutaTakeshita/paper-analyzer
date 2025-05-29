# backend/app/tei2json.py
import os
import logging
from lxml import etree

# tei_utils からGROBID対応の関数をインポート
from .tei_utils import (
    extract_sections_from_tei, 
    extract_references_from_tei
    # extract_figures_by_section は extract_sections_from_tei に統合されたため、ここでは不要
)
# meta_utils からGROBID対応の関数をインポート
from .meta_utils import extract_meta_from_tei # ★ インポート元を修正

from .pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf

logger = logging.getLogger(__name__) # loggerを定義 (既にあればOK)

def convert_xml_to_json(xml_content: str, pdf_path: str = None) -> dict:
    # ... (XMLパース処理 - 前回の提案通り) ...
    # XML宣言やBOMがあれば取り除く、パースエラー対策
    if isinstance(xml_content, str) and xml_content.startswith("<?xml"):
        xml_content = xml_content.split("?>", 1)[-1].lstrip()
    
    xml_content_bytes = xml_content.encode('utf-8') if isinstance(xml_content, str) else xml_content

    try:
        parser = etree.XMLParser(remove_comments=True, recover=True) # ns_clean=True は削除またはテスト
        root = etree.fromstring(xml_content_bytes, parser=parser)
    except Exception as e:
        logger.error(f"TEI XML parse error: {e}. XML (first 500 chars): {xml_content_bytes[:500].decode('utf-8', 'ignore')}")
        raise ValueError(f"TEI XML parse error: {e}")
    if root is None:
        logger.error("TEI XML parse resulted in a None root.")
        raise ValueError("TEI XML parse error: root is None")

    # 修正された関数を呼び出す
    meta = extract_meta_from_tei(root)       # meta_utils からインポートした関数
    sections = extract_sections_from_tei(root) # tei_utils からインポートした関数 (図キャプションも含む)
    references = extract_references_from_tei(root) # tei_utils からインポートした関数
    
    # extract_figures_by_section の呼び出しと後続のループは不要になる
    # fig_map = extract_figures_by_section(root) 
    # for sec in sections:
    #     title = sec.get("head") or "__no_title__"
    #     sec["figures"] = fig_map.get(title, [])

    pdf_figs, tables = [], []
    if pdf_path:
        logger.info(f"Extracting figures and tables from PDF: {pdf_path}")
        pdf_figs = extract_figures_from_pdf(pdf_path)
        tables = extract_tables_from_pdf(pdf_path)
        logger.info(f"Extracted {len(pdf_figs)} figures and {len(tables)} tables from PDF.")

    final_data = {
        'meta': meta,
        'sections': sections,    # 各セクションオブジェクトが 'figures' キーでTEI内の図キャプションを持つ想定
        'references': references,
        'figures': pdf_figs,    # PDFから直接抽出した図の画像データ
        'tables': tables,      # PDFから直接抽出した表データ
    }
    return final_data