import os
import pytest
from app.tei_utils import extract_jats_sections, extract_meta

@pytest.fixture
def sample_tei():
    path = os.path.join(os.path.dirname(__file__), "fixtures", "sample_tei.xml")
    return open(path, encoding="utf-8").read()

def test_extract_meta(sample_tei):
    from lxml import etree
    root = etree.fromstring(sample_tei.encode("utf-8"))
    meta = extract_meta(root)
    assert meta["title"] == "テストタイトル"
    assert "山田 太郎" in meta["authors"]

def test_extract_sections(sample_tei):
    from lxml import etree
    root = etree.fromstring(sample_tei.encode("utf-8"))
    secs = extract_jats_sections(root)
    # 例：「はじめに」セクションが取れている
    assert any(sec["head"] == "はじめに" for sec in secs)