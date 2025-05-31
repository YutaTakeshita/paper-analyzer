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
        target_id_raw = node.get('target', '') # 元の target (例: "#b1")
        target_id_cleaned = target_id_raw.lstrip('#') 
        display_text = "".join(node.itertext()).strip().rstrip(',.')
        
        if display_text:
            if target_id_cleaned:
                href_value = f"#ref-{target_id_cleaned}" # フロントエンドのID形式に合わせる
                return f'<sup class="citation" data-target-id="{target_id_cleaned}"><a href="{href_value}">{display_text}</a></sup>'
            else:
                return f'<sup class="citation">{display_text}</sup>' 
        else: 
            return "" 

    elif tag_name == 'p':
        content = "".join(_node_to_html_string_for_grobid(child) for child in node.xpath('node()'))
        return f"<p>{content}</p>"

    elif tag_name == 'hi': 
        rend = node.get('rend', '')
        content = "".join(_node_to_html_string_for_grobid(child) for child in node.xpath('node()'))
        if rend == 'italic':
            return f"<em>{content}</em>"
        elif rend == 'bold':
            return f"<strong>{content}</strong>"
        return content 

    elif tag_name in ['formula', 'graphic', 'table', 'figure']: # figure もここで処理
        # <figure> タグ自体とその内容をHTMLとして返す
        # ただし、セクション内の図キャプション抽出は extract_grobid_tei_sections 側で行うので、
        # ここで <figure> を特別扱いしすぎると二重処理になる可能性。
        # シンプルにタグと内容を返すか、特定の変換を行うか検討が必要。
        # GROBID の <figure> は本文の一部として扱われることが多いので、
        # この関数が本文生成に使われるなら、その内容を返すのが適切。
        # ここでは、一旦figureタグ自体は出力せず、中身のテキスト関連のみを処理する方向で
        # 下の「上記以外のタグ」のロジックに任せる。
        # もし <figure> タグ自体をHTMLに残したい場合は以下を有効化：
        # return etree.tostring(node, encoding='unicode', method='html').strip()
        pass # 下の汎用ロジックに任せる

    # 上記以外のタグ (div や figure など、ここでは text コンテンツを優先)
    inner_html_parts = []
    if node.text:
        inner_html_parts.append(node.text.strip())
    for child in node:
        inner_html_parts.append(_node_to_html_string_for_grobid(child))
        if child.tail:
            inner_html_parts.append(child.tail.strip())
    
    # タグ名が figure や table の場合、特別なプレースホルダーや空文字列を返すことも検討
    # ここではタグ自体は出力せず、テキスト内容のみを連結
    if tag_name in ['figure', 'table', 'formula']: # これらのタグに遭遇したら、そのタグは出力せず、中身のテキストだけを処理
         return "".join(filter(None, inner_html_parts))


    # デフォルトはタグ自身は出力せず、子ノードを再帰的に処理して内容を連結
    # ただし、特定のタグ (例: list, item) はHTMLタグとして残したい場合がある
    # この関数の汎用性と呼び出し元コンテキストに注意が必要
    # 今回はセクション本文の <p> や <hi>, <ref> 以外のタグは無視して中身だけを連結する想定
    return "".join(filter(None, inner_html_parts))


