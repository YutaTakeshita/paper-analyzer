# backend/app/tei_utils.py
import re
from typing import List, Dict, Union
from lxml import etree
from collections import defaultdict

# TEI名前空間の定義 (GROBIDの出力に合わせて)
TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}

def _node_to_html_string_for_grobid(node: Union[etree._Element, str]) -> str:
    """
    GROBID TEIのノード（要素またはテキスト）をHTML文字列に変換する。
    本文中の<ref type="bibr">を<sup><a>...</a></sup>に変換する。
    それ以外のタグは適宜HTMLタグとして保持する（例：<p>, <em>, <strong>など）。
    """
    if isinstance(node, str): # etree._ElementUnicodeResult (テキストノード) の場合
        return node.strip() # テキストは空白をトリムして返す

    # 要素ノードの場合
    tag_name = etree.QName(node).localname # 名前空間を除いたタグ名を取得

    if tag_name == 'ref' and node.get('type') == 'bibr':
        target_id = node.get('target', '').lstrip('#') # "#b0" -> "b0"
        display_text = "".join(node.itertext()).strip().rstrip(',.') # 末尾のカンマやピリオドを除去
        
        if display_text: # 表示テキストがあれば何らかの処理
            if target_id : # ターゲットIDがあればリンク付き
                return f'<sup class="citation" data-target-id="{target_id}"><a href="#{target_id}">{display_text}</a></sup>'
            else: # ターゲットIDがなくても、引用数字ならsupで囲む (リンクなし)
                return f'<sup class="citation">{display_text}</sup>' 
        else: 
            return "" 

    elif tag_name == 'p':
        # <p> タグの場合、その内部を再帰的に処理して文字列化
        # node.xpath('node()') は現在のノードの子ノード全て (テキストノード含む) を取得
        content = "".join(_node_to_html_string_for_grobid(child) for child in node.xpath('node()'))
        return f"<p>{content}</p>"

    elif tag_name == 'hi': # 例えば <hi rend="italic"> のような場合
        rend = node.get('rend', '')
        content = "".join(_node_to_html_string_for_grobid(child) for child in node.xpath('node()'))
        if rend == 'italic':
            return f"<em>{content}</em>"
        elif rend == 'bold':
            return f"<strong>{content}</strong>"
        # 他のrend属性 (例: superscript, subscript) も必要なら追加
        return content # 未知のrend属性はそのまま内容を返す

    elif tag_name in ['formula', 'graphic', 'table', 'figure']:
        # これらの要素は、内容が複雑な場合があるため、
        # ここではetree.tostringでそのままHTMLとして出力する。
        # より詳細な変換が必要な場合は、各要素ごとに専用の処理関数を作成する。
        # <figure>内の<graphic url="...">を<img>に変換するなども考えられる。
        return etree.tostring(node, encoding='unicode', method='html').strip()

    # 上記以外のタグは、そのタグ自身は出力せず (構造を示すタグが多いと想定)、
    # 子ノードを再帰的に処理して内容を連結する。
    # (例: <div>, <item> in <list>, <tr>, <td> in <table>など、
    #  _node_to_html_string_for_grobidが呼ばれる文脈による)
    inner_html_parts = []
    if node.text: # 要素の直下のテキスト (例: <item>Some text <child/> more text</item> の "Some text ")
        inner_html_parts.append(node.text.strip())
    for child in node: # 子要素をイテレート
        inner_html_parts.append(_node_to_html_string_for_grobid(child)) # 再帰呼び出し
        if child.tail: # 子要素の後のテキスト (例: <item>Some text <child/> more text</item> の " more text")
            inner_html_parts.append(child.tail.strip())
    
    return "".join(filter(None, inner_html_parts))


