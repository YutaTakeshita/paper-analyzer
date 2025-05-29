"use client"

import { useState, useEffect } from 'react'
import axios from 'axios'
import styles from './page.module.css'

const logger = console; 

export default function Home() {
  const [file, setFile] = useState(null);
  const [status, setStatus] = useState(null); 
  const [error, setError] = useState(null);

  const [meta, setMeta] = useState(null);
  const [sections, setSections] = useState(null);
  const [references, setReferences] = useState(null);
  const [figuresData, setFiguresData] = useState([]); 
  const [tablesData, setTablesData] = useState([]);   

  const [sectionNames, setSectionNames] = useState([]); // 初期値を空配列に
  const [summaries, setSummaries] = useState({});
  const [loadingSummaries, setLoadingSummaries] = useState({});
  const [audioUrls, setAudioUrls] = useState({});
  const [loadingAudio, setLoadingAudio] = useState({});
  const [expanded, setExpanded] = useState({});
  const [showBackButton, setShowBackButton] = useState(false);

  useEffect(() => {
    logger.log("BACKEND_URL:", process.env.NEXT_PUBLIC_BACKEND_URL);
  }, []);

  // 戻るボタンの表示ロジック (Canvasの内容に置き換え)
  useEffect(() => {
    const handleHashChange = () => { 
      if (window.location.hash && 
          (window.location.hash.startsWith('#b') || 
           sections?.some(s => s.head && `#${encodeURIComponent(s.head)}` === window.location.hash) || 
           window.location.hash === '#references_list_title')) {
        setShowBackButton(true);
      } else {
        setShowBackButton(false); 
      }
    };

    handleHashChange(); 
    window.addEventListener('hashchange', handleHashChange);
    
    return () => {
      window.removeEventListener('hashchange', handleHashChange);
    };
  }, [sections]); 

  // sectionsが更新されたらsectionNamesも更新
  useEffect(() => {
    if (sections) {
      const names = sections.map(sec => sec.head).filter(Boolean);
      // アブストラクトをセクションとして表示する場合、その見出しも目次に含めるか検討
      // 今回はmeta.abstractを別途表示するので、sectionNamesはそのまま
      setSectionNames(names);
    } else {
      setSectionNames([]);
    }
  }, [sections]);


  const goBack = () => {
    setShowBackButton(false);
    window.history.back();
  };

  const resetState = () => {
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.value = ""; 
    }
    setFile(null); 
    setStatus(null);
    setError(null);
    setMeta(null);
    setSections(null);
    setReferences(null);
    setFiguresData([]);
    setTablesData([]);
    setSummaries({});
    setLoadingSummaries({});
    setAudioUrls({});
    setLoadingAudio({});
    setExpanded({});
  };

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) {
      setError('PDFファイルを選択してください');
      return;
    }
    resetState(); 
    setStatus('uploading');

    const form = new FormData();
    form.append('file', file);

    try {
      const endpoint = `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/parse`; 
      logger.log(`Uploading file and parsing with GROBID via: ${endpoint}`);
      
      const res = await axios.post(endpoint, form, {
        timeout: 600000 
      }); 
      
      logger.info('Full result data fetched from backend:', res.data);
      const resultData = res.data;

      setMeta(resultData.meta || null);
      setReferences(resultData.references || null);
      setFiguresData(resultData.figures || []);
      setTablesData(resultData.tables || []);

      if (resultData.sections && Array.isArray(resultData.sections)) {
        const processedSections = resultData.sections.map(sec => {
          return { 
            head: sec.head || "無題のセクション", 
            text: (sec.text || ""), // 空文字列をデフォルトに
            figures: sec.figures || [] 
          };
        });
        setSections(processedSections);
        const initialExpandedState = {};
        processedSections.forEach(sec => {
            if (sec.head) initialExpandedState[sec.head] = false; 
        });
        setExpanded(initialExpandedState);
      } else {
        setError('解析結果のセクション形式が正しくありません。');
        logger.error('Sections data is not an array or is missing:', resultData);
        setSections(null);
      }
      setStatus('done');

    } catch (err) {
      logger.error('Upload or processing failed:', err);
      if (err.response) {
        setError(`処理失敗: ${err.response.data.detail || err.response.statusText} (Status: ${err.response.status})`);
      } else if (err.request) {
        setError('処理失敗: バックエンドサーバーからの応答がありません。ネットワークとサーバーの状態を確認してください。');
      } else {
        setError(`処理失敗: ${err.message}`);
      }
      setStatus('failed');
    }
  }

  async function handleSummarize(sectionName, sectionHtmlText) {
    logger.log(`Requesting summary for: ${sectionName}`);
    setLoadingSummaries(prev => ({ ...prev, [sectionName]: true }));
    setError(null); 
    try {
      const plainText = (sectionHtmlText || "").replace(/<[^>]+>/g, '');
      if (!plainText.trim()) {
        setSummaries(prev => ({ ...prev, [sectionName]: "要約するテキストがありません。" }));
        setLoadingSummaries(prev => ({ ...prev, [sectionName]: false }));
        return;
      }
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/summarize`, 
        { 
          text: plainText,
          max_tokens: 1000
        }
      );
      setSummaries(prev => ({ ...prev, [sectionName]: response.data.summary }));
    } catch (err) {
      logger.error(`Error summarizing ${sectionName}:`, err);
      let errorMsg = "要約の取得に失敗しました。";
      if (err.response) {
        errorMsg += ` (サーバーエラー: ${err.response.data.detail || err.response.statusText})`;
      } else if (err.request) {
        errorMsg += " (サーバーからの応答がありません)";
      } else {
        errorMsg += ` (${err.message})`;
      }
      setSummaries(prev => ({ ...prev, [sectionName]: errorMsg }));
    } finally {
      setLoadingSummaries(prev => ({ ...prev, [sectionName]: false }));
    }
  }

  async function handleTTS(sectionName, textToSpeakHtml) {
    logger.log(`Requesting TTS for: ${sectionName}`);
    setLoadingAudio(prev => ({ ...prev, [sectionName]: true }));
    setError(null);
    setAudioUrls(prev => ({ ...prev, [sectionName]: null })); 

    try {
      const plainText = (textToSpeakHtml || "").replace(/<[^>]+>/g, '');
      if (!plainText.trim()) {
        logger.warn(`No text to speak for section: ${sectionName}`);
        setLoadingAudio(prev => ({ ...prev, [sectionName]: false }));
        return;
      }
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/tts`, 
        { text: plainText }, 
        { responseType: 'blob' } 
      );
      const url = URL.createObjectURL(response.data);
      setAudioUrls(prev => ({ ...prev, [sectionName]: url }));
    } catch (err) {
      logger.error(`Error generating TTS for ${sectionName}:`, err);
      let errorMsg = "音声の生成に失敗しました。";
      if (err.response) {
        try {
          let detail = 'サーバーエラー詳細不明';
          if (err.response.data && typeof err.response.data.text === 'function') {
            const errorJsonText = await err.response.data.text();
            try {
                const errorJson = JSON.parse(errorJsonText);
                detail = errorJson.detail || err.response.statusText;
            } catch (parseErr) {
                detail = errorJsonText || err.response.statusText;
            }
          } else if (err.response.data && err.response.data.detail) {
            detail = err.response.data.detail;
          } else {
            detail = err.response.statusText;
          }
          errorMsg += `: ${detail}`;
        } catch (e) {
          errorMsg += `: ${err.response.statusText || 'サーバーエラー詳細取得失敗'}`;
        }
      } else if (err.request) {
        errorMsg += " (サーバーからの応答がありません)";
      } else {
        errorMsg += ` (${err.message})`;
      }
      setError(prevError => prevError ? `${prevError}\n「${sectionName}」の音声生成エラー: ${errorMsg}` : `「${sectionName}」の音声生成エラー: ${errorMsg}`);
    } finally {
      setLoadingAudio(prev => ({ ...prev, [sectionName]: false }));
    }
  }

  const getPlainTextPreview = (htmlString, maxLength = 500) => {
    if (typeof window === 'undefined' || !htmlString) {
        return { previewHtml: "", isLong: false, fullTextHtml: htmlString || "" };
    }
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlString;
    const plainText = tempDiv.textContent || tempDiv.innerText || "";
    
    if (plainText.length > maxLength) {
      // プレビューはHTMLのまま、最初の部分を表示 (より安全な方法を検討する余地あり)
      // 例えば、最初の数個の<p>タグだけを取り出すなど。
      // ここでは単純に、isLongフラグだけを正しく設定し、表示はhtmlTextのままにする。
      // プレビュー表示は、expanded[name]がfalseの時にtextPreviewHtmlを使う。
      // textPreviewHtmlには、HTML構造を壊さない形で短縮したHTMLを入れるのが理想。
      // 簡単のため、ここではプレーンテキストのプレビューを返すように戻し、
      // 表示側でHTMLかプレーンテキストかを選択する。
      return { previewText: plainText.slice(0, maxLength) + '…', isLong: true, fullTextHtml: htmlString };
    }
    return { previewText: htmlString, isLong: false, fullTextHtml: htmlString }; // 短い場合はHTMLのまま
  };

  return (
    <main className={styles.main}>
      <div className={styles.header}>
        <h1>Paper Analyzer</h1>
        <p className={styles.description}>
          論文のPDFをアップロードすると、見出しを抽出して各セクションに分割して表示します。<br/>
          各セクション毎に要約したり、音声で読み上げたりすることができます。
        </p>
      </div>

      <form onSubmit={handleUpload} className={styles.form}>
        <input
          type="file"
          id="fileInput"
          accept="application/pdf"
          onChange={e => setFile(e.target.files[0])}
          disabled={status === 'uploading'}
        />
        <button type="submit" disabled={!file || status === 'uploading'}>
          {(status === 'uploading') ? '処理中...' : 'Upload & Parse'}
        </button>
      </form>

      {status && status !== 'done' && status !== 'failed' && status !== null && <p className={styles.statusMessage}>ステータス: {status}</p>}
      {error && <p className={styles.error}>{error}</p>}

      {status === 'done' && meta && (
        <section className={`${styles.section} ${styles.metaSection}`}>
          {meta.title && <h2>{meta.title}</h2>}
          <p><strong>Author:</strong> {meta.authors && meta.authors.length > 0 ? meta.authors.join(', ') : 'N/A'}</p>
          <p><strong>Journal:</strong> {meta.journal || 'N/A'}</p>
          <p><strong>Published Date:</strong> {meta.issued || 'N/A'}</p>
          
          {/* アブストラクト本文とAI要約を最初から表示 */}
          {meta.abstract && (
            <div className={styles.abstractContainer}>
              <div className={styles.abstractOriginal}>
                <h3>abstract</h3>
                {/* アブストラクト本文は複数段落の可能性があるので、改行を<br>に変換 */}
                <div dangerouslySetInnerHTML={{ __html: meta.abstract.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>') }} />
              </div>
              {meta.abstract_summary && (
                <div className={styles.abstractSummary}>
                  <h3>要約</h3>
                  <div dangerouslySetInnerHTML={{ __html: meta.abstract_summary.replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>') }} />
                </div>
              )}
            </div>
          )}
        </section>
      )}
      
      {status === 'done' && sectionNames.length > 0 && (
        <details className={styles.toc} open>
          <summary>目次（全{sectionNames.length}セクション）</summary>
          <ul>
            {sectionNames.map(name => (
              name && <li key={name}><a href={`#${encodeURIComponent(name)}`}>{name}</a></li>
            ))}
            {references && references.length > 0 && (
              <li><a href="#references_list_title">References</a></li>
            )}
          </ul>
        </details>
      )}

      {status === 'done' && sections && (
        <div className={styles.results}>
          {sections.map(sec => {
            const name = sec.head;
            const htmlText = sec.text; 
            const plainTextForCheck = (htmlText || "").replace(/<[^>]+>/g, '').trim();
            const { previewText, isLong: isTextLong } = getPlainTextPreview(htmlText, 500); // プレビューはプレーンテキストベースで判断
            
            const isReferenceSection =
              typeof name === 'string' && (name.toLowerCase().includes('reference') || name.toLowerCase().includes('参考文献'));

            // セクション名があり、かつ (本文があるか、またはセクション内図があるか、または参考文献セクション) の場合に表示
            if (name && (plainTextForCheck || (sec.figures && sec.figures.length > 0) || isReferenceSection )) {
              // OK
            } else if (!name && plainTextForCheck) { // セクション名はないが本文はある場合（稀だが）
              // OK
            }
            else { // 上記以外（実質的に空のセクション）は表示しない
                return null;
            }

            return (
              <section key={name || `section-${Math.random()}`} id={name ? encodeURIComponent(name) : undefined} className={styles.section}>
                {name && <h2>{name}</h2>}
                <div
                  className={styles.sectionText}
                  dangerouslySetInnerHTML={{ 
                    __html: isReferenceSection || !isTextLong // 参考文献または短いセクションは常に全文(HTML)表示
                              ? htmlText 
                              : (expanded[name] ? htmlText : previewText) // プレビューはプレーンテキストの可能性あり注意
                  }} 
                />
                {/* セクション内の図キャプション表示 (TEI XML由来) */}
                {sec.figures && sec.figures.length > 0 && (
                  <div className={styles.figuresInTei}>
                    <h4>このセクションの図 (論文内キャプションより):</h4>
                    {sec.figures
                      .filter(fig => fig.caption && fig.caption.trim() !== "") 
                      .map((fig, index) => (
                      <figure key={fig.id || `sec-fig-${name}-${index}`} className={styles.figureItemTei}>
                        <figcaption>図 {fig.id || index + 1}: {fig.caption}</figcaption>
                      </figure>
                    ))}
                  </div>
                )}
                
                {!isReferenceSection && isTextLong && plainTextForCheck && (
                  <button
                    className={styles.readMoreButton}
                    onClick={() =>
                      setExpanded(prev => ({ ...prev, [name]: !prev[name] }))
                    }
                  >
                    {expanded[name] ? '▲ 閉じる' : '▼ 続きを読む'}
                  </button>
                )}

                {!isReferenceSection && plainTextForCheck && ( // 本文がある場合のみアクションボタン表示
                  <div className={styles.actionsContainer}>
                    <button
                      className={styles.summaryButton}
                      onClick={() => handleSummarize(name, htmlText)} 
                      disabled={loadingSummaries[name]}
                    >
                      {loadingSummaries[name] ? '要約中...' : 'このセクションを要約'}
                    </button>
                    {summaries[name] && (
                      <p className={styles.summaryText}>{summaries[name].replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br/>')}</p>
                    )}
                    <div className={styles.ttsContainer}>
                      <button
                        className={styles.ttsButton}
                        onClick={() =>
                          handleTTS(name, summaries[name] || htmlText) 
                        }
                        disabled={
                          loadingAudio[name] || !(summaries[name] || plainTextForCheck)
                        }
                      >
                        {loadingAudio[name] ? '音声生成中...' : 'このセクションを読み上げ ▶'}
                      </button>
                      {audioUrls[name] && (
                        <audio controls src={audioUrls[name]} onEnded={() => {
                          URL.revokeObjectURL(audioUrls[name]);
                          setAudioUrls(prev => ({...prev, [name]: null})); 
                        }}/>
                      )}
                    </div>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {/* PDF全体から抽出された図 */}
      {status === 'done' && figuresData && figuresData.length > 0 && (
        <section className={`${styles.section} ${styles.extractedMediaSection}`}>
          <h2>抽出された図 (PDF全体より)</h2>
          <div className={styles.figuresGrid}>
            {figuresData
              .filter(fig => fig.data_uri && fig.data_uri.length > 'data:image/png;base64,'.length + 100)
              .map((fig, index) => (
              <figure key={fig.id || fig.index || `global-fig-${index}`} className={styles.figureItem}>
                {fig.data_uri && <img src={fig.data_uri} alt={`Figure page ${fig.page}, index ${fig.index}`} />}
                <figcaption>図 (ページ: {fig.page}, インデックス: {fig.index})</figcaption>
              </figure>
            ))}
            {figuresData.filter(fig => fig.data_uri && fig.data_uri.length > 'data:image/png;base64,'.length + 100).length === 0 && (
              <p className={styles.empty}>表示できる図は見つかりませんでした。</p>
            )}
          </div>
        </section>
      )}

      {/* PDF全体から抽出された表 */}
      {status === 'done' && tablesData && tablesData.length > 0 && (
        <section className={`${styles.section} ${styles.extractedMediaSection}`}>
          <h2>抽出された表 (PDF全体より)</h2>
          {tablesData
            .filter(table => table.data && Array.isArray(table.data) && table.data.length > 0 && table.data.some(row => Array.isArray(row) && row.length > 0 && row.some(cell => cell && cell.toString().trim() !== "")))
            .map((table, tableIndex) => (
            <div key={table.table_id || `global-table-${tableIndex}`} className={styles.tableContainer}>
              <h4>表 {table.table_id || tableIndex + 1}</h4>
              <div className={styles.tableScrollWrapper}>
                <table>
                  <tbody>
                    {table.data.map((row, rowIndex) => (
                      <tr key={rowIndex}>
                        {row.map((cell, cellIndex) => (
                          <td key={cellIndex}>{cell}</td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
          {tablesData.filter(table => table.data && Array.isArray(table.data) && table.data.length > 0 && table.data.some(row => Array.isArray(row) && row.length > 0 && row.some(cell => cell && cell.toString().trim() !== ""))).length === 0 && (
            <p className={styles.empty}>表示できる表は見つかりませんでした。</p>
          )}
        </section>
      )}

      {/* 参考文献セクション */}
      {status === 'done' && references && references.length > 0 && (
        <section className={`${styles.section} ${styles.referencesSection}`} id="references_list_title">
          <h2>References</h2>
          <ol className={styles.referencesList}>
            {/* ★ここからが page_js_add_search_links の内容 */}
            {references.map((ref, index) => {
              const refText = ref.text; // バックエンドで整形済みのテキスト
              const searchQuery = ref.search_query || refText; // バックエンドから 'search_query' が来ればそれを使う

              // Google Scholar 検索URL
              const googleScholarUrl = `https://scholar.google.com/scholar?q=${encodeURIComponent(searchQuery)}`;
              // PubMed 検索URL (より詳細な検索フィールドを指定することも可能)
              const pubmedUrl = `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(searchQuery)}`;

              return (
                <li key={ref.id || `ref-item-${index}`} 
                    id={ref.id}> 
                  {refText}
                  <div className={styles.referenceSearchLinks}>
                    <a href={googleScholarUrl} target="_blank" rel="noopener noreferrer">Google Scholar</a>
                    {' | '}
                    <a href={pubmedUrl} target="_blank" rel="noopener noreferrer">PubMed</a>
                    {/* 他の検索エンジンへのリンクも追加可能 */}
                  </div>
                </li>
              );
            })}
            {/* ★ここまでが page_js_add_search_links の内容 */}
          </ol>
        </section>
      )}

      {showBackButton && (
        <button className={styles.backButton} onClick={goBack}>
          ▲ もどる
        </button>
      )}
    </main>
  );
}
