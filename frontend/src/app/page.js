"use client"

import { useState, useEffect } from 'react'
import axios from 'axios'
import styles from './page.module.css'

export default function Home() {
  const [file, setFile] = useState(null)
  const [sections, setSections] = useState(null)
  const [jobId, setJobId] = useState(null)
  const [status, setStatus] = useState(null)
  // 全セクション名を配列化し、目次表示に利用
  const sectionNames = sections ? sections.map(sec => sec.head) : []
  const [error, setError] = useState(null)
  const [summaries, setSummaries] = useState({})
  const [loadingSummaries, setLoadingSummaries] = useState({})
  const [audioUrls, setAudioUrls] = useState({})
  const [loadingAudio, setLoadingAudio] = useState({})
  const [expanded, setExpanded] = useState({})
  const [showBackButton, setShowBackButton] = useState(false);

  // Log backend URL to verify environment variable
  useEffect(() => {
    console.log("BACKEND_URL:", process.env.NEXT_PUBLIC_BACKEND_URL);
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

  // Go back to previous scroll position via browser history, then hide the back button
  const goBack = () => {
    setShowBackButton(false);
    window.history.back();
  };

  async function handleUpload(e) {
    e.preventDefault()
    if (!file) {
      setError('PDFファイルを選択してください')
      return
    }
    setError(null)
    // start a new CERMINE job
    const form = new FormData()
    form.append('file', file)
    try {
      const res = await axios.post(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/cermine/upload`,
        form
      )
      const { jobId } = res.data
      setJobId(jobId)
      setStatus('processing')
      setSections(null)
      setSummaries({})
      setAudioUrls({})
    } catch (err) {
      setError('アップロードに失敗しました')
      console.error(err)
    }
  }

  // CERMINE ジョブの完了を 2 秒間隔でポーリング
  useEffect(() => {
    let interval
    if (jobId) {
      interval = setInterval(async () => {
        try {
          const res = await axios.get(
            `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/cermine/status?jobId=${jobId}`
          )
          if (res.data.status === 'done') {
            clearInterval(interval)
            setStatus('done')
            // ジョブ完了時に downloadUrl から JSON を取得し、セクションを整形
            const rawSections = (await axios.get(res.data.downloadUrl)).data.sections;
            // 引用番号をクリック可能なリンクに加工
            const linkedSections = rawSections.map(sec => {
              const newHtml = sec.text.replace(
                /<sup\s+[^>]*class=['"]citation['"][^>]*>\s*(\d+)[^<]*<\/sup>/gi,
                (_, num) => `<sup class="citation"><a href="#ref${num}">${num}</a></sup>`
              );
              return { head: sec.head, text: newHtml, figures: sec.figures || [] };
            });
            setSections(linkedSections);
            setJobId(null)
          }
        } catch (err) {
          console.error('ステータス取得エラー', err)
          clearInterval(interval)
          setJobId(null)
          setError('処理中にエラーが発生しました')
        }
      }, 2000)
    }
    return () => clearInterval(interval)
  }, [jobId])

  return (
    <main className={styles.main}>
      {status === 'processing' && <p>処理中です…</p>}
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
          accept="application/pdf"
          onChange={e => setFile(e.target.files[0])}
        />
        <button type="submit">Upload &amp; Parse</button>
      </form>

      {status === 'processing' && <div className={styles.spinner}>Loading...</div>}

      {sectionNames.length > 0 && (
        <details className={styles.toc} open>
          <summary>目次（全{sectionNames.length}セクション）</summary>
          <ul>
            {sectionNames.map(name => (
              <li key={name}>
                <a href={`#${name}`}>{name}</a>
              </li>
            ))}
          </ul>
        </details>
      )}

      {error && <p className={styles.error}>{error}</p>}

      {sections && (
        <div className={styles.results}>
          // 取得した各セクションをカード形式で描画
          {sections.map(sec => {
            const name = sec.head;
            const text = sec.text;
            // References セクションかどうか判定
            const isReferenceSection =
              name.toLowerCase().includes('reference') ||
              name.includes('参考文献')

            return (
              <section key={name} id={name} className={styles.section}>
                <h2>{name}</h2>
                <div
                  className={styles.sectionText}
                  dangerouslySetInnerHTML={{
                    __html: isReferenceSection
                      ? text
                      : (expanded[name] ? text : text.slice(0, 200) + '…')
                  }}
                />
                // このセクションに紐づく図表があれば表示
                {sec.figures.length > 0 && (
                  <div className={styles.figures}>
                    <h3>Figures</h3>
                    {sec.figures.map(f => (
                      <figure key={f.id}>
                        {/* If you have data_uri for each figure, use <img src={f.data_uri} /> */}
                        <figcaption>{f.caption}</figcaption>
                      </figure>
                    ))}
                  </div>
                )}
                {!isReferenceSection && (
                  <button
                    className={styles.readMoreButton}
                    onClick={() =>
                      setExpanded(prev => ({ ...prev, [name]: !prev[name] }))
                    }
                  >
                    {expanded[name] ? '▲ 閉じる' : '▼ 続きを読む'}
                  </button>
                )}

                {/* References セクションはここ以降をスキップ */}
                {!isReferenceSection && (
                  <>
                    <button
                      className={styles.summaryButton}
                      onClick={() => handleSummarize(name, text)}
                      disabled={loadingSummaries[name]}
                    >
                      {loadingSummaries[name] ? '要約中...' : '要約'}
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
                        {loadingAudio[name] ? '生成中...' : '音声 ▶'}
                      </button>
                      {audioUrls[name] && (
                        <audio controls src={audioUrls[name]} />
                      )}
                    </div>
                  </>
                )}
              </section>
            )
          })}
        </div>
      )}

      {/* Back to previous position */}
      {showBackButton && (
        <button className={styles.backButton} onClick={goBack}>
          ▲ 戻る
        </button>
      )}
    </main>
  )
}