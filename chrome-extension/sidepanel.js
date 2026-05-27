// Side panel controller — includes inline settings drawer

const frame      = document.getElementById('app-frame');
const offlineMsg = document.getElementById('offline-msg');
const statusDot  = document.getElementById('status-dot');
const statusText = document.getElementById('status-text');
const ytBtn      = document.getElementById('yt-btn');
const zoomOutBtn = document.getElementById('zoom-out-btn');
const zoomInBtn  = document.getElementById('zoom-in-btn');
const zoomLabel  = document.getElementById('zoom-label');

// ── i18n ──────────────────────────────────────────────────────────────────────

const I18N = {
  zh: {
    settings: '設定',
    serverSection: 'Server 連線',
    portLabel: 'Port',
    portHint: '本地 FastAPI server 的 port，預設 7654',
    vaultLabel: 'Obsidian Vault 名稱',
    vaultHint: '用於產生 obsidian:// 連結開啟筆記',
    save: '儲存',
    testConn: '測試連線',
    outputSection: '筆記輸出位置',
    outputObsidianTitle: 'Obsidian Vault',
    outputObsidianDesc: '依 podcasts.json 設定的 note_dir 儲存',
    outputFolderTitle: '自訂資料夾',
    outputFolderDesc: '不需 Obsidian，純 .md 檔案',
    folderLabel: '資料夾路徑',
    folderHint: '筆記將以 .md 格式存入此資料夾',
    generationSection: '筆記生成模型',
    generationClaudeTitle: 'Claude（預設）',
    generationClaudeDesc: '沿用 claude -p，適合保守穩定的產線',
    generationCodexTitle: 'Codex',
    generationCodexDesc: '用 Codex CLI 產生 analysis.json，再由本機流程寫入筆記',
    transcriptSection: '轉錄方式',
    transcriptLocalTitle: '本地（faster-whisper）',
    transcriptLocalDesc: '需要 ffmpeg，不花 API 費用，支援 GPU 加速',
    transcriptApiTitle: '雲端（Whisper API）',
    transcriptApiDesc: '需要 OpenAI API key，不需要本地模型',
    modelLabel: '本地模型大小',
    keyLabel: 'OpenAI API Key',
    keyNotSet: '尚未設定 API Key',
    keySet: 'API Key 已設定',
    keyHint: 'Key 僅存在本機 server，不傳到其他地方。留空則保留已儲存的 Key。',
    langLabel: '筆記輸出語言',
    langHint: '決定筆記輸出語言（與轉錄語言無關）',
    promptSection: '分析 Prompt',
    customBadge: '已自訂',
    promptHint: '預設為 note-investment.md。修改後儲存，下次分析生效。',
    savePrompt: '儲存 Prompt',
    reload: '重新載入',
    resetDefault: '恢復預設',
    analyzing: '分析影片',
    connecting: '連線中...',
    connected: '已連線',
    offline: '離線',
    retryConn: '重新連線',
    serverOffline: '無法連線到本地 Server',
  },
  en: {
    settings: 'Settings',
    serverSection: 'Server Connection',
    portLabel: 'Port',
    portHint: 'Local FastAPI server port, default 7654',
    vaultLabel: 'Obsidian Vault Name',
    vaultHint: 'Used to generate obsidian:// links to open notes',
    save: 'Save',
    testConn: 'Test Connection',
    outputSection: 'Note Output',
    outputObsidianTitle: 'Obsidian Vault',
    outputObsidianDesc: 'Save to note_dir from podcasts.json',
    outputFolderTitle: 'Custom Folder',
    outputFolderDesc: 'Plain .md files, no Obsidian needed',
    folderLabel: 'Folder Path',
    folderHint: 'Notes will be saved as .md files to this folder',
    generationSection: 'Note Generator',
    generationClaudeTitle: 'Claude (default)',
    generationClaudeDesc: 'Use the existing claude -p flow for stable production notes',
    generationCodexTitle: 'Codex',
    generationCodexDesc: 'Use Codex CLI to create analysis.json, then write notes locally',
    transcriptSection: 'Transcription',
    transcriptLocalTitle: 'Local (faster-whisper)',
    transcriptLocalDesc: 'Requires ffmpeg, no API cost, supports GPU',
    transcriptApiTitle: 'Cloud (Whisper API)',
    transcriptApiDesc: 'Requires OpenAI API key, no local model needed',
    modelLabel: 'Local Model Size',
    keyLabel: 'OpenAI API Key',
    keyNotSet: 'API Key not set',
    keySet: 'API Key saved',
    keyHint: 'Key is stored locally only. Leave blank to keep existing key.',
    langLabel: 'Note Output Language',
    langHint: 'Language used to write notes (independent of transcript language)',
    promptSection: 'Analysis Prompt',
    customBadge: 'Custom',
    promptHint: 'Default is note-investment.md. Changes take effect on next analysis.',
    savePrompt: 'Save Prompt',
    reload: 'Reload',
    resetDefault: 'Reset to Default',
    analyzing: 'Analyze Video',
    connecting: 'Connecting...',
    connected: 'Connected',
    offline: 'Offline',
    retryConn: 'Reconnect',
    serverOffline: 'Cannot connect to local server',
  },
};
I18N.auto = I18N.zh; // auto fallback

