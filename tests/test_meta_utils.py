import pytest
from lxml import etree
from app.meta_utils import extract_meta, normalize_authors

@pytest.fixture
def sample_article_meta():
    xml = """
    <article>
      <front>
        <article-meta>
          <title-group>
            <article-title>Test Title</article-title>
          </title-group>
          <contrib-group>
            <contrib contrib-type="author">
              <surname>Yamada</surname>
              <given-names>Taro</given-names>
            </contrib>
            <contrib contrib-type="author">
              <surname>Suzuki</surname>
              <given-names>Hanako</given-names>
            </contrib>
          </contrib-group>
          <journal-meta>
            <journal-title>Test Journal</journal-title>
          </journal-meta>
          <pub-date>
            <year>2021</year><month>5</month><day>10</day>
          </pub-date>
        </article-meta>
      </front>
    </article>
    """
    return etree.fromstring(xml)

def test_normalize_authors():
    raws = ["Yamada Taro", "  Suzuki   Hanako  ", "Single"]
    assert normalize_authors(raws) == ["Taro Yamada", "Hanako Suzuki", "Single"]

def test_extract_meta(sample_article_meta):
    meta = extract_meta(sample_article_meta)
    assert meta["title"] == "Test Title"
    assert meta["journal"] == "Test Journal"
    assert meta["issued"] == "2021-05-10"
    assert "Taro Yamada" in meta["authors"]
    assert "Hanako Suzuki" in meta["authors"]