#!/usr/bin/env python3
"""
tei2json.py

Simple CLI utility:
$ python tei2json.py path/to/file.tei.xml > out.json
"""

import sys
import json
from pathlib import Path
from lxml import etree

def extract_meta(root):
    """Extract basic metadata from a TEI document."""
    meta = {
        "title": root.findtext(".//titleStmt/title"),
        "journal": root.findtext(".//publicationStmt/idno[@type='journal']"),
        "issued": root.findtext(".//sourceDesc/biblStruct/monogr/imprint/date/@when"),
        "authors": [],
    }
    for pers in root.xpath(".//teiHeader//author/persName", namespaces=root.nsmap):
        name_parts = []
        surname = pers.findtext("surname")
        forename = pers.findtext("forename")
        if forename:
            name_parts.append(forename)
        if surname:
            name_parts.append(surname)
        if name_parts:
            meta["authors"].append(" ".join(name_parts))
    return meta

def extract_sections(root):
    """Extract section headings and plaintext."""
    sections = []
    for div in root.xpath("//text/body/div", namespaces=root.nsmap):
        head = (div.findtext("head") or "").strip()
        text = " ".join(" ".join(div.itertext()).split())  # collapse whitespace
        sections.append({"head": head, "text": text})
    return sections

def main():
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: tei2json.py path/to/file.tei.xml\n")
        sys.exit(1)

    tei_path = Path(sys.argv[1])
    if not tei_path.exists():
        sys.stderr.write(f"File not found: {tei_path}\n")
        sys.exit(1)

    parser = etree.XMLParser(remove_comments=True, recover=True)
    root = etree.parse(str(tei_path), parser).getroot()

    payload = {
        "meta": extract_meta(root),
        "sections": extract_sections(root),
    }

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
