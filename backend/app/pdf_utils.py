# backend/app/pdf_utils.py
from typing import List, Dict
import pdfplumber
import tabula
import base64
from io import BytesIO

def extract_figures_from_pdf(pdf_path: str) -> List[Dict]:
    """
    PDF から図を検出し base64 data URI 形式で返却する。
    open 失敗や途中の例外はすべて握りつぶして [] を返す。
    """
    try:
        figures = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                for idx, img in enumerate(page.images, start=1):
                    try:
                        x0, y0, x1, y1 = img['x0'], img['y0'], img['x1'], img['y1']
                        cropped = page.within_bbox((x0, y0, x1, y1)).to_image(resolution=150)
                        buf = BytesIO()
                        cropped.original.save(buf, format='PNG')
                        data = base64.b64encode(buf.getvalue()).decode('ascii')
                        figures.append({
                            'page': page_num,
                            'index': idx,
                            'data_uri': f'data:image/png;base64,{data}'
                        })
                    except Exception:
                        continue
        return figures
    except Exception:
        # open自体の失敗やモックによる例外もここで握りつぶす
        return []

def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
    """
    PDF から表を抽出し 2次元リスト形式で返却する。
    """
    try:
        dfs = tabula.read_pdf(pdf_path, pages='all', lattice=True, stream=False)
    except:
        return []
    tables = []
    for i, df in enumerate(dfs, start=1):
        if df.empty:
            continue
        data = df.fillna('').values.tolist()
        tables.append({
            'table_id': i,
            'data':     data
        })
    return tables
