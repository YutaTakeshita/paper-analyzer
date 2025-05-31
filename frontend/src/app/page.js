"use client"

import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Image from 'next/image';
import styles from './page.module.css';

const logger = console;
const POLLING_INTERVAL = 3000; // 3秒ごとにステータスを確認

export default function Home() {
  const [file, setFile] = useState(null);
  const [originalFileName, setOriginalFileName] = useState("");
  const [status, setStatus] = useState(null); // 'file_selected', 'uploading', 'queued', 'processing', 'done', 'failed'
  const [error, setError] = useState(null);

  const [meta, setMeta] = useState(null);
  const [sections, setSections] = useState(null); // { id, head, text, figures, level, subsections } の配列
  const [references, setReferences] = useState(null); // { id, text, search_query } の配列
  const [figuresData, setFiguresData] = useState([]);
  const [tablesData, setTablesData] = useState([]);

  const [sectionNames, setSectionNames] = useState([]); // 目次表示用 (トップレベルのセクション名)
  const [summaries, setSummaries] = useState({}); // { [sectionId]: "summary text" }
  const [loadingSummaries, setLoadingSummaries] = useState({}); // { [sectionId]: boolean }

  const [audioUrls, setAudioUrls] = useState({}); // { [sectionId]: url }
  const [loadingAudio, setLoadingAudio] = useState({}); // { [sectionId]: boolean }

  const [expanded, setExpanded] = useState({}); // { [sectionId]: boolean } セクション本文の展開状態
  const [showBackButton, setShowBackButton] = useState(false);

  // Notion連携用state
  const [notionStatus, setNotionStatus] = useState(null); // null, 'saving', 'saved', 'failed'
  const [notionError, setNotionError] = useState(null);
  const [notionPageUrl, setNotionPageUrl] = useState(null);
  const [userTags, setUserTags] = useState([]);
  const [currentTagInput, setCurrentTagInput] = useState("");
  const [userRating, setUserRating] = useState(null); // "☆", "☆☆", "☆☆☆" または null
  const [userMemo, setUserMemo] = useState("");

  const [parsingJobId, setParsingJobId] = useState(null);
  const [parsingStatusMessage, setParsingStatusMessage] = useState("");

  const NOTION_TARGET_URL = "https://www.notion.so/1f007614621080fd839dd0410d9ff901?v=1f0076146210819ba94b000ce6a933c0";
  const pollingIntervalRef = useRef(null);

  useEffect(() => {
    logger.log("BACKEND_URL:", process.env.NEXT_PUBLIC_BACKEND_URL);
  }, []);

  useEffect(() => {
    const onHashChange = () => {
      const hash = window.location.hash;
      if (hash) {
        const isCitationLink = /^#ref-.+$/.test(hash);
        const isSectionLink = sections && sections.some(s => s.head && `#${encodeURIComponent(s.head)}` === hash);
        const isReferencesTitleLink = hash === '#references_list_title';
        const isNotionSaveAreaLink = hash === '#notion-save-area';
        if (isCitationLink || isSectionLink || isReferencesTitleLink || isNotionSaveAreaLink) {
          setShowBackButton(true);
        } else {
          setShowBackButton(false);
        }
      } else {
        setShowBackButton(false);
      }
    };
    window.addEventListener('hashchange', onHashChange);
    if (window.location.hash) onHashChange();
    return () => window.removeEventListener('hashchange', onHashChange);
  }, [sections, references]); // sections, references が変更されたときに再評価

  useEffect(() => {
    if (sections) {
      const names = sections.filter(sec => sec.level === 1 && sec.head).map(sec => sec.head);
      setSectionNames(names);
    } else {
      setSectionNames([]);
    }
  }, [sections]);

  // ポーリング処理のためのuseEffect
  useEffect(() => {
    const fetchJobStatus = async () => {
      if (!parsingJobId) return;

      try {
        logger.log(`Polling status for job ID: ${parsingJobId}`);
        const res = await axios.get(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/parse_status/${parsingJobId}`);
        const jobData = res.data;

        setParsingStatusMessage(`解析処理: ${jobData.status} (${jobData.filename || originalFileName})`);
        
        if (status !== jobData.status) {
            setStatus(jobData.status);
        }

        if (jobData.status === 'completed') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          setParsingJobId(null);
          setParsingStatusMessage("解析が完了しました。");

          // ★★★ ここで jobData.result の内容をログ出力して確認 ★★★
          console.log("Job Result from Backend:", JSON.stringify(jobData.result, null, 2));

          setMeta(jobData.result?.meta || null);
          setReferences(jobData.result?.references || null);
          setFiguresData(jobData.result?.figures || []);
          setTablesData(jobData.result?.tables || []);

          if (jobData.result?.sections && Array.isArray(jobData.result.sections)) {
            const processedSections = jobData.result.sections.map((sec, index) => ({
              id: `section-${index}-${(sec.head || 'untitled').replace(/\s+/g, '-')}`,
              head: (typeof sec.head === 'string' && sec.head.trim() !== "") ? sec.head.trim() : null,
              text: (sec.text || ""),
              figures: sec.figures || [],
              level: sec.level || 1,
              subsections: sec.subsections || []
            }));
            setSections(processedSections);
            const initialExpandedState = {};
            processedSections.forEach(sec => { initialExpandedState[sec.id] = false; });
            setExpanded(initialExpandedState);
          } else {
            setError('解析結果のセクション形式が正しくありません。');
            setSections(null);
          }
          setStatus('done');
        } else if (jobData.status === 'failed') {
          if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
          setParsingJobId(null);
          setError(`解析処理に失敗しました: ${jobData.error || '不明なエラー'}`);
          setParsingStatusMessage(`解析処理に失敗しました。`);
          setStatus('failed');
        } else if (jobData.status === 'queued' || jobData.status === 'processing') {
          // ポーリング継続
        }

      } catch (err) {
        logger.error("Error during polling:", err);
        if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
        setParsingJobId(null);
        setError("処理状況の確認中にエラーが発生しました。");
        setParsingStatusMessage("処理状況の確認に失敗しました。");
        setStatus('failed');
      }
    };

    if (parsingJobId && (status === 'queued' || status === 'processing')) {
      fetchJobStatus(); // 最初の呼び出し
      pollingIntervalRef.current = setInterval(fetchJobStatus, POLLING_INTERVAL);
    } else {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
        pollingIntervalRef.current = null;
      }
    }

    return () => {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
    };
  }, [parsingJobId, status, originalFileName]); // 依存配列を修正

  const goBack = () => { setShowBackButton(false); window.history.back(); };

  const resetState = (keepFile = false) => {
    if (!keepFile) {
        const fileInput = document.querySelector('input[type="file"]');
        if (fileInput) fileInput.value = "";
        setFile(null); setOriginalFileName("");
    }
    setStatus(null); setError(null); setMeta(null); setSections(null);
    setReferences(null); setFiguresData([]); setTablesData([]);
    setSummaries({}); setLoadingSummaries({}); setAudioUrls({}); setLoadingAudio({});
    setExpanded({}); setNotionStatus(null); setNotionError(null); setNotionPageUrl(null);
    setUserTags([]); setCurrentTagInput(""); setUserRating(null); setUserMemo("");
    setParsingJobId(null); setParsingStatusMessage("");
    if (pollingIntervalRef.current) clearInterval(pollingIntervalRef.current);
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
        setFile(selectedFile); setOriginalFileName(selectedFile.name);
        resetState(true); setStatus("file_selected"); setError(null);
    }
  };

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) { setError('PDFファイルを選択してください'); return; }
    resetState(true);
    setStatus('uploading');
    setParsingStatusMessage("PDFをアップロードし、解析処理を開始しています...");
    setError(null);

    const form = new FormData();
    form.append('file', file);

    try {
      const endpoint = `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/parse_async`;
      const res = await axios.post(endpoint, form);
      if (res.data && res.data.job_id) {
        setParsingJobId(res.data.job_id);
        setStatus(res.data.status || 'queued'); 
        setParsingStatusMessage(`解析処理が開始されました (ジョブID: ${res.data.job_id.substring(0,8)})。結果表示までお待ちください...`);
      } else {
        throw new Error("バックエンドからジョブIDが返されませんでした。");
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || '非同期処理の開始に失敗しました。');
      setStatus('failed');
      setParsingStatusMessage("処理の開始に失敗しました。");
      setParsingJobId(null);
    }
  }

  async function handleSummarize(sectionId, sectionHtmlText) {
    if (!sectionId) return;
    setLoadingSummaries(prev => ({ ...prev, [sectionId]: true }));
    setError(null);
    try {
      const plainText = (sectionHtmlText || "").replace(/<[^>]+>/g, '');
      if (!plainText.trim()) {
        setSummaries(prev => ({ ...prev, [sectionId]: "要約するテキストがありません。" }));
        setLoadingSummaries(prev => ({ ...prev, [sectionId]: false }));
        return;
      }
      const response = await axios.post(`${process.env.NEXT_PUBLIC_BACKEND_URL}/summarize`, { text: plainText, max_tokens: 1000 });
      setSummaries(prev => ({ ...prev, [sectionId]: response.data.summary }));
    } catch (err) {
      setSummaries(prev => ({ ...prev, [sectionId]: `要約失敗: ${err.response?.data?.detail || err.message}` }));
    } finally {
      setLoadingSummaries(prev => ({ ...prev, [sectionId]: false }));
    }
  }

  async function handleTTS(sectionId, textToSpeakHtml) {
    if (!sectionId) return;
    setLoadingAudio(prev => ({ ...prev, [sectionId]: true }));
    setError(null);
    setAudioUrls(prev => ({ ...prev, [sectionId]: null }));
    try {
      const plainText = (textToSpeakHtml || "").replace(/<[^>]+>/g, '');
      if (!plainText.trim()) {
        setLoadingAudio(prev => ({ ...prev, [sectionId]: false }));
        return;
      }
      const response = await axios.post(`${process.env.NEXT_PUBLIC_BACKEND_URL}/tts`, { text: plainText, language: 'ja' }, { responseType: 'blob' });
      const url = URL.createObjectURL(response.data);
      setAudioUrls(prev => ({ ...prev, [sectionId]: url }));
    } catch (err) {
      setError(`音声生成失敗 (ID: ${sectionId}): ${err.response?.data?.detail || err.message}`);
    } finally {
      setLoadingAudio(prev => ({ ...prev, [sectionId]: false }));
    }
  }

  const getPlainTextPreview = (htmlString, maxLength = 500) => {
    if (typeof window === 'undefined' || !htmlString) {
        return { previewText: "", plainTextLength: 0, isLong: false, fullTextHtml: htmlString || "" };
    }
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = htmlString;
    const plainText = tempDiv.textContent || tempDiv.innerText || "";
    if (plainText.length > maxLength) {
      return { previewText: plainText.slice(0, maxLength) + '…', plainTextLength: plainText.length, isLong: true, fullTextHtml: htmlString };
    }
    return { previewText: plainText, plainTextLength: plainText.length, isLong: false, fullTextHtml: htmlString };
  };

  const handleSaveToNotion = async () => {
    if (!meta || !meta.title) {
      setNotionError("Notionに保存するための情報が不足しています（タイトルは必須）。");
      setNotionStatus('failed');
      return;
    }
    setNotionStatus('saving');
    setNotionError(null);
    setNotionPageUrl(null);
    const notionData = {
      title: meta.title,
      authors: meta.authors || [],
      journal: meta.journal || null,
      published_date: meta.issued || null,
      doi: meta.doi || null,
      pdf_filename: originalFileName || null,
      original_abstract: meta.abstract || null,
      tags: userTags,
      rating: userRating,
      memo: userMemo,
    };
    try {
      const response = await axios.post(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/save_to_notion`, notionData);
      if (response.data.success) {
        setNotionStatus('saved');
        setNotionPageUrl(NOTION_TARGET_URL);
      } else {
        throw new Error(response.data.error || "Notionへの保存レスポンスが不正です。");
      }
    } catch (err) {
      const errorDetail = err.response?.data?.detail || err.message || "不明なエラー";
      setNotionError(`Notion保存失敗: ${errorDetail}`);
      setNotionStatus('failed');
    }
  };
  const handleTagInputChange = (e) => setCurrentTagInput(e.target.value);
  const handleTagInputKeyDown = (e) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      const newTag = currentTagInput.trim();
      if (newTag && !userTags.includes(newTag)) setUserTags([...userTags, newTag]);
      setCurrentTagInput("");
    }
  };
  const removeTag = (tagToRemove) => setUserTags(userTags.filter(tag => tag !== tagToRemove));

  const renderSection = (sec, isLastContentSection) => {
    const { id: sectionId, head: name, text: htmlText, figures: sectionFigures, level, subsections } = sec;
    const plainTextContent = (htmlText || "").replace(/<[^>]+>/g, '').trim();
    const hasMeaningfulContent = name || plainTextContent || (sectionFigures && sectionFigures.length > 0) || (subsections && subsections.length > 0);
    if (!hasMeaningfulContent) return null;

    const { previewText, isLong: isTextLong, fullTextHtml } = getPlainTextPreview(htmlText, 500);
    const isExpanded = sectionId ? !!expanded[sectionId] : true;
    const textToRenderHtml = isTextLong && name && !isExpanded ? `<p>${previewText.replace(/\n\n+/g, '</p><p>').replace(/\n/g, '<br />')}</p>` : fullTextHtml;
    const isReferenceSection = typeof name === 'string' && (name.toLowerCase().includes('reference') || name.toLowerCase().includes('参考文献'));
    const sectionStyleClasses = [styles.section];
    if (level > 1) sectionStyleClasses.push(styles.subSection);
    const HeadingTag = `h${Math.min(6, 1 + level)}`;

    return (
      <section key={sectionId} id={name ? encodeURIComponent(name) : undefined} className={sectionStyleClasses.join(' ')}>
        {name && <HeadingTag>{name}</HeadingTag>}
        {(!name && plainTextContent) && <HeadingTag>無題のセクション</HeadingTag>}
        <div className={styles.sectionText} dangerouslySetInnerHTML={{ __html: textToRenderHtml }} />
        {sectionFigures && sectionFigures.length > 0 && (
          <div className={styles.figureItemTeiContainer}>
            <h4>このセクションの図 (論文内キャプションより):</h4>
            {sectionFigures.filter(fig => fig.caption && fig.caption.trim() !== "").map((fig, index) => (
              <figure key={fig.id || `sec-fig-${sectionId}-${index}`} className={styles.figureItemTei}>
                <figcaption>図 {fig.id || index + 1}: {fig.caption}</figcaption>
              </figure>
            ))}
          </div>
        )}
        {!isReferenceSection && isTextLong && name && plainTextContent && (
          <button className={styles.readMoreButton} onClick={() => setExpanded(prev => ({ ...prev, [sectionId]: !prev[sectionId] }))}>
            {isExpanded ? '▲ 閉じる' : '▼ 続きを読む'}
          </button>
        )}
        {!isReferenceSection && plainTextContent && (
          <div className={styles.actionsContainer}>
            <div className={styles.actionGroup}>
              <button className={styles.summaryButton} onClick={() => handleSummarize(sectionId, htmlText)} disabled={loadingSummaries[sectionId]}>
                {loadingSummaries[sectionId] ? '要約中...' : 'このセクションを要約'}
              </button>
              {summaries[sectionId] && (
                <>
                  <div className={styles.summaryText} dangerouslySetInnerHTML={{ __html: summaries[sectionId].split(/\n\s*\n+/).map(para => `<p>${para.trim().replace(/\n/g, '<br />')}</p>`).join('') }} />
                  <div className={styles.ttsContainer}>
                     <button className={styles.ttsButtonSmall} onClick={() => handleTTS(sectionId, summaries[sectionId])} disabled={loadingAudio[sectionId] || !summaries[sectionId]}>
                        {loadingAudio[sectionId] ? '生成中...' : '要約を読み上げ ▶'}
                     </button>
                     {audioUrls[sectionId] && ( <audio controls src={audioUrls[sectionId]} onEnded={() => { URL.revokeObjectURL(audioUrls[sectionId]); setAudioUrls(prev => ({...prev, [sectionId]: null})); }} style={{ marginTop: '8px', width: '100%'}}/> )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
        {isLastContentSection && !isReferenceSection && (
            <div className={styles.sectionFooterActions}> <a href="#notion-save-area" className={styles.actionLinkButton}> ▲ Notion登録セクションへ移動 </a> </div>
        )}
        {subsections && subsections.length > 0 && (
          <div className={styles.subSectionsContainer}> {subsections.map(subSec => renderSection(subSec, false))} </div>
        )}
      </section>
    );
  };

  // Notionリンクボタン表示制御用のセクションリスト (図表・参考文献セクションを除外)
  const contentSectionsForNotionLink = sections ? sections.filter(sec =>
    sec.level === 1 &&
    (sec.head || ((sec.text || "").replace(/<[^>]+>/g, '').trim())) &&
    !(typeof sec.head === 'string' &&
      (sec.head.toLowerCase().includes('reference') ||
       sec.head.toLowerCase().includes('参考文献') ||
       sec.head.toLowerCase().includes('figure') ||
       sec.head.toLowerCase().includes('table') // ★★★ 括弧の対応を修正 ★★★
      ) // ★★★ この閉じ括弧が不足していました ★★★
    )
  ) : [];


  const isParsingInProgress = status === 'uploading' || status === 'queued' || status === 'processing';

  return (
    <main className={styles.main}>
      <div className={styles.header}>
        <div className={styles.titleContainer}>
          <Image src="/PapeLog.png" alt="PapeLog Logo" width={50} height={50} className={styles.logoImage} />
          <h1>PapeLog</h1>
        </div>
        <p className={styles.description}>
          PDF論文をアップロードするだけ！AIがパッと解析して、論文の構造をまるごとキャッチ。<br />
          重要なポイントはAI要約で時短、音声読み上げでスキマ時間も活用！<br />
          「参考になった度」評価、タグ、ひらめいたメモと一緒に読んだ論文をNotionデータベースにしっかり記録＆管理。<br />
          あなたの「読んだ」を価値ある「記録」に。
        </p>
      </div>

      <form onSubmit={handleUpload} className={styles.form}>
        <input type="file" id="fileInput" accept="application/pdf" onChange={handleFileChange} disabled={isParsingInProgress} />
        <button type="submit" disabled={!file || isParsingInProgress}>
          {isParsingInProgress ? (parsingStatusMessage || '処理中...') : 'PDFを解析'}
        </button>
        {originalFileName && <p className={styles.fileName}>選択中のファイル: {originalFileName}</p>}
      </form>

      {(status === 'queued' || status === 'processing') && parsingStatusMessage &&
        <p className={styles.statusMessage}>{parsingStatusMessage}</p>
      }
      {status === 'failed' && error &&
        <p className={styles.error} dangerouslySetInnerHTML={{ __html: error.replace(/\n/g, '<br />') }} />}
      
      {status === 'done' && meta && (
        <>
          <section className={`${styles.section} ${styles.metaSection}`}>
            {meta.title && <h2>{meta.title}</h2>}
            <p><strong>著者:</strong> <span>{meta.authors && meta.authors.length > 0 ? meta.authors.join(', ') : 'N/A'}</span></p>
            <p><strong>ジャーナル:</strong> <span>{meta.journal || 'N/A'}</span></p>
            <p><strong>発行日:</strong> <span>{meta.issued || 'N/A'}</span></p>
            {meta.doi && <p><strong>DOI:</strong> <span>{meta.doi}</span></p>}
            {meta.abstract && (
              <div className={styles.abstractContainer}>
                <div className={styles.abstractOriginal}>
                  <h3>アブストラクト</h3>
                  <div className={styles.sectionText} dangerouslySetInnerHTML={{ __html: meta.abstract.replace(/\n\n+/g, '</p><p>').replace(/\n/g, '<br/>') }} />
                </div>
                {meta.abstract_summary && (
                  <div className={styles.abstractSummary}>
                    <h3>要約</h3>
                    <div className={styles.sectionText} dangerouslySetInnerHTML={{ __html: meta.abstract_summary.split(/\n\s*\n+/).map(para => `<p>${para.trim().replace(/\n/g, '<br />')}</p>`).join('') }} />
                  </div>
                )}
              </div>
            )}
          </section>

          <section id="notion-save-area" className={`${styles.section} ${styles.notionSaveSection}`}>
            <h3>Notionに保存</h3>
            <div className={styles.notionSaveContainer}>
              <div className={styles.inputRow}>
                <div className={styles.tagInputContainer}>
                  <label htmlFor="notionTags">タグ (Enterまたはカンマで追加):</label>
                  <input type="text" id="notionTags" value={currentTagInput} onChange={handleTagInputChange} onKeyDown={handleTagInputKeyDown} placeholder="例: 機械学習, 論文レビュー" className={styles.tagInputField}/>
                  <div className={styles.tagsPreview}>
                    {userTags.map(tag => (
                      <span key={tag} className={styles.tagItem}>
                        {tag}
                        <button onClick={() => removeTag(tag)} className={styles.removeTagButton} title={`タグ "${tag}" を削除`}>×</button>
                      </span>
                    ))}
                  </div>
                </div>
                <div className={styles.memoInputContainer}>
                  <label htmlFor="notionMemo">メモ (任意):</label>
                  <textarea id="notionMemo" value={userMemo} onChange={(e) => setUserMemo(e.target.value)} placeholder="この論文に関するメモを入力..." rows={3} className={styles.memoTextarea}/>
                </div>
              </div>
              <div className={styles.ratingInputContainer}>
                <label>参考になった度:</label>
                <div className={styles.ratingOptions}>
                  {["☆", "☆☆", "☆☆☆"].map(r => (
                    <label key={r} className={`${styles.ratingLabel} ${userRating === r ? styles.selectedRating : ''}`}>
                      <input type="radio" name="notionRating" value={r} checked={userRating === r} onChange={(e) => setUserRating(e.target.value)} className={styles.ratingRadioInput}/>
                      {r}
                    </label>
                  ))}
                  {userRating && (<button onClick={() => setUserRating(null)} className={styles.clearRatingButton}>評価クリア</button>)}
                </div>
              </div>
              <button onClick={handleSaveToNotion} disabled={notionStatus === 'saving' || !meta || !meta.title || isParsingInProgress} className={styles.notionSaveButton}>
                {notionStatus === 'saving' ? 'Notionに保存中...' : 'この論文をNotionに保存'}
              </button>
              {notionStatus === 'saved' && notionPageUrl && (<p className={styles.notionSuccess}> Notionに保存しました！ <a href={notionPageUrl} target="_blank" rel="noopener noreferrer">ページを開く</a> </p>)}
              {notionStatus === 'failed' && notionError && <p className={styles.error}>{notionError}</p>}
            </div>
          </section>
        </>
      )}

      {status === 'done' && sectionNames.length > 0 && (
        <details className={styles.toc} open>
          <summary>目次（全{sectionNames.length}主要セクション）</summary>
          <ul>
            {sections && sections.filter(sec => sec.level === 1 && sec.head).map(sec => ( <li key={`toc-${sec.id}`}><a href={`#${encodeURIComponent(sec.head)}`}>{sec.head}</a></li> ))}
            {references && references.length > 0 && ( <li key="toc-references"><a href="#references_list_title">参考文献</a></li> )}
          </ul>
        </details>
      )}

      {status === 'done' && sections && sections.length > 0 && (
        <div className={styles.results}>
          {sections.filter(sec => sec.level === 1).map((sec, index) => {
            const isLastContentSec = contentSectionsForNotionLink.length > 0 && sec.id === contentSectionsForNotionLink[contentSectionsForNotionLink.length - 1]?.id;
            return renderSection(sec, isLastContentSec);
          })}
          {sections.filter(sec => sec.level === 1).length === 0 && sections.length > 0 && (
            sections.map((sec, index) => {
                 const isLastContentSec = contentSectionsForNotionLink.length > 0 && sec.id === contentSectionsForNotionLink[contentSectionsForNotionLink.length - 1]?.id;
                 return renderSection(sec, isLastContentSec)
            })
          )}
          {sections.length === 0 && <p className={styles.empty}>表示できるセクションが見つかりませんでした。</p>}
        </div>
      )}

      {status === 'done' && figuresData && figuresData.length > 0 && (
        <section className={`${styles.section} ${styles.extractedMediaSection}`}>
          <h2>抽出された図 (PDF全体より)</h2>
          <div className={styles.figuresGrid}>
            {figuresData
              .filter(fig => fig.data_uri && fig.data_uri.length > 'data:image/png;base64,'.length + 100)
              .map((fig, index) => {
                const uniqueKey = fig.id || `global-fig-p${fig.page || 0}-idx${fig.index !== undefined ? fig.index : index}-${fig.data_uri ? fig.data_uri.slice(-10) : ''}`;
                return (
                  <figure key={uniqueKey} className={styles.figureItem}>
                    {fig.data_uri && <img src={fig.data_uri} alt={`Figure page ${fig.page}, index ${fig.index}`} />}
                    <figcaption>図 (ページ: {fig.page || 'N/A'}, インデックス: {fig.index !== undefined ? fig.index : index + 1})</figcaption>
                  </figure>
                );
              })}
            {figuresData.filter(fig => fig.data_uri && fig.data_uri.length > 'data:image/png;base64,'.length + 100).length === 0 && (
              <p className={styles.empty}>表示できる図は見つかりませんでした。</p>
            )}
          </div>
        </section>
      )}

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
                      <tr key={`table-${tableIndex}-row-${rowIndex}`}>
                        {row.map((cell, cellIndex) => (
                          <td key={`table-${tableIndex}-row-${rowIndex}-cell-${cellIndex}`}>{cell}</td>
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
      
      {status === 'done' && references && references.length > 0 && (
        <section className={`${styles.section} ${styles.referencesSection}`} id="references_list_title">
          <h2>参考文献</h2>
          <ol className={styles.referencesList}>
            {references.map((ref, index) => {
              const refText = ref.text;
              const plainRefTextForSearch = typeof refText === 'string' ? refText.replace(/<[^>]+>/g, '') : '';
              const searchQuery = ref.search_query || plainRefTextForSearch;
              const googleScholarUrl = `https://scholar.google.com/scholar?q=${encodeURIComponent(searchQuery)}`;
              const pubmedUrl = `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(searchQuery)}`;
              const referenceItemId = ref.id ? `ref-${ref.id}` : undefined;
              return (
                <li key={ref.id || `ref-item-${index}`} id={referenceItemId}>
                  <span className={styles.referenceTextContainer} dangerouslySetInnerHTML={{ __html: refText }} />
                  <div className={styles.referenceSearchLinks}>
                    <a href={googleScholarUrl} target="_blank" rel="noopener noreferrer">Google Scholar</a>
                    <a href={pubmedUrl} target="_blank" rel="noopener noreferrer">PubMed</a>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {showBackButton && ( <button className={styles.backButton} onClick={goBack} title="前のセクション/ページに戻る"> ▲ 戻る </button> )}
    </main>
  );
}
