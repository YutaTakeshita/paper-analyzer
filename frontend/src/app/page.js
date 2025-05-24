"use client"

import { useState, useEffect } from 'react'
import axios from 'axios'
import styles from './page.module.css'

const logger = console; // または適切なロガーライブラリ

export default function Home() {
  const [file, setFile] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState(null); // 'uploading', 'processing', 'pending', 'done', 'failed', 'error_polling'
  const [error, setError] = useState(null);

  const [meta, setMeta] = useState(null);
  const [sections, setSections] = useState(null);
  const [references, setReferences] = useState(null);
  const [figuresData, setFiguresData] = useState([]); // PDFから抽出された図
  const [tablesData, setTablesData] = useState([]);   // PDFから抽出された表

  const sectionNames = sections ? sections.map(sec => sec.head) : [];
  const [summaries, setSummaries] = useState({});
  const [loadingSummaries, setLoadingSummaries] = useState({});
  const [audioUrls, setAudioUrls] = useState({});
  const [loadingAudio, setLoadingAudio] = useState({});
  const [expanded, setExpanded] = useState({});
  const [showBackButton, setShowBackButton] = useState(false);

  useEffect(() => {
    logger.log("BACKEND_URL:", process.env.NEXT_PUBLIC_BACKEND_URL);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      if (window.location.hash.startsWith('#ref')) {
        setShowBackButton(true);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [sections]);

  const goBack = () => {
    setShowBackButton(false);
    window.history.back();
  };

  const resetState = () => {
    // file は setFile(null) でリセットされるが、<input type="file"> の表示は別途クリアが必要
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
        fileInput.value = ""; // ファイル選択フィールドをクリア
    }
    setFile(null); // ファイルステートもクリア
    setJobId(null);
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
    resetState(); // 新しいアップロードの前に状態をリセット
    setStatus('uploading');

    const form = new FormData();
    form.append('file', file);

    try {
      logger.log(`Uploading file to: ${process.env.NEXT_PUBLIC_BACKEND_URL}/api/cermine/upload`);
      const res = await axios.post(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/cermine/upload`,
        form
      );
      const { jobId: newJobId } = res.data;
      if (newJobId) {
        setJobId(newJobId);
        setStatus('processing');
        logger.log(`Upload successful, jobId: ${newJobId}`);
      } else {
        setError('ジョブIDの取得に失敗しました。');
        setStatus(null);
        logger.error('Failed to get jobId from upload response:', res.data);
      }
    } catch (err) {
      logger.error('Upload failed:', err);
      if (err.response) {
        setError(`アップロード失敗: ${err.response.data.detail || err.response.statusText} (Status: ${err.response.status})`);
      } else if (err.request) {
        setError('アップロード失敗: バックエンドからの応答がありません。ネットワークを確認してください。');
      } else {
        setError(`アップロード失敗: ${err.message}`);
      }
      setStatus(null);
    }
  }

  useEffect(() => {
    let interval;
    if (jobId && (status === 'processing' || status === 'pending')) { // pending もポーリング対象に含める
      interval = setInterval(async () => {
        try {
          logger.log(`Polling status for jobId: ${jobId}`);
          const res = await axios.get(
            `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/cermine/status?jobId=${jobId}`
          );
          logger.log('Status poll response:', res.data);

          if (res.data.status === 'done') {
            clearInterval(interval);
            setStatus('done');
            logger.info(`Job ${jobId} is done. Fetching result from /api/get-result-json`);
            
            try {
              const resultResponse = await axios.get(
                `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/get-result-json?jobId=${jobId}`
              );
              logger.info('Full result data fetched:', resultResponse.data);

              const resultData = resultResponse.data;
              setMeta(resultData.meta || null);
              setReferences(resultData.references || null);
              setFiguresData(resultData.figures || []);
              setTablesData(resultData.tables || []);

              if (resultData.sections && Array.isArray(resultData.sections)) {
                const linkedSections = resultData.sections.map(sec => {
                  const newHtml = (sec.text || "").replace(
                    /<sup\s+[^>]*class=['"]citation['"][^>]*>\s*(\d+)[^<]*<\/sup>/gi,
                    (_, num) => `<sup class="citation"><a href="#ref${num}">${num}</a></sup>`
                  );
                  return { 
                    head: sec.head || "無題のセクション", 
                    text: newHtml, 
                    figures: sec.figures || [] 
                  };
                });
                setSections(linkedSections);
              } else {
                setError('解析結果のセクション形式が正しくありません。');
                logger.error('Sections data is not an array or is missing:', resultData);
                setSections(null);
              }
            } catch (fetchResultError) {
              logger.error('Error fetching or processing result json:', fetchResultError);
              if (fetchResultError.response) {
                setError(`結果取得エラー(JSON): ${fetchResultError.response.data.detail || fetchResultError.response.statusText} (Status: ${fetchResultError.response.status})`);
              } else if (fetchResultError.request) {
                setError('結果取得エラー(JSON): バックエンドからの応答がありません。');
              } else {
                setError(`結果取得エラー(JSON): ${fetchResultError.message}`);
              }
              setSections(null);
            }
          } else if (res.data.status === 'failed') {
            clearInterval(interval);
            setStatus('failed');
            setError(`ジョブ処理失敗: ${res.data.errorMessage || '不明なエラーがバックエンドで発生しました。'}`);
            logger.error('Job processing failed on backend:', res.data);
          } else if (res.data.status === 'pending' || res.data.status === 'processing') {
            setStatus(res.data.status);
          } else if (res.data.status) {
            logger.warn('Unexpected job status received:', res.data.status);
            setStatus(res.data.status);
          } else {
            logger.error('Invalid status response:', res.data);
            setError('無効なステータスレスポンスを受け取りました。');
            clearInterval(interval);
            setStatus('error_polling');
          }
        } catch (err) {
          logger.error('Error polling status:', err);
          clearInterval(interval);
          if (!error && status !== 'failed' && status !== 'done') { 
            if (err.response) {
              setError(`ステータス取得ポーリングエラー: ${err.response.data.detail || err.response.statusText} (Status: ${err.response.status})`);
            } else if (err.request) {
              setError('ステータス取得ポーリングエラー: バックエンドからの応答がありません。');
            } else {
              setError(`ステータス取得ポーリングエラー: ${err.message}`);
            }
            setStatus('error_polling');
          }
        }
      }, 3000); 
    }
    return () => clearInterval(interval);
  }, [jobId, status, error]);

  async function handleSummarize(sectionName, sectionText) {
    logger.log(`Requesting summary for: ${sectionName}`);
    setLoadingSummaries(prev => ({ ...prev, [sectionName]: true }));
    setError(null); 
    try {
      const plainText = (sectionText || "").replace(/<[^>]+>/g, '');
      if (!plainText.trim()) {
        setSummaries(prev => ({ ...prev, [sectionName]: "要約するテキストがありません。" }));
        setLoadingSummaries(prev => ({ ...prev, [sectionName]: false }));
        return;
      }

      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/summarize`, 
        { 
          text: plainText,
          max_tokens: 300 
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

  async function handleTTS(sectionName, textToSpeak) {
    logger.log(`Requesting TTS for: ${sectionName}`);
    setLoadingAudio(prev => ({ ...prev, [sectionName]: true }));
    setError(null);
    setAudioUrls(prev => ({ ...prev, [sectionName]: null })); // 古いURLをクリア

    try {
      const plainText = (textToSpeak || "").replace(/<[^>]+>/g, '');
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
          const errorJsonText = await err.response.data.text();
          const errorJson = JSON.parse(errorJsonText);
          errorMsg += `: ${errorJson.detail || err.response.statusText || '詳細不明'}`;
        } catch (parseErr) {
          errorMsg += `: ${err.response.statusText || 'サーバーエラー詳細不明'}`;
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
          id="fileInput" // IDを追加してリセットしやすくする
          accept="application/pdf"
          onChange={e => setFile(e.target.files[0])}
          disabled={status === 'processing' || status === 'uploading'}
        />
        <button type="submit" disabled={!file || status === 'processing' || status === 'uploading'}>
          {(status === 'processing' || status === 'uploading') ? '処理中...' : 'Upload & Parse'}
        </button>
      </form>

      {status && status !== 'done' && status !== 'failed' && status !== null && <p className={styles.statusMessage}>ステータス: {status}</p>}
      {error && <p className={styles.error}>{error}</p>}

      {status === 'done' && meta && (
        <section className={`${styles.section} ${styles.metaSection}`}>
          <h2>メタ情報</h2>
          <p><strong>タイトル:</strong> {meta.title || 'N/A'}</p>
          <p><strong>著者:</strong> {meta.authors && meta.authors.length > 0 ? meta.authors.join(', ') : 'N/A'}</p>
          <p><strong>ジャーナル:</strong> {meta.journal || 'N/A'}</p>
          <p><strong>発行日:</strong> {meta.issued || 'N/A'}</p>
        </section>
      )}
      
      {status === 'done' && sectionNames.length > 0 && (
        <details className={styles.toc} open>
          <summary>目次（全{sectionNames.length}セクション）</summary>
          <ul>
            {sectionNames.map(name => (
              <li key={name}>
                <a href={`#${name}`}>{name}</a>
              </li>
            ))}
            {references && references.length > 0 && (
              <li><a href="#references">参考文献</a></li>
            )}
          </ul>
        </details>
      )}

      {status === 'done' && sections && (
        <div className={styles.results}>
          {sections.map(sec => {
            const name = sec.head;
            const text = sec.text; // これはHTML文字列
            const isReferenceSection =
              typeof name === 'string' && (name.toLowerCase().includes('reference') || name.toLowerCase().includes('参考文献'));

            return (
              <section key={name} id={name} className={styles.section}>
                <h2>{name}</h2>
                <div
                  className={styles.sectionText}
                  dangerouslySetInnerHTML={{
                    __html: isReferenceSection
                      ? text
                      : (expanded[name] || (text && text.length <= 200) ? text : (text ? text.slice(0, 200) + '…' : ''))
                  }}
                />
                {sec.figures && sec.figures.length > 0 && (
                  <div className={styles.figures}>
                    <h4>このセクションの図 (TEIより):</h4>
                    {sec.figures.map((fig, index) => (
                      <figure key={fig.id || `sec-fig-${name}-${index}`} className={styles.figureItemTei}>
                        <figcaption>図 {fig.id || index + 1}: {fig.caption || '(キャプション無し)'}</figcaption>
                      </figure>
                    ))}
                  </div>
                )}
                {!isReferenceSection && text && text.length > 200 && (
                  <button
                    className={styles.readMoreButton}
                    onClick={() =>
                      setExpanded(prev => ({ ...prev, [name]: !prev[name] }))
                    }
                  >
                    {expanded[name] ? '▲ 閉じる' : '▼ 続きを読む'}
                  </button>
                )}

                {!isReferenceSection && (
                  <div className={styles.actionsContainer}>
                    <button
                      className={styles.summaryButton}
                      onClick={() => handleSummarize(name, text)}
                      disabled={loadingSummaries[name]}
                    >
                      {loadingSummaries[name] ? '要約中...' : 'このセクションを要約'}
                    </button>
                    {summaries[name] && (
                      <p className={styles.summaryText}>{summaries[name]}</p>
                    )}
                    <div className={styles.ttsContainer}>
                      <button
                        className={styles.ttsButton}
                        onClick={() =>
                          handleTTS(name, summaries[name] || text) 
                        }
                        disabled={
                          loadingAudio[name] || !(summaries[name] || text)
                        }
                      >
                        {loadingAudio[name] ? '音声生成中...' : 'このセクションを読み上げ ▶'}
                      </button>
                      {audioUrls[name] && (
                        <audio controls src={audioUrls[name]} onEnded={() => URL.revokeObjectURL(audioUrls[name])}/>
                      )}
                    </div>
                  </div>
                )}
              </section>
            );
          })}
        </div>
      )}

      {status === 'done' && figuresData && figuresData.length > 0 && (
        <section className={`${styles.section} ${styles.extractedMediaSection}`}>
          <h2>抽出された図 (PDF全体より)</h2>
          <div className={styles.figuresGrid}>
            {figuresData.map((fig, index) => (
              <figure key={fig.id || fig.index || `global-fig-${index}`} className={styles.figureItem}>
                {fig.data_uri && <img src={fig.data_uri} alt={`Figure page ${fig.page}, index ${fig.index}`} />}
                <figcaption>図 (ページ: {fig.page}, インデックス: {fig.index})</figcaption>
              </figure>
            ))}
          </div>
        </section>
      )}

      {status === 'done' && tablesData && tablesData.length > 0 && (
        <section className={`${styles.section} ${styles.extractedMediaSection}`}>
          <h2>抽出された表 (PDF全体より)</h2>
          {tablesData.map((table, tableIndex) => (
            <div key={table.table_id || `global-table-${tableIndex}`} className={styles.tableContainer}>
              <h4>表 {table.table_id || tableIndex + 1}</h4>
              <div className={styles.tableScrollWrapper}>
                <table>
                  <tbody>
                    {table.data && table.data.map((row, rowIndex) => (
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
        </section>
      )}
      
      {status === 'done' && references && references.length > 0 && (
        <section className={`${styles.section} ${styles.referencesSection}`} id="references">
          <h2>参考文献</h2>
          <ol className={styles.referencesList}>
            {references.map(ref => (
              <li key={ref.id || ref.text.slice(0,30)} id={ref.id ? ref.id.replace(/^R/, 'ref') : null}>
                {ref.text}
              </li>
            ))}
          </ol>
        </section>
      )}

      {showBackButton && (
        <button className={styles.backButton} onClick={goBack}>
          ▲ 戻る
        </button>
      )}
    </main>
  );
}