let currentLang = 'zh';
let uiZoom = 1;

function applyLang(lang) {
  currentLang = lang in I18N ? lang : 'zh';
  const t = I18N[currentLang];

  // Drawer header
  document.querySelector('#drawer-header h2').textContent = t.settings;

  // Server section
  setText('s-server-label', t.serverSection);
  setText('s-port-label', t.portLabel);
  setText('s-port-hint', t.portHint);
  setText('s-vault-label', t.vaultLabel);
  setText('s-vault-hint', t.vaultHint);
  setText('d-saveBtn', t.save);
  setText('d-testBtn', t.testConn);

  // Output section
  setText('s-output-label', t.outputSection);
  setText('s-obsidian-title', t.outputObsidianTitle);
  setText('s-obsidian-desc', t.outputObsidianDesc);
  setText('s-folder-title', t.outputFolderTitle);
  setText('s-folder-desc', t.outputFolderDesc);
  setText('s-folder-label', t.folderLabel);
  setText('s-folder-hint', t.folderHint);
  setText('d-saveOutputBtn', t.save);

  // Generation section
  setText('s-generation-label', t.generationSection);
  setText('s-provider-claude-title', t.generationClaudeTitle);
  setText('s-provider-claude-desc', t.generationClaudeDesc);
  setText('s-provider-codex-title', t.generationCodexTitle);
  setText('s-provider-codex-desc', t.generationCodexDesc);
  setText('d-saveGenerationBtn', t.save);

  // Transcript section
  setText('s-transcript-label', t.transcriptSection);
  setText('s-local-title', t.transcriptLocalTitle);
  setText('s-local-desc', t.transcriptLocalDesc);
  setText('s-api-title', t.transcriptApiTitle);
  setText('s-api-desc', t.transcriptApiDesc);
  setText('s-model-label', t.modelLabel);
  setText('s-key-label', t.keyLabel);
  setText('d-keyStatusText', currentLang === 'zh'
    ? (document.getElementById('d-keyStatus').classList.contains('saved') ? t.keySet : t.keyNotSet)
    : (document.getElementById('d-keyStatus').classList.contains('saved') ? t.keySet : t.keyNotSet));
  setText('s-key-hint', t.keyHint);
  setText('s-lang-label', t.langLabel);
  setText('s-lang-hint', t.langHint);
  setText('d-saveTranscriptBtn', t.save);

  // Prompt section
  setText('s-prompt-label', t.promptSection);
  setText('d-customBadge', t.customBadge);
  setText('s-prompt-hint', t.promptHint);
  setText('d-savePromptBtn', t.savePrompt);
  setText('d-reloadPromptBtn', t.reload);
  setText('d-resetPromptBtn', t.resetDefault);

  // Toolbar / status
  statusText.textContent = statusDot.classList.contains('online') ? t.connected
    : statusDot.classList.contains('offline') ? t.offline : t.connecting;
  ytBtn.querySelector('span') && (ytBtn.querySelector('span').textContent = ' ' + t.analyzing);
  document.getElementById('retry-btn').textContent = t.retryConn;
  document.querySelector('#offline-msg strong').textContent = t.serverOffline;
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

let serverUrl = 'http://localhost:7654';

// ── Init ──────────────────────────────────────────────────────────────────────

async function init() {
  const res = await sendBg({ type: 'GET_SERVER_URL' });
  if (res?.url) serverUrl = res.url;

  const stored = await chrome.storage.local.get({ uiZoom: 1 });
  applyUiZoom(stored.uiZoom || 1);

  await checkAndLoad();
  pollYouTubeTab();

  chrome.tabs.onActivated.addListener(() => pollYouTubeTab());
  chrome.tabs.onUpdated.addListener((_id, info) => {
    if (info.status === 'complete') pollYouTubeTab();
  });

  document.getElementById('popout-btn').addEventListener('click', popout);
  document.getElementById('settings-btn').addEventListener('click', openSettings);
  document.getElementById('retry-btn').addEventListener('click', checkAndLoad);
  zoomOutBtn.addEventListener('click', () => setUiZoom(uiZoom - 0.1));
  zoomInBtn.addEventListener('click', () => setUiZoom(uiZoom + 0.1));
  zoomLabel.addEventListener('click', () => setUiZoom(1));
  ytBtn.addEventListener('click', analyzeCurrentVideo);

  initSettingsDrawer();
}

// ── UI zoom ──────────────────────────────────────────────────────────────────

function clampZoom(value) {
  return Math.min(1.5, Math.max(0.7, Math.round(value * 10) / 10));
}

function applyUiZoom(value) {
  uiZoom = clampZoom(value);
  frame.style.transform = `scale(${uiZoom})`;
  frame.style.width = `${100 / uiZoom}%`;
  frame.style.height = `${100 / uiZoom}%`;
  zoomLabel.textContent = `${Math.round(uiZoom * 100)}%`;
  zoomOutBtn.disabled = uiZoom <= 0.7;
  zoomInBtn.disabled = uiZoom >= 1.5;
}

async function setUiZoom(value) {
  applyUiZoom(value);
  await chrome.storage.local.set({ uiZoom });
}

// ── Server health ─────────────────────────────────────────────────────────────

async function checkAndLoad() {
  statusDot.className = 'status-dot';
  statusText.textContent = '連線中...';
  try {
    const r = await fetch(`${serverUrl}/api/youtube/channels`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!r.ok) throw new Error('bad status');
    showFrame();
  } catch (_) {
    showOffline();
  }
}

function showFrame() {
  offlineMsg.style.display = 'none';
  frame.style.display = 'block';
  statusDot.className = 'status-dot online';
  statusText.textContent = I18N[currentLang].connected;
  if (frame.src !== serverUrl + '/') frame.src = serverUrl + '/';
}

function showOffline() {
  frame.style.display = 'none';
  offlineMsg.style.display = 'flex';
  statusDot.className = 'status-dot offline';
  statusText.textContent = I18N[currentLang].offline;
}

// ── YouTube button ────────────────────────────────────────────────────────────

async function pollYouTubeTab() {
  const info = await sendBg({ type: 'GET_PAGE_INFO' });
  if (info?.isVideoPage && info.videoId) {
    ytBtn.style.display = 'inline-flex';
    ytBtn.dataset.videoId = info.videoId;
    ytBtn.textContent = '▶ 分析影片';
    // restore text (may have been overwritten by prior analysis)
    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('width', '11'); icon.setAttribute('height', '11');
    icon.setAttribute('viewBox', '0 0 24 24'); icon.setAttribute('fill', 'currentColor');
    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    poly.setAttribute('points', '5 3 19 12 5 21 5 3');
    icon.appendChild(poly);
    ytBtn.textContent = ' 分析影片';
    ytBtn.prepend(icon);
  } else {
    ytBtn.style.display = 'none';
  }
}

async function analyzeCurrentVideo() {
  const videoId = ytBtn.dataset.videoId;
  if (!videoId) return;

  ytBtn.disabled = true;
  ytBtn.textContent = '處理中...';

  try {
    await fetch(`${serverUrl}/api/youtube/queue`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: `https://www.youtube.com/watch?v=${videoId}` }),
    });
    const r = await fetch(`${serverUrl}/api/youtube/videos/${videoId}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    });
    const data = await r.json();
    if (data.job_id) {
      ytBtn.textContent = '⏳ 分析中...';
      pollJob(data.job_id);
    } else {
      resetYtBtn();
    }
  } catch (_) {
    ytBtn.textContent = '❌ 失敗';
    setTimeout(resetYtBtn, 2000);
  }
}

async function pollJob(jobId) {
  const timer = setInterval(async () => {
    try {
      const r = await fetch(`${serverUrl}/api/jobs/${jobId}`);
      const job = await r.json();
      if (job.status === 'done') {
        clearInterval(timer);
        ytBtn.textContent = '✅ 完成';
        frame.src = frame.src;
        setTimeout(resetYtBtn, 3000);
      } else if (job.status === 'error') {
        clearInterval(timer);
        ytBtn.textContent = '❌ 失敗';
        setTimeout(resetYtBtn, 3000);
      } else {
        ytBtn.textContent = `⏳ ${job.phase || '分析中'}`;
      }
    } catch (_) {
      clearInterval(timer);
      resetYtBtn();
    }
  }, 2000);
}

function resetYtBtn() {
  ytBtn.disabled = false;
  pollYouTubeTab(); // restore icon + text
}

// ── Popout ────────────────────────────────────────────────────────────────────

function popout() {
  chrome.tabs.create({ url: serverUrl + '/' });
  window.close();
}

// ── Settings Drawer ───────────────────────────────────────────────────────────

const drawer  = document.getElementById('settings-drawer');
const overlay = document.getElementById('settings-overlay');

function openSettings() {
  drawer.classList.add('open');
  overlay.classList.add('open');
  document.getElementById('drawer-close').focus();
  loadDrawerSettings();
}

function closeSettings() {
  drawer.classList.remove('open');
  overlay.classList.remove('open');
  document.getElementById('settings-btn').focus();
}

function initSettingsDrawer() {
  document.getElementById('drawer-close').addEventListener('click', closeSettings);
  overlay.addEventListener('click', closeSettings);

  // Close on Escape
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && drawer.classList.contains('open')) closeSettings();
  });

  // Output mode toggle
  document.querySelectorAll('input[name="outputMode"]').forEach(r => {
    r.addEventListener('change', () => {
      const isFolder = document.querySelector('input[name="outputMode"]:checked')?.value === 'folder';
      document.getElementById('d-folderPathField').style.display = isFolder ? 'block' : 'none';
    });
  });

  // Transcription mode toggle
  document.querySelectorAll('input[name="transcriptMode"]').forEach(r => {
    r.addEventListener('change', syncTranscriptFields);
  });

  // Language pill — auto-save + switch UI language immediately
  document.querySelectorAll('input[name="analysisLang"]').forEach(r => {
    r.addEventListener('change', async () => {
      const lang = r.value;
      applyLang(lang);
      // save silently (no loading state needed — instant feel)
      const mode = document.querySelector('input[name="transcriptMode"]:checked')?.value || 'local';
      const whisper_model = document.getElementById('d-whisperModel').value;
      try {
        await fetch(`${serverUrl}/api/settings/transcription`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode, whisper_model, openai_api_key: '', language: lang }),
        });
      } catch (_) {}
    });
  });

  // API key show/hide toggle
  document.getElementById('d-keyToggle').addEventListener('click', () => {
    const input = document.getElementById('d-openaiKey');
    const icon = document.getElementById('d-eyeIcon');
    const isHidden = input.type === 'password';
    input.type = isHidden ? 'text' : 'password';
    icon.innerHTML = isHidden
      ? '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94"/><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>'
      : '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  });

  // Transcription save
  document.getElementById('d-saveTranscriptBtn').addEventListener('click', async () => {
    const btn = document.getElementById('d-saveTranscriptBtn');
    const mode = document.querySelector('input[name="transcriptMode"]:checked')?.value || 'local';
    const whisper_model = document.getElementById('d-whisperModel').value;
    const openai_api_key = document.getElementById('d-openaiKey').value.trim();
    const language = document.querySelector('input[name="analysisLang"]:checked')?.value || 'zh';

    btn.classList.add('loading');
    btn.textContent = '儲存中';
    try {
      const r = await fetch(`${serverUrl}/api/settings/transcription`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, whisper_model, openai_api_key, language }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      // clear key field and update status badge
      document.getElementById('d-openaiKey').value = '';
      document.getElementById('d-openaiKey').type = 'password';
      if (mode === 'api' && openai_api_key) updateKeyStatus(true);
      showDrawerStatus('d-transcriptStatusMsg', '✅ 已儲存', true);
    } catch (e) {
      showDrawerStatus('d-transcriptStatusMsg', `❌ ${e.message}`, false);
    } finally {
      btn.classList.remove('loading');
      btn.textContent = '儲存';
    }
  });

  // Connection save
  document.getElementById('d-saveBtn').addEventListener('click', async () => {
    const btn = document.getElementById('d-saveBtn');
    const port = parseInt(document.getElementById('d-serverPort').value, 10);
    const vault = document.getElementById('d-vaultName').value.trim();
    if (!port || port < 1024 || port > 65535) {
      showDrawerStatus('d-statusMsg', 'Port 必須在 1024–65535 之間', false);
      return;
    }
    btn.classList.add('loading'); btn.textContent = '儲存中';
    await chrome.storage.local.set({ serverPort: port, vaultName: vault || 'arthurwang_DB' });
    serverUrl = `http://localhost:${port}`;
    btn.classList.remove('loading'); btn.textContent = '儲存';
    showDrawerStatus('d-statusMsg', '✅ 已儲存', true);
    checkAndLoad();
  });

  // Test connection
  document.getElementById('d-testBtn').addEventListener('click', async () => {
    const port = parseInt(document.getElementById('d-serverPort').value, 10) || 7654;
    try {
      const r = await fetch(`http://localhost:${port}/api/youtube/channels`, {
        signal: AbortSignal.timeout(3000),
      });
      showDrawerStatus('d-statusMsg', r.ok ? `✅ 連線成功（port ${port}）` : `⚠️ HTTP ${r.status}`, r.ok);
    } catch (e) {
      showDrawerStatus('d-statusMsg', `❌ 無法連線：${e.message}`, false);
    }
  });

  // Output save
  document.getElementById('d-saveOutputBtn').addEventListener('click', async () => {
    const btn = document.getElementById('d-saveOutputBtn');
    const mode = document.querySelector('input[name="outputMode"]:checked')?.value || 'obsidian';
    const folder_path = document.getElementById('d-folderPath').value.trim() || '~/Documents/AlphaNote';
    btn.classList.add('loading'); btn.textContent = '儲存中';
    try {
      const r = await fetch(`${serverUrl}/api/settings/output`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, folder_path }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      showDrawerStatus('d-outputStatusMsg', '✅ 已儲存', true);
    } catch (e) {
      showDrawerStatus('d-outputStatusMsg', `❌ ${e.message}`, false);
    } finally {
      btn.classList.remove('loading'); btn.textContent = '儲存';
    }
  });

  // Generation provider save
  document.getElementById('d-saveGenerationBtn').addEventListener('click', async () => {
    const btn = document.getElementById('d-saveGenerationBtn');
    const provider = document.querySelector('input[name="generationProvider"]:checked')?.value || 'claude';
    btn.classList.add('loading'); btn.textContent = '儲存中';
    try {
      const r = await fetch(`${serverUrl}/api/settings/generation`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      showDrawerStatus(
        'd-generationStatusMsg',
        `✅ 已切換為 ${provider === 'codex' ? 'Codex' : 'Claude'}`,
        true,
      );
    } catch (e) {
      showDrawerStatus('d-generationStatusMsg', `❌ ${e.message}`, false);
    } finally {
      btn.classList.remove('loading'); btn.textContent = '儲存';
    }
  });

  // Prompt edit/preview toggle — button OR clicking the box
  document.getElementById('d-promptEditBtn').addEventListener('click', () => {
    switchToPromptEdit();
  });
  document.getElementById('d-promptBox').addEventListener('click', (e) => {
    if (document.getElementById('d-promptBox').classList.contains('previewing')) {
      switchToPromptEdit();
    }
  });

  // Cancel edit → back to preview
  document.getElementById('d-cancelPromptBtn').addEventListener('click', () => {
    // restore textarea to last saved content
    const ta = document.getElementById('d-promptEditor');
    ta.value = ta.dataset.saved || ta.value;
    switchToPromptPreview();
  });

  // Prompt save
  document.getElementById('d-savePromptBtn').addEventListener('click', async () => {
    const content = document.getElementById('d-promptEditor').value;
    const btn = document.getElementById('d-savePromptBtn');
    btn.classList.add('loading'); btn.textContent = '儲存中';
    try {
      const r = await fetch(`${serverUrl}/api/settings/prompt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      await chrome.storage.local.set({ promptCustomised: true });
      document.getElementById('d-customBadge').className = 'custom-badge visible';
      document.getElementById('d-promptEditor').dataset.saved = content;
      renderPromptPreview(content);
      switchToPromptPreview();
      showDrawerStatus('d-promptStatusMsg', '✅ Prompt 已儲存', true);
    } catch (e) {
      showDrawerStatus('d-promptStatusMsg', `❌ ${e.message}`, false);
    } finally {
      btn.classList.remove('loading'); btn.textContent = '儲存';
    }
  });

  // Prompt reload
  document.getElementById('d-reloadPromptBtn').addEventListener('click', async () => {
    await loadPromptInDrawer();
    showDrawerStatus('d-promptStatusMsg', '🔄 已重新載入', true);
  });

  // Prompt reset
  document.getElementById('d-resetPromptBtn').addEventListener('click', async () => {
    if (!confirm('確定要恢復預設 prompt？自訂內容將清除。')) return;
    try {
      await fetch(`${serverUrl}/api/settings/prompt`, { method: 'DELETE' });
      await chrome.storage.local.set({ promptCustomised: false });
      document.getElementById('d-customBadge').className = 'custom-badge';
      await loadPromptInDrawer();
      switchToPromptPreview();
      showDrawerStatus('d-promptStatusMsg', '✅ 已恢復預設', true);
    } catch (e) {
      showDrawerStatus('d-promptStatusMsg', `❌ ${e.message}`, false);
    }
  });
}

function switchToPromptPreview() {
  const box = document.getElementById('d-promptBox');
  box.classList.replace('editing', 'previewing');
  document.getElementById('d-promptEditor').style.display = 'none';
  document.getElementById('d-promptPreview').style.display = 'block';
  document.getElementById('d-promptEditHint').style.display = 'flex';
  document.getElementById('d-promptPreviewFooter').style.display = 'block';
  document.getElementById('d-promptEditFooter').style.display = 'none';
  const btn = document.getElementById('d-promptEditBtn');
  btn.classList.remove('active');
  btn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg> 編輯`;
}

function switchToPromptEdit() {
  const box = document.getElementById('d-promptBox');
  box.classList.replace('previewing', 'editing');
  document.getElementById('d-promptPreview').style.display = 'none';
  document.getElementById('d-promptEditHint').style.display = 'none';
  const ta = document.getElementById('d-promptEditor');
  ta.style.display = 'block';
  document.getElementById('d-promptPreviewFooter').style.display = 'none';
  document.getElementById('d-promptEditFooter').style.display = 'block';
  const btn = document.getElementById('d-promptEditBtn');
  btn.classList.add('active');
  btn.innerHTML = `<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg> 預覽`;
  ta.focus();
}

function renderPromptPreview(markdown) {
  const preview = document.getElementById('d-promptPreview');
  if (typeof marked !== 'undefined' && markdown.trim()) {
    preview.innerHTML = marked.parse(markdown);
  } else if (markdown.trim()) {
    // fallback: escape and wrap in pre
    preview.innerHTML = `<pre style="white-space:pre-wrap;font-size:10.5px;color:var(--text-dim);">${markdown.replace(/</g,'&lt;')}</pre>`;
  } else {
    preview.innerHTML = '<div class="prompt-preview-loading">無內容</div>';
  }
}

function syncTranscriptFields() {
  const mode = document.querySelector('input[name="transcriptMode"]:checked')?.value;
  document.getElementById('d-localModelField').classList.toggle('visible', mode === 'local');
  document.getElementById('d-apiKeyField').classList.toggle('visible', mode === 'api');
}

function updateKeyStatus(isSet) {
  const el = document.getElementById('d-keyStatus');
  const text = document.getElementById('d-keyStatusText');
  if (isSet) {
    el.className = 'key-status saved';
    el.querySelector('svg').innerHTML = '<polyline points="20 6 9 17 4 12"/>';
    text.textContent = 'API Key 已設定';
  } else {
    el.className = 'key-status empty';
    el.querySelector('svg').innerHTML = '<circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>';
    text.textContent = '尚未設定 API Key';
  }
}

async function loadDrawerSettings() {
  // Connection
  const data = await chrome.storage.local.get(['serverPort', 'vaultName', 'promptCustomised']);
  if (data.serverPort) document.getElementById('d-serverPort').value = data.serverPort;
  if (data.vaultName) document.getElementById('d-vaultName').value = data.vaultName;
  document.getElementById('d-customBadge').className =
    'custom-badge' + (data.promptCustomised ? ' visible' : '');

  // Output settings
  try {
    const r = await fetch(`${serverUrl}/api/settings/output`, { signal: AbortSignal.timeout(2000) });
    if (r.ok) {
      const cfg = await r.json();
      const radio = document.querySelector(`input[name="outputMode"][value="${cfg.mode}"]`);
      if (radio) radio.checked = true;
      if (cfg.folder_path) document.getElementById('d-folderPath').value = cfg.folder_path;
      document.getElementById('d-folderPathField').style.display =
        cfg.mode === 'folder' ? 'block' : 'none';
    }
  } catch (_) {}

  // Generation provider
  try {
    const r = await fetch(`${serverUrl}/api/settings/generation`, { signal: AbortSignal.timeout(2000) });
    if (r.ok) {
      const cfg = await r.json();
      const radio = document.querySelector(
        `input[name="generationProvider"][value="${cfg.provider || 'claude'}"]`,
      );
      if (radio) radio.checked = true;
    }
  } catch (_) {}

  // Transcription settings
  try {
    const r = await fetch(`${serverUrl}/api/settings/transcription`, { signal: AbortSignal.timeout(2000) });
    if (r.ok) {
      const cfg = await r.json();
      const radio = document.querySelector(`input[name="transcriptMode"][value="${cfg.mode}"]`);
      if (radio) radio.checked = true;
      if (cfg.whisper_model) document.getElementById('d-whisperModel').value = cfg.whisper_model;
      updateKeyStatus(!!cfg.openai_api_key_set);
      const savedLang = cfg.language || 'zh';
      const langRadio = document.querySelector(`input[name="analysisLang"][value="${savedLang}"]`);
      if (langRadio) langRadio.checked = true;
      applyLang(savedLang);
      syncTranscriptFields();
    }
  } catch (_) {}

  // Prompt
  await loadPromptInDrawer();
}

async function loadPromptInDrawer() {
  const ta = document.getElementById('d-promptEditor');
  const preview = document.getElementById('d-promptPreview');
  preview.innerHTML = '<div class="prompt-preview-loading">載入中...</div>';
  try {
    const r = await fetch(`${serverUrl}/api/settings/prompt`, { signal: AbortSignal.timeout(3000) });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const text = await r.text();
    ta.value = text;
    ta.dataset.saved = text;
    ta.placeholder = '';
    renderPromptPreview(text);
  } catch (e) {
    ta.placeholder = `無法載入（${e.message}）\n請確認 server 正在運行。`;
    preview.innerHTML = `<div class="prompt-preview-loading">無法載入：${e.message}</div>`;
  }
}

function showDrawerStatus(id, msg, ok) {
  const el = document.getElementById(id);
  el.textContent = msg;
  el.className = 's-status ' + (ok ? 'ok' : 'err');
  setTimeout(() => { el.className = 's-status'; }, 3500);
}

// ── Util ──────────────────────────────────────────────────────────────────────

function sendBg(msg) {
  return new Promise(resolve => {
    chrome.runtime.sendMessage(msg, res => resolve(res || null));
  });
}

init();
