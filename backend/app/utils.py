import re
import xml.etree.ElementTree as ET
from urllib.parse import quote_plus

# Helper to serialize paragraphs with <ref> tags as superscript citations
def _serialize_paragraph_with_refs(elem):
    """
    Recursively serialize an XML element, wrapping <ref> text in <sup class="citation">.
    """
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        if child.tag == 'ref':
            # Wrap citation references
            ref_text = (child.text or '').strip()
            parts.append(f'<sup class="citation">{ref_text}</sup>')
        else:
            # Recursively handle nested elements
            parts.append(_serialize_paragraph_with_refs(child))
        if child.tail:
            parts.append(child.tail)
    return ''.join(parts)

def extract_sections_from_tei(tei_xml: str) -> dict:
    """
    TEI/XML 文字列から主要セクションを抽出。デフォルト namespace を削除して扱いやすくする。
    """
    # Remove namespaces for easier parsing
    tei_xml = re.sub(r'\s+xmlns(:\w+)?="[^"]+"', '', tei_xml)
    tei_xml = re.sub(r'\s+[A-Za-z0-9]+:[A-Za-z0-9]+="[^"]+"', '', tei_xml)
    try:
        root = ET.fromstring(tei_xml)
    except ET.ParseError:
        return {}

    # Extract abstract from profileDesc as Summary
    # (ensures Summary appears before Introduction)
    sections = {}
    # Try TEI namespace if present
    ns = {'tei': 'http://www.tei-c.org/ns/1.0'}
    # Look for profileDesc/abstract paragraphs
    abstract_elem = root.find('.//profileDesc/abstract')
    if abstract_elem is None:
        # Try with namespace
        abstract_elem = root.find('.//tei:profileDesc/tei:abstract', ns)
    if abstract_elem is not None:
        summary_texts = []
        # Collect all <p> under abstract
        for p in abstract_elem.findall('.//p', ns):
            txt = ''.join(p.itertext()).strip()
            if txt:
                summary_texts.append(txt)
        if summary_texts:
            # Wrap each summary paragraph in <p> for proper HTML structure and CSS styling
            sections['Summary'] = ''.join(f'<p>{paragraph}</p>' for paragraph in summary_texts)

    # Scan every <div> element in the document
    for div in root.findall('.//div'):
        head = div.find('head')
        if head is None or not head.text:
            continue
        raw_name = head.text.strip()
        lname = raw_name.lower()

        # Normalize both "method" and "material" variants into Methods
        if 'method' in lname or 'material' in lname:
            key = 'Methods'
        elif 'introduction' in lname:
            key = 'Introduction'
        elif 'result' in lname:
            key = 'Results'
        elif 'discussion' in lname:
            key = 'Discussion'
        elif 'abstract' in lname:
            key = 'Abstract'
        else:
            key = raw_name.title()

        # Extract paragraphs under this div, preserving paragraph breaks and citations
        paras = []
        for p in div.findall('.//p'):
            # Serialize text, wrapping <ref> tags as superscript citations
            serialized = _serialize_paragraph_with_refs(p).strip()
            if serialized:
                paras.append(serialized)
        if not paras:
            continue

        # Wrap each paragraph in <p> to enable paragraph-level styling
        content = ''.join(f'<p>{para}</p>' for para in paras)
        sections[key] = content

    # Remove sections with empty content
    sections = {k: v for k, v in sections.items() if v.strip()}
    # Remove generic 'Methods' parent section if child sections are present
    if 'Methods' in sections:
        sections.pop('Methods', None)
    # Keep only sections up to and including 'Discussion'
    keys = list(sections.keys())
    if 'Discussion' in keys:
        idx = keys.index('Discussion')
        sections = {k: sections[k] for k in keys[:idx + 1]}

    # Extract bibliography entries only from <listBibl> (with or without namespace)
    refs = []
    # Without namespace
    for bibl in root.findall('.//listBibl/bibl'):
        text = ''.join(bibl.itertext()).strip()
        if text:
            refs.append(text)
    # With TEI namespace
    if not refs:
        for bibl in root.findall('.//tei:listBibl/tei:bibl', ns):
            text = ''.join(bibl.itertext()).strip()
            if text:
                refs.append(text)
    # As a last resort, include <biblStruct> only under listBibl
    if not refs:
        for bibl in root.findall('.//listBibl//biblStruct'):
            text = ''.join(bibl.itertext()).strip()
            if text:
                refs.append(text)
    # Build clickable list: each <li> contains an <a> to Google search, with an id for in-page link
    if refs:
        items = []
        for idx, ref in enumerate(refs, start=1):
            query = quote_plus(ref)
            url = f'https://www.google.com/search?q={query}'
            items.append(
                f'<li id="ref{idx}">'
                f'<a href="{url}" target="_blank" rel="noopener noreferrer">'
                f'{ref}'
                f'</a>'
                f'</li>'
            )
        sections['References'] = '<ol>' + ''.join(items) + '</ol>'

    return sections