def extract_grobid_tei_sections(root: etree._Element) -> List[Dict]:
    """
    GROBID TEI XMLの <body> 内の <div xmlns="http://www.tei-c.org/ns/1.0"> 要素から
    セクションの見出しと本文（HTML形式）を抽出する。
    本文中の <ref type="bibr"> は <sup><a> タグに変換する。
    """
    processed_sections = []
    body = root.find('.//tei:body', namespaces=TEI_NS)

    if body is not None:
        # トップレベルの<div>（セクションとみなせるもの、通常<head>を持つ）を処理
        for section_div in body.xpath('./tei:div[tei:head]', namespaces=TEI_NS):
            head_element = section_div.find('./tei:head', namespaces=TEI_NS)
            # <head>内のテキストを全て結合（<hi>タグなどを含む場合を考慮）
            section_title = "".join(head_element.itertext()).strip() if head_element is not None else "Untitled Section"

            html_content_parts = []
            # <head> を除いた section_div の子ノード (要素ノードとテキストノード) を処理
            for child_node in section_div.xpath('./node()[not(self::tei:head)]', namespaces=TEI_NS):
                html_content_parts.append(_node_to_html_string_for_grobid(child_node))
            
            final_html_text = "".join(filter(None, html_content_parts)).strip()
            # 空白や改行の正規化
            final_html_text = re.sub(r'\s{2,}', ' ', final_html_text) 
            final_html_text = re.sub(r'(\n\s*){2,}', '\n\n', final_html_text).strip()

            # セクション内の図キャプション抽出 (GROBIDの<figure>タグから)
            figures_in_section = []
            # section_div の子孫要素として <figure> を検索
            for fig_element in section_div.xpath('.//tei:figure[not(@type="table")]', namespaces=TEI_NS):
                fig_id = fig_element.get('{http://www.w3.org/XML/1998/namespace}id') # xml:id
                
                caption_parts = []
                fig_head_el = fig_element.find('./tei:head', namespaces=TEI_NS) # 図のタイトル/キャプション
                if fig_head_el is not None:
                    caption_parts.append("".join(fig_head_el.itertext()).strip())
                
                fig_label_el = fig_element.find('./tei:label', namespaces=TEI_NS) # 図のラベル (例: "1")
                if fig_label_el is not None and fig_label_el.text:
                    # ラベルがキャプションの先頭に来るように調整 (例: "Figure 1: ...")
                    # ただし、<head>に既に "Figure 1" が含まれている場合もあるので、重複に注意
                    if not any(fig_label_el.text.strip() in part for part in caption_parts):
                         caption_parts.insert(0, f"Figure {fig_label_el.text.strip()}")


                fig_desc_el = fig_element.find('./tei:figDesc', namespaces=TEI_NS) # 詳細な説明
                if fig_desc_el is not None:
                    desc_text = "".join(fig_desc_el.itertext()).strip()
                    if desc_text:
                        caption_parts.append(desc_text)
                
                fig_caption = " ".join(filter(None, caption_parts)).strip()
                fig_caption = re.sub(r'\s*:\s*', ': ', fig_caption) # "Figure 1 :" -> "Figure 1: "
                fig_caption = re.sub(r'\s{2,}', ' ', fig_caption)
                
                if fig_id or fig_caption:
                    figures_in_section.append({"id": fig_id, "caption": fig_caption})

            # 実質的なテキスト内容があるかチェック (HTMLタグを除いたプレーンテキストで判断)
            plain_text_check = re.sub('<[^<]+?>', '', final_html_text).strip()
            if section_title != "Untitled Section" or plain_text_check:
                processed_sections.append({
                    'head': section_title,
                    'text': final_html_text if final_html_text else "",
                    'figures': figures_in_section 
                })
    return processed_sections


