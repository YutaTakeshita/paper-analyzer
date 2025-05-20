import pytest
from app.pdf_utils import extract_figures_from_pdf, extract_tables_from_pdf

def test_extract_tables_error(monkeypatch, tmp_path):
    """tabula.read_pdf が例外を投げても [] が返ることを確認"""
    def raise_error(*_a, **_k):
        raise Exception("tabula failure")
    monkeypatch.setattr("app.pdf_utils.tabula.read_pdf", raise_error)

    dummy = tmp_path / "dummy.pdf"
    dummy.write_bytes(b"%PDF-1.4\n%EOF")
    assert extract_tables_from_pdf(str(dummy)) == []

def test_extract_figures_error(monkeypatch, tmp_path):
    """pdfplumber.open が例外を投げても [] が返ることを確認"""
    def raise_error(*_a, **_k):
        raise Exception("pdfplumber failure")
    monkeypatch.setattr("app.pdf_utils.pdfplumber.open", raise_error)

    dummy = tmp_path / "dummy.pdf"
    dummy.write_bytes(b"%PDF-1.4\n%EOF")
    assert extract_figures_from_pdf(str(dummy)) == []