def _extract_single_section_data(section_div_element: etree._Element, current_level: int) -> Dict:
    """
    単一の <div[tei:head]> 要素からセクションデータを抽出するヘルパー関数。
    サブセクションも再帰的に処理する。
    """
    head_element = section_div_element.find('./tei:head', namespaces=TEI_NS)
    section_title = "".join(head_element.itertext()).strip() if head_element is not None else None

    html_content_parts = []
    # <head> とネストされた <div[tei:head]> (サブセクション) を除いた子ノードから本文を生成
    # figure や table タグもここでは本文として扱わない (図キャプションは別途抽出)
    for child_node in section_div_element.xpath('./node()[not(self::tei:head) and not(self::tei:div[tei:head]) and not(self::tei:figure) and not(self::tei:table)]', namespaces=TEI_NS):
        html_content_parts.append(_node_to_html_string_for_grobid(child_node))
    
    final_html_text = "".join(filter(None, html_content_parts)).strip()
    final_html_text = re.sub(r'\s{2,}', ' ', final_html_text)
    final_html_text = re.sub(r'(\n\s*){2,}', '\n\n', final_html_text).strip()

    figures_in_section = []
    # section_div_element の直接の子または孫要素として <figure type="figure"> を検索 (type="table" を除く)
    # ネストされたサブセクション内の図は、そのサブセクションで処理されるべき
    for fig_element in section_div_element.xpath('./tei:figure[not(@type="table")] | .//tei:p/tei:figure[not(@type="table")]', namespaces=TEI_NS):
        # サブセクション内の図を二重カウントしないように、現在のセクション直下のものだけを対象にする工夫が必要
        # 簡単な方法としては、figureの親のdivが現在のsection_div_elementであるかを確認する
        # ただし、xpathでより厳密に指定する方が良い
        # ここでは、一旦 section_div_element の子孫全てを対象としてみるが、重複の可能性に注意
        # より正確には、サブセクションのdivを除外したパスで検索する

        fig_id = fig_element.get('{http://www.w3.org/XML/1998/namespace}id')
        caption_parts = []
        fig_head_el = fig_element.find('./tei:head', namespaces=TEI_NS)
        if fig_head_el is not None: caption_parts.append("".join(fig_head_el.itertext()).strip())
        
        fig_label_el = fig_element.find('./tei:label', namespaces=TEI_NS)
        if fig_label_el is not None and fig_label_el.text:
            label_text = fig_label_el.text.strip()
            if not any(label_text in part for part in caption_parts): # 重複を避ける
                 caption_parts.insert(0, f"Figure {label_text}")

        fig_desc_el = fig_element.find('./tei:figDesc', namespaces=TEI_NS)
        if fig_desc_el is not None:
            desc_text = "".join(fig_desc_el.itertext()).strip()
            if desc_text: caption_parts.append(desc_text)
        
        fig_caption = " ".join(filter(None, caption_parts)).strip()
        fig_caption = re.sub(r'\s*:\s*', ': ', fig_caption).strip() # "Text :" -> "Text: "
        fig_caption = re.sub(r'\s{2,}', ' ', fig_caption)
        
        if fig_id or fig_caption: figures_in_section.append({"id": fig_id, "caption": fig_caption})

    subsections = []
    # section_div_element の直接の子であるサブセクションを再帰的に処理
    for sub_section_div in section_div_element.xpath('./tei:div[tei:head]', namespaces=TEI_NS):
        subsections.append(_extract_single_section_data(sub_section_div, current_level + 1))

    return {
        'head': section_title,
        'text': final_html_text, # 空文字列も許容
        'figures': figures_in_section,
        'level': current_level,
        'subsections': subsections
    }

def extract_grobid_tei_sections(root: etree._Element) -> List[Dict]:
    """
    GROBID TEI XMLの <body> 内のトップレベルの <div[tei:head]> 要素から
    セクション構造を階層的に抽出する。
    """
    processed_sections = []
    body = root.find('.//tei:body', namespaces=TEI_NS)

    if body is not None:
        # トップレベルのセクション (<body> の直接の子である <div[tei:head]>) を処理
        for section_div in body.xpath('./tei:div[tei:head]', namespaces=TEI_NS):
            section_data = _extract_single_section_data(section_div, 1) # トップレベルは level 1
            
            # セクションを追加する条件: タイトルがある、または本文がある、または図がある、またはサブセクションがある
            plain_text_check = re.sub('<[^<]+?>', '', section_data['text']).strip()
            if section_data['head'] or plain_text_check or section_data['figures'] or section_data['subsections']:
                processed_sections.append(section_data)
            elif not section_data['head'] and not plain_text_check and not section_data['figures'] and not section_data['subsections']:
                # タイトルも本文も図もサブセクションもない完全に空のものはスキップ
                continue


    return processed_sections


