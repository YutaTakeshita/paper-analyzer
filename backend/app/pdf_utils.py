# backend/app/pdf_utils.py
from typing import List, Dict
import pdfplumber
import tabula
import base64
from io import BytesIO
import logging # logging をインポート

logger = logging.getLogger(__name__) # logger を定義

def extract_figures_from_pdf(pdf_path: str) -> List[Dict]:
    """
    PDF から図を検出し base64 data URI 形式で返却する。
    エラー発生時はログに出力し、空のリストを返す。
    """
    figures = []
    if not pdf_path:
        logger.warning("extract_figures_from_pdf: pdf_path is None or empty.")
        return figures
        
    try:
        with pdfplumber.open(pdf_path) as pdf:
            logger.info(f"Processing PDF for figures: {pdf_path}, Pages: {len(pdf.pages)}")
            for page_num, page in enumerate(pdf.pages, start=1):
                if not page.images: # ページに画像がない場合はスキップ
                    continue
                logger.info(f"Page {page_num}: Found {len(page.images)} image objects.")
                for idx, img_obj in enumerate(page.images, start=1):
                    try:
                        # pdfplumberの画像オブジェクトから直接画像データを取得する試み
                        # x0, y0, x1, y1 = img_obj['x0'], img_obj['top'], img_obj['x1'], img_obj['bottom']
                        # cropped_image = page.crop((x0, y0, x1, y1)).to_image(resolution=150) 
                        # to_image() はPillowImageオブジェクトを返す
                        
                        # PillowImageオブジェクトから画像データを取得
                        # img_data = cropped_image.original # Pillow Image object
                        
                        # pdfplumber 0.10.0 以降では page.images は画像のメタデータのみを含むことがある。
                        # 画像そのものを抽出するには page.extract_images() を使う方が良い場合がある。
                        # ここでは、page.images の各要素が直接画像データを持つと仮定せず、
                        # page.crop().to_image() で Pillow Image を取得し、それを保存する。
                        
                        # ページ全体から画像として抽出できるものを試す (より堅牢な方法)
                        # to_image() はページ全体の画像。img_objは画像領域のメタデータ。
                        # img_obj を使ってページから画像を切り出す
                        
                        x0, top, x1, bottom = img_obj['x0'], img_obj['top'], img_obj['x1'], img_obj['bottom']
                        # バウンディングボックスがページの範囲内にあることを確認
                        if not (0 <= x0 < x1 <= page.width and 0 <= top < bottom <= page.height):
                            logger.warning(f"Page {page_num}, Image {idx}: Invalid bbox { (x0, top, x1, bottom) } for page size { (page.width, page.height) }. Skipping.")
                            continue

                        im = page.crop((x0, top, x1, bottom)).to_image(resolution=150) # 解像度を調整可能

                        buf = BytesIO()
                        im.original.save(buf, format="PNG") # PillowのImageオブジェクトのsaveメソッド
                        data_uri = f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"
                        
                        figures.append({
                            'page': page_num,
                            'index': idx, # ページ内の画像インデックス
                            'data_uri': data_uri,
                            'bbox': (x0, top, x1, bottom) # デバッグ用に座標情報も追加
                        })
                        logger.debug(f"Extracted figure: Page {page_num}, Index {idx}")
                    except Exception as e_img:
                        logger.warning(f"Could not process image {idx} on page {page_num} from {pdf_path}: {e_img}", exc_info=True)
                        continue # 個々の画像の処理エラーはスキップ
        logger.info(f"Finished extracting figures from {pdf_path}. Found {len(figures)} figures.")
        return figures
    except Exception as e_pdf:
        logger.error(f"Failed to open or process PDF for figures {pdf_path}: {e_pdf}", exc_info=True)
        return []

def extract_tables_from_pdf(pdf_path: str) -> List[Dict]:
    """
    PDF から表を抽出し 2次元リスト形式で返却する。
    エラー発生時はログに出力し、空のリストを返す。
    """
    tables = []
    if not pdf_path:
        logger.warning("extract_tables_from_pdf: pdf_path is None or empty.")
        return tables

    try:
        logger.info(f"Processing PDF for tables: {pdf_path}")
        # tabula-py は Java 依存。コンテナにJREが必要。
        # lattice=True は罫線のある表に強い。stream=True は罫線がない表に試す。
        dfs = tabula.read_pdf(pdf_path, pages='all', lattice=True, stream=False, silent=True)
        
        if dfs is None or not isinstance(dfs, list) or not dfs: # tabulaが何も返さないか、空リストの場合
            logger.info(f"No tables found by tabula-py in {pdf_path}.")
            return []

        logger.info(f"tabula-py found {len(dfs)} potential dataframes in {pdf_path}.")
        
        processed_tables_count = 0
        for i, df in enumerate(dfs, start=1):
            if df.empty:
                logger.debug(f"DataFrame {i} from {pdf_path} is empty, skipping.")
                continue
            
            # 全ての列がNaNまたは空文字列である行を削除 (より意味のあるデータのみ残す)
            # df = df.dropna(axis=0, how='all', subset=df.columns[df.dtypes != 'object']) # 全て数値列の場合を考慮
            df = df.dropna(axis=0, how='all') # 全ての列がNaNなら行削除
            if df.empty: # dropna で空になった場合
                logger.debug(f"DataFrame {i} from {pdf_path} became empty after dropna, skipping.")
                continue

            data = df.fillna('').values.tolist() # NaNを空文字列に置換
            
            # 実質的なデータがあるか再チェック（全て空文字列のリストではないか）
            if not any(any(str(cell).strip() for cell in row) for row in data):
                logger.debug(f"Table {i} from {pdf_path} contains no actual data after processing, skipping.")
                continue

            tables.append({
                'table_id': processed_tables_count + 1, # 有効なテーブルのみカウント
                'data': data,
                'page': df.iloc[0,0] if hasattr(df.iloc[0,0], 'page') else "Unknown" # tabula-pyがページ情報を提供する場合がある
            })
            processed_tables_count += 1
            logger.debug(f"Extracted table: ID {processed_tables_count} from {pdf_path}")
        
        logger.info(f"Finished extracting tables from {pdf_path}. Found {len(tables)} valid tables.")
        return tables
    except Exception as e:
        logger.error(f"Failed to read or process PDF for tables {pdf_path}: {e}", exc_info=True)
        # tabula-py が Java を見つけられない場合のエラーはここで捕捉される
        return []
