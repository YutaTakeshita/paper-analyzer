# backend/app/pdf_utils.py
# PDF→図・表抽出ロジック

from typing import List, Dict
import pdfplumber
import tabula
import pandas as pd
import base64
from io import BytesIO
from PIL import Image

def extract_figures_from_pdf(pdf_path: str) -> List[Dict]:
    """
    pdfplumber でページ毎に画像を検出し、
    base64 data URI 形式で返却する。
    """
    figures = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages, start=1):
            for idx, img in enumerate(page.images, start=1):
                try:
                    x0, y0, x1, y1 = img["x0"], img["y0"], img["x1"], img["y1"]
                    cropped = page.within_bbox((x0, y0, x1, y1)).to_image(resolution=150)
                    buf = BytesIO()
                    cropped.original.save(buf, format="PNG")
                    data = base64.b64encode(buf.getvalue()).decode("ascii")
                    figures.append({
                        "page": page_num,
                        "index": idx,
                        "data_uri": f"data:image/png;base64,{data}"
                    })
                except Exception:
                    continue
    return figures

def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
    """
    tabula-py で全ページのテーブルを抽出し、
    2次元リスト形式で返却する。
    """
    try:
        dfs = tabula.read_pdf(pdf_path, pages="all", lattice=True, stream=False)
    except Exception:
        return []
    tables = []
    for i, df in enumerate(dfs, start=1):
        if df.empty:
            continue
        data = df.fillna("").values.tolist()
        tables.append({
            "table_id": i,
            "page": None,
            "data": data
        })
    return tables