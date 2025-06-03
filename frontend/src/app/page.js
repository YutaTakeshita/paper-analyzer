"use client"

import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import Image from 'next/image';
import styles from './page.module.css';

const logger = console;
const POLLING_INTERVAL = 3000;
// ★★★ 固定のNotionデータベースURLを定数として定義 ★★★
const FIXED_NOTION_DATABASE_URL = "https://www.notion.so/1f007614621080fd839dd0410d9ff901?v=1f0076146210819ba94b000ce6a933c0";

export default function Home() {
  const [file, setFile] = useState(null);
  const [originalFileName, setOriginalFileName] = useState("");
  const [status, setStatus] = useState(null); 
  const [error, setError] = useState(null);

  const [meta, setMeta] = useState(null);
  const [sections, setSections] = useState(null);
  const [references, setReferences] = useState(null);
  const [figuresData, setFiguresData] = useState([]);
  const [tablesData, setTablesData] = useState([]);
  const [googleDriveUrl, setGoogleDriveUrl] = useState(null);

  const [sectionNames, setSectionNames] = useState([]);
  const [summaries, setSummaries] = useState({});
  const [loadingSummaries, setLoadingSummaries] = useState({});
  const [audioUrls, setAudioUrls] = useState({});
  const [loadingAudio, setLoadingAudio] = useState({});
  const [expanded, setExpanded] = useState({});
  const [showBackButton, setShowBackButton] = useState(false);

  const [notionStatus, setNotionStatus] = useState(null);
  const [notionError, setNotionError] = useState(null);
  const [notionPageUrl, setNotionPageUrl] = useState(null);
  const [userTags, setUserTags] = useState([]);
  const [currentTagInput, setCurrentTagInput] = useState("");
  const [userRating, setUserRating] = useState(null);
  const [userMemo, setUserMemo] = useState("");

  const [enhancedSuggestedTags, setEnhancedSuggestedTags] = useState([]);
  const [loadingSuggestedTags, setLoadingSuggestedTags] = useState(false);

  const [parsingJobId, setParsingJobId] = useState(null);
  const [parsingStatusMessage, setParsingStatusMessage] = useState(""); // メインの進捗・ステータスメッセージ用
  const [detailedParsingMessage, setDetailedParsingMessage] = useState(""); // バックエンドからの詳細な処理ステップメッセージ

  const [isPotentiallyFirstLoad, setIsPotentiallyFirstLoad] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const timerRef = useRef(null);
  const [showInitialLoadMessage, setShowInitialLoadMessage] = useState(false);
  const [showProcessingCompleteMessage, setShowProcessingCompleteMessage] = useState(false);

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
  }, [sections, references]);

  useEffect(() => {
    if (sections) {
      const names = sections.filter(sec => sec.level === 1 && sec.head).map(sec => sec.head);
      setSectionNames(names);
    } else {
      setSectionNames([]);
    }
  }, [sections]);

  useEffect(() => {
    if (parsingJobId && (status === 'queued' || status === 'processing')) {
      if (timerRef.current) clearInterval(timerRef.current);
      setElapsedTime(0); 
      timerRef.current = setInterval(() => {
        setElapsedTime(prev => prev + 1);
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
  }, [parsingJobId, status]);

  useEffect(() => {
    const fetchJobStatus = async () => {
      if (!parsingJobId) return;

      try {
        const res = await axios.get(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/parse_status/${parsingJobId}`);
        const jobData = res.data;
        
        if (jobData.status_detail) {
            setDetailedParsingMessage(jobData.status_detail);
        } else if (jobData.status === 'queued') {
            setDetailedParsingMessage("解析キューに追加されました。");
        } else if (jobData.status === 'processing' && !jobData.status_detail) {
            setDetailedParsingMessage("解析処理を実行中です...");
        }
        
        if (jobData.status === 'queued' || jobData.status === 'processing') {
            if (elapsedTime >= 5 && isPotentiallyFirstLoad) {
                setShowInitialLoadMessage(true);
            }
        } else {
            setIsPotentiallyFirstLoad(false); 
            setShowInitialLoadMessage(false);
        }
        
        if (jobData.status === 'completed') {
          setShowProcessingCompleteMessage(true); 
          setIsPotentiallyFirstLoad(false);
          setShowInitialLoadMessage(false);
          setMeta(jobData.result?.meta || null);
          setSections(jobData.result?.sections || null);
          setReferences(jobData.result?.references || null);
          setFiguresData(jobData.result?.figures || []);
          setTablesData(jobData.result?.tables || []);
          setGoogleDriveUrl(jobData.result?.google_drive_url || null);
          setEnhancedSuggestedTags(jobData.result?.meta?.suggested_tags_with_alternatives || []);
          if (jobData.result?.sections && Array.isArray(jobData.result.sections)) {
            const processedSections = jobData.result.sections.map((sec, index) => ({
              id: `section-${index}-${(sec.head || `untitled-section-${index}`).replace(/\s+/g, '-')}`,
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
            setSections(null);
          }
          setStatus('done'); 
        } else if (jobData.status === 'failed') {
          setError(`解析処理に失敗しました: ${jobData.error || '不明なエラー'}`);
          setIsPotentiallyFirstLoad(false);
          setShowInitialLoadMessage(false);
          setStatus('failed');
          setParsingJobId(null); 
        } else if (jobData.status === 'not_found') {
            setError(`ジョブ (ID: ${parsingJobId}) が見つかりませんでした。`);
            setDetailedParsingMessage("指定されたジョブが見つかりません。");
            setStatus('failed');
            setParsingJobId(null);
        } else if (jobData.status === 'queued' || jobData.status === 'processing') {
            if (status !== jobData.status) {
                setStatus(jobData.status);
            }
        } else {
            logger.warn("Unknown job status received from backend:", jobData.status);
            setError("不明な処理ステータスを受信しました。");
            setDetailedParsingMessage("不明なステータスです。");
            setStatus('failed');
            setParsingJobId(null);
        }
      } catch (err) {
        logger.error("Error during polling in fetchJobStatus:", err);
        if (pollingIntervalRef.current) {
            clearInterval(pollingIntervalRef.current);
            pollingIntervalRef.current = null;
        }
        if (err.response && err.response.status === 404) {
          setError(`ジョブ (ID: ${parsingJobId}) の状況確認に失敗しました (APIエラー 404)。`);
          setDetailedParsingMessage("ジョブの状況を確認できません (404)。");
        } else {
          setError("処理状況の確認中に予期せぬエラーが発生しました。");
          setDetailedParsingMessage("状況確認中に通信エラーが発生しました。");
        }
        setStatus('failed');
        setParsingJobId(null); 
        setIsPotentiallyFirstLoad(false);
        setShowInitialLoadMessage(false);
      }
    };

    if (parsingJobId && (status === 'queued' || status === 'processing')) {
      if (pollingIntervalRef.current) {
        clearInterval(pollingIntervalRef.current);
      }
      fetchJobStatus(); 
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
        pollingIntervalRef.current = null; 
      }
    };
  }, [parsingJobId, status]); // 依存配列を絞り込み


  // ★★★ parsingStatusMessage 更新専用の useEffect (修正) ★★★
  useEffect(() => {
    if (status === 'queued' || status === 'processing') {
      // detailedParsingMessage があればそれを優先、なければデフォルトの処理中メッセージ
      let message = detailedParsingMessage || `処理中 (${originalFileName || 'ファイル名不明'})`;
      if (elapsedTime > 0 && !showInitialLoadMessage) { 
        message += ` - 約${elapsedTime}秒経過...`;
      }
      setParsingStatusMessage(message);
    } else if (status === 'done') {
      if (showProcessingCompleteMessage) { // 「結果を処理中です」の一時的なメッセージ
        setParsingStatusMessage("解析が完了しました。結果を処理中です...");
        setDetailedParsingMessage(""); // この期間は詳細メッセージは不要
      } else { // 結果表示がメインになったら、ステータスメッセージはクリア
        setParsingStatusMessage(""); 
        setDetailedParsingMessage("");
      }
    } else if (status === 'failed') {
      // エラーメッセージをセット (detailedParsingMessage に具体的なエラーが入ることを期待)
      setParsingStatusMessage(detailedParsingMessage || (error ? `エラー: ${String(error).split('\n')[0]}` : "解析処理に失敗しました。"));
      if (!detailedParsingMessage && error) setDetailedParsingMessage(""); // 重複を避ける
    } else if (!parsingJobId && status !== 'file_selected') {
        setParsingStatusMessage("");
        setDetailedParsingMessage("");
    } else if (status === 'file_selected') {
        setParsingStatusMessage("PDFファイルが選択されました。「PDFを解析」ボタンを押してください。");
        setDetailedParsingMessage("");
    }
  // detailedParsingMessage も依存配列に追加
  }, [status, elapsedTime, originalFileName, detailedParsingMessage, error, parsingJobId, showInitialLoadMessage, showProcessingCompleteMessage]);


  useEffect(() => {
    if (status === 'done' && meta && showProcessingCompleteMessage) {
      const clearMsgTimeout = setTimeout(() => {
        setShowProcessingCompleteMessage(false);
        // parsingStatusMessage と detailedParsingMessage は上のuseEffectでクリアされる
      }, 2000); // 2秒後に「結果を処理中です」メッセージをクリア
      return () => clearTimeout(clearMsgTimeout);
    }
  }, [status, meta, showProcessingCompleteMessage]);

  const goBack = () => { setShowBackButton(false); window.history.back(); };

  const resetState = (keepFile = false) => {
    if (!keepFile) {
        const fileInput = document.querySelector('input[type="file"]');
        if (fileInput) fileInput.value = "";
        setFile(null); setOriginalFileName("");
    }
    setStatus(null); setError(null); setMeta(null); setSections(null);
    setReferences(null); setFiguresData([]); setTablesData([]);
    setGoogleDriveUrl(null); 
    setSummaries({}); setLoadingSummaries({}); setAudioUrls({}); setLoadingAudio({});
    setExpanded({}); setNotionStatus(null); setNotionError(null); setNotionPageUrl(null);
    setUserTags([]); setCurrentTagInput(""); setUserRating(null); setUserMemo("");
    setEnhancedSuggestedTags([]); setLoadingSuggestedTags(false);
    setParsingJobId(null); 
    setParsingStatusMessage(""); setDetailedParsingMessage("");
    setIsPotentiallyFirstLoad(false); setShowInitialLoadMessage(false);
    setShowProcessingCompleteMessage(false); setElapsedTime(0);
    if (pollingIntervalRef.current) { clearInterval(pollingIntervalRef.current); pollingIntervalRef.current = null; }
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
  };

  const handleFileChange = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
        setFile(selectedFile); setOriginalFileName(selectedFile.name);
        resetState(true); 
        setStatus("file_selected"); setError(null);
    }
  };

  async function handleUpload(e) {
    e.preventDefault();
    if (!file) { setError('PDFファイルを選択してください'); return; }
    resetState(true); 
    setStatus('uploading'); setIsPotentiallyFirstLoad(true);
    setError(null);
    const form = new FormData();
    form.append('file', file);
    try {
      const endpoint = `${process.env.NEXT_PUBLIC_BACKEND_URL}/api/parse_async`;
      const res = await axios.post(endpoint, form);
      if (res.data && res.data.job_id) {
        setParsingJobId(res.data.job_id); 
        setStatus(res.data.status || 'queued');
        if(res.data.status_detail) setDetailedParsingMessage(res.data.status_detail);
      } else {
        throw new Error("バックエンドからジョブIDが返されませんでした。");
      }
    } catch (err) {
      logger.error("Error initiating async parse:", err);
      setError(err.response?.data?.detail || err.message || '非同期処理の開始に失敗しました。');
      setStatus('failed'); setParsingJobId(null);
      setIsPotentiallyFirstLoad(false); setShowInitialLoadMessage(false);
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
      logger.error("Error during summarization:", err);
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
      const response = await axios.post(
        `${process.env.NEXT_PUBLIC_BACKEND_URL}/tts`,
        { text: plainText, language: 'ja' },
        { responseType: 'blob' } 
      );
      const url = URL.createObjectURL(response.data); 
      setAudioUrls(prev => ({ ...prev, [sectionId]: url }));
    } catch (err) {
      logger.error("Error during TTS generation:", err);
      setError(`音声生成失敗 (セクションID: ${sectionId}): ${err.response?.data?.detail || err.message}`);
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
    setNotionStatus('saving'); setNotionError(null); setNotionPageUrl(null); 
    const notionData = {
      title: meta.title, authors: meta.authors || [], journal: meta.journal || null,
      published_date: meta.issued || null, doi: meta.doi || null,
      pdf_filename: originalFileName || null, pdf_google_drive_url: googleDriveUrl, 
      original_abstract: meta.abstract || null, tags: userTags, rating: userRating, memo: userMemo,
    };
    try {
      const response = await axios.post(`${process.env.NEXT_PUBLIC_BACKEND_URL}/api/save_to_notion`, notionData);
      if (response.data.success) {
        setNotionStatus('saved');
        // ★★★ バックエンドから返される個別ページURLの代わりに、固定のDB URLを設定 ★★★
        setNotionPageUrl(FIXED_NOTION_DATABASE_URL); 
        // setNotionPageUrl(response.data.url || NOTION_TARGET_URL); 
      } else {
        throw new Error(response.data.error || "Notionへの保存レスポンスが不正です。");
      }
    } catch (err) {
      logger.error("Error saving to Notion:", err);
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

  const addSuggestedTag = (tagToAdd, existingSimilarTag = null) => {
    const finalTag = existingSimilarTag || tagToAdd;
    if (finalTag && !userTags.includes(finalTag)) {
      setUserTags(prevTags => [...prevTags, finalTag]);
    }
  };

  const renderSection = (sec, isLastContentSection) => {
    const { id: sectionId, head: name, text: htmlText, figures: sectionFigures, level, subsections } = sec;
    const plainTextContent = (htmlText || "").replace(/<[^>]+>/g, '').trim();
    const hasMeaningfulContent = name || plainTextContent || (sectionFigures && sectionFigures.length > 0) || (subsections && subsections.length > 0);
    if (!hasMeaningfulContent) return null;
    const { previewText, isLong: isTextLong, fullTextHtml } = getPlainTextPreview(htmlText, 500);
    const isExpandedForThisSection = sectionId ? !!expanded[sectionId] : true;
    const textToRenderHtml = isTextLong && name && !isExpandedForThisSection ? `<p>${previewText.replace(/\n\n+/g, '</p><p>').replace(/\n/g, '<br />')}</p>` : fullTextHtml;
    const isReferencesSectionByName = typeof name === 'string' && (name.toLowerCase().includes('reference') || name.toLowerCase().includes('参考文献') || name.toLowerCase().includes('bibliography') || name.toLowerCase().includes('literature cited'));
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
        {!isReferencesSectionByName && isTextLong && name && plainTextContent && (
          <button className={styles.readMoreButton} onClick={() => setExpanded(prev => ({ ...prev, [sectionId]: !prev[sectionId] }))}>
            {isExpandedForThisSection ? '▲ 閉じる' : '▼ 続きを読む'}
          </button>
        )}
        {!isReferencesSectionByName && plainTextContent && (
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
                    {audioUrls[sectionId] && (<audio controls src={audioUrls[sectionId]} onEnded={() => { URL.revokeObjectURL(audioUrls[sectionId]); setAudioUrls(prev => ({...prev, [sectionId]: null})); }} style={{ marginTop: '8px', width: '100%'}}/> )}
                  </div>
                </>
              )}
            </div>
          </div>
        )}
        {isLastContentSection && !isReferencesSectionByName && (<div className={styles.sectionFooterActions}><a href="#notion-save-area" className={styles.actionLinkButton}> ▲ Notion登録セクションへ移動 </a></div>)}
        {subsections && subsections.length > 0 && (<div className={styles.subSectionsContainer}>{subsections.map(subSec => renderSection(subSec, false))}</div>)}
      </section>
    );
  };

  const contentSectionsForNotionLink = sections ? sections.filter(sec =>sec.level === 1 && (sec.head || ((sec.text || "").replace(/<[^>]+>/g, '').trim())) && !(typeof sec.head === 'string' && (sec.head.toLowerCase().includes('reference') || sec.head.toLowerCase().includes('参考文献') || sec.head.toLowerCase().includes('bibliography') || sec.head.toLowerCase().includes('literature cited') || sec.head.toLowerCase().includes('figure') || sec.head.toLowerCase().includes('table')))) : [];
  const isParsingInProgress = status === 'uploading' || status === 'queued' || status === 'processing';

  return (
    <main className={styles.main}>
      <div className={styles.header}>
        <div className={styles.titleContainer}>
          <Image src="/PapeLog.png" alt="PapeLog Logo" width={128} height={128} className={styles.logoImage} />
          <h1>PapeLog</h1>
        </div>
        <p className={styles.description}>
          PDF論文をアップロードすれば、AIが構造解析しGoogle Driveへ賢く保存。<br/><strong>タグ候補もAIが自動で提案！</strong><br />
          AI要約や音声読み上げで時短学習、評価・メモ・タグと共にNotionへ一元管理。<br />
          あなたの「読んだ」を、たしかな「記録」へ。
        </p>
      </div>

      <form onSubmit={handleUpload} className={styles.form}>
        <input type="file" id="fileInput" accept="application/pdf" onChange={handleFileChange} disabled={isParsingInProgress} />
        <button type="submit" disabled={!file || isParsingInProgress}>
          {isParsingInProgress ? '解析処理中...' : 'PDFを解析'}
        </button>
        {originalFileName && <p className={styles.fileName}>選択中のファイル: {originalFileName}</p>}
      </form>

      {/* ★★★ 初回起動メッセージ (復活・修正) ★★★ */}
      {showInitialLoadMessage && isParsingInProgress && ( // isParsingInProgressも条件に追加
        <p className={styles.infoMessage}>
          初回アクセス時はサーバーの準備に時間がかかることがあります (最大2～3分程度)。しばらくお待ちください。
          {elapsedTime > 0 && ` (約${elapsedTime}秒経過)`}
        </p>
      )}
      
      {/* ★★★ ステータスBOXに表示を統一 (詳細進捗＋経過時間 または エラー/完了メッセージ) ★★★ */}
      {!showInitialLoadMessage && parsingStatusMessage && (status === 'queued' || status === 'processing' || status === 'failed' || (status === 'done' && showProcessingCompleteMessage)) && (
        <div className={styles.statusBox}> {/* 既存のステータスBOXのスタイルを想定 */}
          <p 
            className={status === 'failed' ? styles.error : styles.statusMessage} 
            dangerouslySetInnerHTML={{ __html: parsingStatusMessage.replace(/\n/g, '<br />') }} 
          />
        </div>
      )}

      {status === 'done' && meta && (
        <>
          <section className={`${styles.section} ${styles.metaSection}`}>
            {meta.title && <h2>{meta.title}</h2>}
            <p><strong>著者:</strong> <span>{meta.authors && meta.authors.length > 0 ? meta.authors.join(', ') : 'N/A'}</span></p>
            <p><strong>ジャーナル:</strong> <span>{meta.journal || 'N/A'}</span></p>
            <p><strong>発行日:</strong> <span>{meta.issued || 'N/A'}</span></p>
            {meta.doi && <p><strong>DOI:</strong> <span>{meta.doi}</span></p>}
            {googleDriveUrl && <p><strong>Google Drive Link:</strong> <a href={googleDriveUrl} target="_blank" rel="noopener noreferrer">{googleDriveUrl}</a></p>}
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
                  <input type="text" id="notionTags" value={currentTagInput} onChange={handleTagInputChange} onKeyDown={handleTagInputKeyDown} placeholder="例: 看護介入, 質的研究, 疼痛管理, QALY" className={styles.tagInputField}/>
                  <div className={styles.tagsPreview}>
                    {userTags.map(tag => (
                      <span key={tag} className={styles.tagItem}>
                        {tag}
                        <button onClick={() => removeTag(tag)} className={styles.removeTagButton} title={`タグ "${tag}" を削除`}>×</button>
                      </span>
                    ))}
                  </div>
                                  
                  {/* ★★★ AIによる提案タグの表示と選択 (UI修正) ★★★ */}
                  {loadingSuggestedTags && <p className={styles.infoMini}>タグを提案中です...</p>}
                  {enhancedSuggestedTags && enhancedSuggestedTags.length > 0 && !loadingSuggestedTags && (
                    <div className={styles.suggestedTagsArea}>
                      <p className={styles.suggestedTagsTitle}>提案タグ (クリックで追加):</p>
                      {enhancedSuggestedTags.map((suggestion, index) => {
                        const aiTag = suggestion.original_ai_tag;
                        const existingTag = suggestion.existing_similar_tag;
                        // 大文字・小文字を無視してAI提案タグと既存タグが実質的に同じ文字列か判定
                        const isEssentiallySame = existingTag && aiTag.toLowerCase() === existingTag.toLowerCase();

                        return (
                          <div key={`suggestion-group-${index}`} className={styles.suggestionGroup}>
                            {/* メインの提案ボタン (既存タグがあればそれを優先表示、なければAI提案タグを表示) */}
                            <button
                              className={styles.suggestedTagButton}
                              onClick={() => addSuggestedTag(existingTag || aiTag)} // 既存タグがあればそれを、なければAIタグを追加
                              disabled={userTags.includes(existingTag || aiTag)}
                              title={
                                existingTag 
                                  ? `既存のタグ「${existingTag}」${!isEssentiallySame ? ` (AI提案: ${aiTag})` : ''} を追加します`
                                  : `新しいタグ「${aiTag}」として追加します`
                              }
                            >
                              {existingTag ? (
                                <>
                                  <strong>{existingTag}</strong> {/* 既存タグを太字で表示 */}
                                  <span className={styles.tagTypeMarker}>[既存]</span>
                                  {/* AI提案と既存タグが異なる場合のみ、AI提案を括弧で補足 */}
                                  {!isEssentiallySame && (
                                    <span className={styles.aiCandidateText}> (AI候補: {aiTag})</span>
                                  )}
                                </>
                              ) : (
                                <>
                                  {aiTag} {/* 既存タグがなければAI提案タグを表示 */}
                                  <span className={styles.tagTypeMarker}>[AI提案]</span>
                                </>
                              )}
                              <span style={{ marginLeft: '0.3em' }}>＋</span>
                            </button>

                            {/* AI提案タグを「新規タグ」として明示的に追加するボタン */}
                            {/* (既存タグがあり、かつAI提案タグと既存タグが異なる場合のみ表示) */}
                            {existingTag && !isEssentiallySame && (
                               <button
                                  className={`${styles.suggestedTagButton} ${styles.suggestedTagButtonAlt}`}
                                  onClick={() => addSuggestedTag(aiTag)} // AI提案タグを新規として追加
                                  disabled={userTags.includes(aiTag)}
                                  title={`AIが提案したタグ「${aiTag}」を新しいタグとして追加します`}
                               >
                                 {aiTag}
                                 <span className={styles.tagTypeMarker}>[新規として採用]</span>
                                 <span style={{ marginLeft: '0.3em' }}>＋</span>
                               </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  )}
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
            {references && references.length > 0 && ( <li key="toc-references"><a href="#references_list_title">References</a></li> )}
          </ul>
        </details>
      )}

      {status === 'done' && sections && (
        <div className={styles.results}>
          {sections.filter(sec => sec.level === 1).length > 0 ? (
            sections.filter(sec => sec.level === 1).map((sec) => {
              const isLastContentSec = contentSectionsForNotionLink.length > 0 && sec.id === contentSectionsForNotionLink[contentSectionsForNotionLink.length - 1]?.id;
              return renderSection(sec, isLastContentSec);
            })
          ) : sections.length > 0 ? ( 
            sections.map((sec) => {
                const isLastContentSec = contentSectionsForNotionLink.length > 0 && sec.id === contentSectionsForNotionLink[contentSectionsForNotionLink.length - 1]?.id;
                return renderSection(sec, isLastContentSec)
            })
          ) : (
            <p className={styles.empty}>表示できるセクションが見つかりませんでした。</p>
          )}
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
          <div className={styles.sectionHeaderWithButton}>
            <h2>References</h2>
            <button onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })} className={styles.scrollToTopButton} title="ページトップへ戻る">
              ▲ トップへ
            </button>
          </div>
          <ol className={styles.referencesList}>
            {references.map((ref, index) => {
              const refText = ref.text;
              const plainRefTextForSearch = typeof refText === 'string' ? refText.replace(/<[^>]+>/g, '') : '';
              const searchQuery = ref.search_query || plainRefTextForSearch;
              const googleScholarUrl = `https://scholar.google.com/scholar?q=${encodeURIComponent(searchQuery)}`;
              const pubmedUrl = `https://pubmed.ncbi.nlm.nih.gov/?term=${encodeURIComponent(searchQuery)}`;
              const referenceItemId = ref.id ? `ref-${ref.id}` : `ref-item-idx-${index}`;
              return (
                <li key={referenceItemId} id={referenceItemId}>
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

      {showBackButton && (
        <button className={styles.backButton} onClick={goBack} title="前のセクション/ページに戻る">
          ▲ 戻る
        </button>
      )}
    </main>
  );
}