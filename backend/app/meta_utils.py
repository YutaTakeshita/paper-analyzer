# backend/app/meta_utils.py
from lxml import etree
from typing import List, Dict

def normalize_authors(raw_authors: List[str]) -> List[str]:
    """
    著者名リストを整形して返す（例：姓・名の並び替えなど）。
    """
    cleaned = []
    for name in raw_authors:
        parts = name.strip().split()
        if len(parts) > 1:
            # surname last format to 'Surname Given'
            cleaned.append(f"{parts[-1]} {' '.join(parts[:-1])}")
        else:
            cleaned.append(parts[0])
    return [n for n in cleaned if n]

def extract_meta(root: etree._Element) -> Dict:
    """
    TEI XML の <article-meta> 以下からメタデータを抽出する。
    抽出項目: title, authors, journal, issued (YYYY-MM-DD)
    """
    meta_root = root.find('.//article-meta')
    if meta_root is None:
        return {}

    title_elem = meta_root.find('.//article-title')
    title = title_elem.text.strip() if title_elem is not None and title_elem.text else None

    authors: List[str] = []
    for contrib in meta_root.findall('.//contrib[@contrib-type="author"]'):
        surname = contrib.findtext('.//surname', default='').strip()
        given   = contrib.findtext('.//given-names', default='').strip()
        name = f"{surname} {given}".strip()
        if name:
            authors.append(name)
    authors = normalize_authors(authors)

    journal = meta_root.findtext('.//journal-title', default=None)
    if journal:
        journal = journal.strip()

    year  = meta_root.findtext('.//pub-date/year',   default=None)
    month = meta_root.findtext('.//pub-date/month',  default=None)
    day   = meta_root.findtext('.//pub-date/day',    default=None)
    issued = None
    if year:
        parts = [year]
        if month:
            parts.append(month.zfill(2))
        if day:
            parts.append(day.zfill(2))
        issued = '-'.join(parts)

    return {
        "title":   title,
        "authors": authors,
        "journal": journal,
        "issued":  issued,
    }
