# backend/app/meta_utils.py 修正案
from lxml import etree
from typing import List, Dict

TEI_NS = {'tei': 'http://www.tei-c.org/ns/1.0'}

def normalize_authors_for_grobid(authors_elements: List[etree._Element]) -> List[str]:
    """
    GROBID TEI XMLの著者要素リストから著者名を整形して返す。
    <persName>内の<forename>と<surname>、または<author>直下の<orgName>を優先する。
    """
    authors = []
    for author_el in authors_elements:
        name_found = False
        # Case 1: <persName> が存在する場合 (個人著者)
        pers_name_el = author_el.find('tei:persName', namespaces=TEI_NS)
        if pers_name_el is not None:
            forename_parts = []
            for fn_el in pers_name_el.findall('tei:forename', namespaces=TEI_NS):
                if fn_el.text:
                    forename_parts.append(fn_el.text.strip())
            forename_str = " ".join(filter(None, forename_parts))

            surname_el = pers_name_el.find('tei:surname', namespaces=TEI_NS)
            surname = surname_el.text.strip() if surname_el is not None and surname_el.text else ''
            
            current_author_name_parts = []
            if forename_str:
                current_author_name_parts.append(forename_str)
            if surname:
                current_author_name_parts.append(surname)
            
            if current_author_name_parts:
                authors.append(" ".join(current_author_name_parts))
                name_found = True
            elif "".join(pers_name_el.itertext()).strip(): # persName内に直接テキストがある場合
                name_str = "".join(pers_name_el.itertext()).strip()
                # "The Florey" のようなケースを避けるため、ある程度短いものに限定するか、
                # あるいは一般的な名前に見えないものは除外するなどのヒューリスティックが必要になることも。
                # ここでは一旦、persNameがあればそのテキストを採用。
                authors.append(name_str)
                name_found = True
        
        if name_found:
            continue

        # Case 2: <persName> がなく、<author> 直下に <orgName> が存在する場合 (グループ著者)
        org_name_el = author_el.find('tei:orgName', namespaces=TEI_NS)
        if org_name_el is not None:
            org_name_text = "".join(org_name_el.itertext()).strip()
            if org_name_text:
                authors.append(org_name_text)
                name_found = True
        
        if name_found:
            continue
            
        # Case 3: <persName> も <orgName> もない場合、<author> タグ直下のテキストで、かつ短いものを試す
        # (所属情報が紛れ込むのを避けるため、非常に限定的にする)
        # <affiliation> を子に持たないことを確認
        if author_el.find('tei:affiliation', namespaces=TEI_NS) is None:
            author_text_nodes = author_el.xpath("./text()") # author直下のテキストノードのみ
            direct_text = " ".join(node.strip() for node in author_text_nodes if node.strip()).strip()
            if direct_text and len(direct_text.split()) < 5 : # 例えば5単語未満など（グループ名想定）
                authors.append(direct_text)
                name_found = True
                
    return [author for author in authors if author]


def extract_meta_from_grobid_tei(root: etree._Element) -> Dict:
    metadata = {}
    tei_header = root.find('tei:teiHeader', namespaces=TEI_NS)

    if tei_header is None:
        return {}

    # 論文タイトル
    title_el = tei_header.find('.//tei:titleStmt/tei:title[@level="a"][@type="main"]', namespaces=TEI_NS)
    if title_el is not None:
        metadata['title'] = "".join(title_el.itertext()).strip()
    else:
        title_el_fallback = tei_header.find('.//tei:titleStmt/tei:title', namespaces=TEI_NS)
        if title_el_fallback is not None:
            metadata['title'] = "".join(title_el_fallback.itertext()).strip()

    # 著者: <sourceDesc> 内の <analytic> の <author> を優先
    authors_elements = tei_header.findall('.//tei:sourceDesc/tei:biblStruct/tei:analytic/tei:author', namespaces=TEI_NS)
    
    # GROBIDの出力では、<titleStmt>直下の<author>は編者や異なる役割の場合があるため、
    # sourceDescから取得できない場合のフォールバックとするか、慎重に扱う。
    # 今回の出力ではsourceDescからの抽出で十分そう。
    # if not authors_elements:
    #     authors_elements = tei_header.findall('.//tei:titleStmt/tei:author', namespaces=TEI_NS)

    if authors_elements:
        authors_list = normalize_authors_for_grobid(authors_elements)
        if authors_list: # 空リストでないことを確認
            metadata['authors'] = authors_list
    
    # 発行日
    pub_date_el = tei_header.find('.//tei:publicationStmt/tei:date[@type="published"]', namespaces=TEI_NS)
    if pub_date_el is not None and pub_date_el.get('when'):
        metadata['issued'] = pub_date_el.get('when')
    else:
        pub_date_el_monogr = tei_header.find('.//tei:sourceDesc/tei:biblStruct/tei:monogr/tei:imprint/tei:date[@type="published"]', namespaces=TEI_NS)
        if pub_date_el_monogr is not None and pub_date_el_monogr.get('when'):
             metadata['issued'] = pub_date_el_monogr.get('when')

    # ジャーナル名
    journal_title_el = tei_header.find('.//tei:sourceDesc/tei:biblStruct/tei:monogr/tei:title[@level="j"]', namespaces=TEI_NS)
    if journal_title_el is not None:
         full_journal_text = "".join(journal_title_el.itertext()).strip()
         if full_journal_text:
            metadata['journal'] = full_journal_text
    else:
        monogr_title_el = tei_header.find('.//tei:sourceDesc/tei:biblStruct/tei:monogr/tei:title', namespaces=TEI_NS)
        if monogr_title_el is not None:
            full_monogr_title_text = "".join(monogr_title_el.itertext()).strip()
            if full_monogr_title_text:
                metadata['journal'] = full_monogr_title_text
    
    # アブストラクト
    abstract_el = tei_header.find('.//tei:profileDesc/tei:abstract', namespaces=TEI_NS)
    if abstract_el is not None:
        abstract_text_parts = []
        # abstract内のdiv/pを想定
        for content_el in abstract_el.xpath('./tei:div/tei:p | ./tei:p', namespaces=TEI_NS):
            abstract_text_parts.append("".join(content_el.itertext()).strip())
        if not abstract_text_parts: # divやpがない場合、abstract直下のテキストを試す
             abstract_text_plain = "".join(abstract_el.itertext()).strip()
             if abstract_text_plain: # abstractタグ自体がテキストを持つ場合
                 abstract_text_parts.append(abstract_text_plain)
        
        full_abstract_text = "\n\n".join(filter(None, abstract_text_parts))
        if full_abstract_text:
            metadata['abstract'] = full_abstract_text

    return metadata

# エイリアス設定
extract_meta_from_tei = extract_meta_from_grobid_tei