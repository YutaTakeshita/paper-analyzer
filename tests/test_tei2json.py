import pytest
from app.tei2json import convert_xml_to_json

@pytest.fixture
def simple_tei_xml():
    return """
    <article>
      <body>
        <sec><title>A</title><p>Text</p></sec>
        <ref id="r1"><label>1</label><p>Ref</p></ref>
      </body>
    </article>
    """

def test_convert_xml_to_json_minimal(monkeypatch, simple_tei_xml):
    # PDF抽出をモックして空リストを返す
    monkeypatch.setattr("app.tei2json.extract_figures_from_pdf", lambda path: [])
    monkeypatch.setattr("app.tei2json.extract_tables_from_pdf", lambda path: [])
    result = convert_xml_to_json(simple_tei_xml, pdf_path=None)
    assert "meta" in result
    assert result["sections"][0]["head"] == "A"
    assert result["references"][0]["id"] == "r1"
    assert result["figures"] == []
    assert result["tables"] == []

def test_convert_with_pdf(monkeypatch, simple_tei_xml, tmp_path):
    # ダミーPDFパスを用意し、図表抽出をモック
    pdf_file = tmp_path / "dummy.pdf"
    pdf_file.write_bytes(b"%PDF-1.4\n%EOF")
    monkeypatch.setattr("app.tei2json.extract_figures_from_pdf", lambda path: [{"page":1,"index":1,"data_uri":"data"}])
    monkeypatch.setattr("app.tei2json.extract_tables_from_pdf", lambda path: [{"table_id":1,"data":[["a"]]}])
    result = convert_xml_to_json(simple_tei_xml, pdf_path=str(pdf_file))
    assert result["figures"] == [{"page":1,"index":1,"data_uri":"data"}]
    assert result["tables"] == [{"table_id":1,"data":[["a"]]}]