def extract_grobid_tei_references(root: etree._Element) -> List[Dict]:
    # ... (この関数は変更なし) ...
    references = []
    list_bibl_element = root.find('.//tei:listBibl', namespaces=TEI_NS)
    
    if list_bibl_element is not None:
        for bibl_struct in list_bibl_element.xpath('./tei:biblStruct', namespaces=TEI_NS):
            ref_id = bibl_struct.get('{http://www.w3.org/XML/1998/namespace}id')
            
            text_parts = []
            analytic_el = bibl_struct.find('./tei:analytic', namespaces=TEI_NS)
            if analytic_el is not None:
                authors_list = []
                for author_el_in_analytic in analytic_el.xpath('./tei:author/tei:persName', namespaces=TEI_NS):
                    surnames = [s.text.strip() for s in author_el_in_analytic.findall('tei:surname', namespaces=TEI_NS) if s.text]
                    forenames = [f.text.strip() for f in author_el_in_analytic.findall('tei:forename', namespaces=TEI_NS) if f.text]
                    name_str = " ".join(forenames + surnames).strip()
                    if name_str: authors_list.append(name_str)
                if authors_list: text_parts.append(", ".join(authors_list) + ".")
                title_el = analytic_el.find('./tei:title[@level="a"]', namespaces=TEI_NS)
                if title_el is not None:
                    title_text = "".join(title_el.itertext()).strip().rstrip('.,')
                    if title_text: text_parts.append(title_text + ".")

            monogr_el = bibl_struct.find('./tei:monogr', namespaces=TEI_NS)
            if monogr_el is not None:
                monogr_title_el = monogr_el.find('./tei:title', namespaces=TEI_NS)
                if monogr_title_el is not None:
                    title_text = "".join(monogr_title_el.itertext()).strip()
                    if title_text: text_parts.append(title_text)
                imprint_el = monogr_el.find('./tei:imprint', namespaces=TEI_NS)
                if imprint_el is not None:
                    date_el = imprint_el.find('./tei:date[@type="published"]', namespaces=TEI_NS)
                    if date_el is not None and date_el.get('when'):
                        year = date_el.get('when').split('-')[0]
                        text_parts.append(year)
                    bibl_scopes_text = []
                    volume_el = imprint_el.find('./tei:biblScope[@unit="volume"]', namespaces=TEI_NS)
                    if volume_el is not None and volume_el.text: bibl_scopes_text.append(volume_el.text.strip())
                    issue_el = imprint_el.find('./tei:biblScope[@unit="issue"]', namespaces=TEI_NS)
                    if issue_el is not None and issue_el.text: bibl_scopes_text.append(f"({issue_el.text.strip()})")
                    page_el = imprint_el.find('./tei:biblScope[@unit="page"]', namespaces=TEI_NS)
                    if page_el is not None:
                        page_from = page_el.get('from'); page_to = page_el.get('to')
                        page_text = page_el.text.strip() if page_el.text else ''
                        if page_from and page_to: bibl_scopes_text.append(f"{page_from}-{page_to}")
                        elif page_from: bibl_scopes_text.append(f"{page_from}")
                        elif page_text: bibl_scopes_text.append(page_text)
                    if bibl_scopes_text: text_parts.append(":".join(bibl_scopes_text) if len(bibl_scopes_text) > 1 and bibl_scopes_text[0].isdigit() and bibl_scopes_text[1].replace('(','').replace(')','').isdigit() else "; ".join(bibl_scopes_text))
            
            doi_el = bibl_struct.find('.//tei:idno[@type="DOI"]', namespaces=TEI_NS)
            if doi_el is not None and doi_el.text: text_parts.append(f"doi:{doi_el.text.strip()}")
            
            ref_text = " ".join(filter(None, text_parts))
            ref_text = re.sub(r'\s{2,}', ' ', ref_text).strip()
            ref_text = ref_text.replace(" .", ".").replace(" ;", ";").replace(" ,", ",").replace(" :", ":")
            ref_text = ref_text.rstrip('.') + "."

            if ref_id or ref_text:
                references.append({
                    'id': ref_id, 
                    'text': ref_text,
                    'search_query': ref_text
                })
    return references

# エイリアス設定 (tei2json.py からの呼び出しに対応)
extract_sections_from_tei = extract_grobid_tei_sections
extract_references_from_tei = extract_grobid_tei_references
