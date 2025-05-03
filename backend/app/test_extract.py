# test_extract.py
import json
from utils import extract_sections_from_tei

sample_path = "sample_tei.xml"

# ファイルを読み込む
with open(sample_path, "r", encoding="utf-8") as f:
    raw = f.read().strip()

# 先にJSONとして解釈を試みる
try:
    data = json.loads(raw)
    tei_xml = data.get("tei", "")
    if not tei_xml:
        print("Error: 'tei' field not found in JSON")
        exit(1)
except json.JSONDecodeError:
    # JSONでなければXMLだとみなす
    tei_xml = raw

# 抽出処理
sections = extract_sections_from_tei(tei_xml)
if not sections:
    print("No sections extracted. Check TEI content.")
else:
    for name, text in sections.items():
        print(f"=== {name.upper()} ===")
        print(text[:200], "...\n")