def extract_grobid_tei_references(root: etree._Element) -> List[Dict]:
    """
    GROBID TEI XMLの <listBibl> 内の <biblStruct> 要素から参考文献を抽出する。
    IDと整形されたテキストを返す。
    """
    references = []
    list_bibl_element = root.find('.//tei:listBibl', namespaces=TEI_NS)
    
    if list_bibl_element is not None:
        for bibl_struct in list_bibl_element.xpath('./tei:biblStruct', namespaces=TEI_NS):
            ref_id = bibl_struct.get('{http://www.w3.org/XML/1998/namespace}id')
            
            text_parts = []
            
            # Analytic part (article, chapter, etc.)
            analytic_el = bibl_struct.find('./tei:analytic', namespaces=TEI_NS)
            if analytic_el is not None:
                # Authors
                authors_list = []
                for author_el_in_analytic in analytic_el.xpath('./tei:author/tei:persName', namespaces=TEI_NS):
                    surnames = [s.text.strip() for s in author_el_in_analytic.findall('tei:surname', namespaces=TEI_NS) if s.text]
                    forenames = [f.text.strip() for f in author_el_in_analytic.findall('tei:forename', namespaces=TEI_NS) if f.text]
                    name_str = " ".join(forenames + surnames).strip()
                    if name_str:
                        authors_list.append(name_str)
                if authors_list:
                    text_parts.append(", ".join(authors_list) + ".")

                # Article Title
                title_el = analytic_el.find('./tei:title[@level="a"]', namespaces=TEI_NS) # type="main" がない場合も考慮
                if title_el is not None:
                    title_text = "".join(title_el.itertext()).strip().rstrip('.,') # 末尾の不要な句読点を削除
                    if title_text:
                         text_parts.append(title_text + ".")


            # Monographic part (journal, book, etc.)
            monogr_el = bibl_struct.find('./tei:monogr', namespaces=TEI_NS)
            if monogr_el is not None:
                # Journal/Book Title
                monogr_title_el = monogr_el.find('./tei:title', namespaces=TEI_NS) # level j or m
                if monogr_title_el is not None:
                    title_text = "".join(monogr_title_el.itertext()).strip()
                    if title_text:
                        text_parts.append(title_text)
                
                # Imprint (publication details)
                imprint_el = monogr_el.find('./tei:imprint', namespaces=TEI_NS)
                if imprint_el is not None:
                    # Publication Date
                    date_el = imprint_el.find('./tei:date[@type="published"]', namespaces=TEI_NS)
                    if date_el is not None and date_el.get('when'):
                        year = date_el.get('when').split('-')[0] # 年のみ取得する例
                        text_parts.append(year)
                    
                    # Volume, Issue, Pages
                    bibl_scopes_text = []
                    volume_el = imprint_el.find('./tei:biblScope[@unit="volume"]', namespaces=TEI_NS)
                    if volume_el is not None and volume_el.text:
                        bibl_scopes_text.append(volume_el.text.strip())
                    
                    issue_el = imprint_el.find('./tei:biblScope[@unit="issue"]', namespaces=TEI_NS)
                    if issue_el is not None and issue_el.text:
                         bibl_scopes_text.append(f"({issue_el.text.strip()})") # 例: (2)

                    page_el = imprint_el.find('./tei:biblScope[@unit="page"]', namespaces=TEI_NS)
                    if page_el is not None:
                        page_from = page_el.get('from')
                        page_to = page_el.get('to')
                        page_text = page_el.text.strip() if page_el.text else ''
                        if page_from and page_to: bibl_scopes_text.append(f"{page_from}-{page_to}")
                        elif page_from: bibl_scopes_text.append(f"{page_from}")
                        elif page_text: bibl_scopes_text.append(page_text)
                    
                    if bibl_scopes_text:
                        text_parts.append(":".join(bibl_scopes_text) if len(bibl_scopes_text) > 1 and bibl_scopes_text[0].isdigit() and bibl_scopes_text[1].replace('(','').replace(')','').isdigit() else "; ".join(bibl_scopes_text))


            # DOI
            # DOIはanalyticまたはmonogrのどちらか、あるいはbiblStruct直下にある可能性も
            doi_el = bibl_struct.find('.//tei:idno[@type="DOI"]', namespaces=TEI_NS)
            if doi_el is not None and doi_el.text:
                text_parts.append(f"doi:{doi_el.text.strip()}")
            
            ref_text = " ".join(filter(None, text_parts))
            ref_text = re.sub(r'\s{2,}', ' ', ref_text).strip()
            ref_text = ref_text.replace(" .", ".").replace(" ;", ";").replace(" ,", ",").replace(" :", ":")
            ref_text = ref_text.rstrip('.') + "." # 確実にピリオドで終わるように

            if ref_id or ref_text:
                references.append({
                    'id': ref_id, 
                    'text': ref_text,
                    'search_query': ref_text # ★ 検索クエリとして文献テキスト全体を追加 (または整形したタイトルなど)
                })
    return references

# --- エイリアス設定 ---
# app.meta_utils.py側でGROBID対応版が extract_meta_from_tei としてエクスポートされている前提
# このファイルはセクションと参考文献の抽出に専念するため、メタ関連のインポートやエイリアスは不要。

extract_sections_from_tei = extract_grobid_tei_sections
extract_references_from_tei = extract_grobid_tei_references
