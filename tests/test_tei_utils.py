import pytest
from lxml import etree
from app.tei_utils import extract_jats_sections, extract_jats_references

@pytest.fixture
def simple_tei():
    xml = """
    <article>
      <body>
        <sec><title>Intro</title><p>Hello world</p></sec>
        <ref id="R1"><label>1</label><mixed-citation>Ref text</mixed-citation></ref>
      </body>
    </article>
    """
    return etree.fromstring(xml)

def test_extract_jats_sections(simple_tei):
    secs = extract_jats_sections(simple_tei)
    assert len(secs) == 1
    assert secs[0]["head"] == "Intro"
    assert "Hello world" in secs[0]["text"]

def test_extract_jats_references(simple_tei):
    refs = extract_jats_references(simple_tei)
    assert refs == [{"id": "R1", "text": "1 Ref text"}]