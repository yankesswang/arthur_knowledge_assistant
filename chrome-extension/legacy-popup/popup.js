// Popup controller

let currentVideoId = null;
let currentTab = null;
let pollInterval = null;

const $ = id => document.getElementById(id);
const content = $('content');
const serverDot = $('serverDot');

// ── Init ─────────────────────────────────────────────────────────────────────

async function init() {
  $('settingsBtn').addEventListener('click', () => chrome.runtime.openOptionsPage());

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  currentTab = tab;

  // Check server health
  const serverOk = await checkServer();

  const isYouTube = tab.url && tab.url.includes('youtube.com/watch');

  if (!isYouTube) {
    renderNotYouTube(serverOk);
    return;
  }

  if (!serverOk) {
    renderServerDown();
    return;
  }

  // Ask content script for page info
  try {
    const info = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PAGE_INFO' });
    if (!info || !info.videoId) {
      renderNotYouTube(true);
      return;
    }
    currentVideoId = info.videoId;
    renderVideoPage(info);
  } catch (e) {
    // Content script not injected yet (e.g. extension just installed)
    renderNotYouTube(serverOk);
  }
}

async function checkServer() {
  return new Promise(resolve => {
    chrome.runtime.sendMessage({ type: 'CHECK_SERVER' }, res => {
      const ok = res && res.ok;
      serverDot.className = 'server-dot ' + (ok ? 'online' : 'offline');
      resolve(ok);
    });
  });
}

// ── Render helpers ───────────────────────────────────────────────────────────

function renderNotYouTube(serverOk) {
  content.innerHTML = `
    <div class="state-msg">
      <div class="emoji">📺</div>
      <div>請在 YouTube 影片頁面開啟</div>
    </div>
    ${serverOk ? openServerLink() : ''}
  `;
}

function renderServerDown() {
  content.innerHTML = `
    <div class="error-msg">
      ⚠️ 無法連線到本地 server（localhost:7654）<br>
      請先執行 <code>bash run.sh</code>
    </div>
    <div class="state-msg" style="padding-top:0">
      <div style="font-size:11px;color:var(--text-muted)">
        cd server<br>bash run.sh
      </div>
    </div>
  `;
}

function openServerLink() {
  return `<div class="open-server-link"><a href="#" id="openServerBtn">打開完整介面 →</a></div>`;
}

async function renderVideoPage(info) {
  // Show video card skeleton first
  content.innerHTML = buildVideoCard(info) + '<div id="belowCard"></div>';

  // Attach open-server link if exists
  const osBtn = document.getElementById('openServerBtn');
  if (osBtn) osBtn.addEventListener('click', openServer);

  // Fetch video status from server
  const below = $('belowCard');
  below.innerHTML = `<div style="color:var(--text-muted);font-size:11px;text-align:center;padding:8px">查詢狀態中...</div>`;

  chrome.runtime.sendMessage({ type: 'GET_VIDEO_STATUS', videoId: info.videoId }, res => {
    if (chrome.runtime.lastError) {
      renderBelowCard(below, null, info);
      return;
    }
    renderBelowCard(below, res.video, info);
  });
}

function buildVideoCard(info) {
  const thumbUrl = `https://img.youtube.com/vi/${info.videoId}/mqdefault.jpg`;
  return `
    <div class="video-card">
      <img class="video-thumb" src="${thumbUrl}" alt="thumbnail">
      <div class="video-info">
        <div class="video-title">${escHtml(info.title || '（無標題）')}</div>
        ${info.channel ? `<div class="video-channel">${escHtml(info.channel)}</div>` : ''}
      </div>
    </div>
  `;
}

function renderBelowCard(container, video, info) {
  const hasTranscript = video && video.has_transcript;
  const hasNote = video && (video.has_note || video.note_path);
  const notePath = video && video.note_path;

  let badges = '';
  if (hasTranscript) badges += `<span class="badge badge-transcript">📝 有逐字稿</span>`;
  if (hasNote) badges += `<span class="badge badge-note">✅ 已有筆記</span>`;

  let tldr = '';
  if (video && video.tldr) {
    tldr = buildTldr(video.tldr);
  }

  const analyzeLabel = hasNote ? '重新產生筆記' : hasTranscript ? '產生筆記' : '下載字幕 + 產生筆記';

  container.innerHTML = `
    ${badges ? `<div class="status-row">${badges}</div>` : ''}
    ${tldr}
    ${hasNote ? `<div class="error-msg" style="background:rgba(74,222,128,.06);color:var(--green)">✅ 筆記已存在 Obsidian vault</div>` : ''}
    <button class="btn btn-primary" id="analyzeBtn">
      🚀 ${analyzeLabel}
    </button>
    ${hasNote ? `<button class="btn btn-secondary" id="openNoteBtn">打開筆記</button>` : ''}
    <div class="open-server-link" style="margin-top:10px">
      <a href="#" id="openServerBtn2">打開完整介面 →</a>
    </div>
  `;

  document.getElementById('analyzeBtn').addEventListener('click', () => startAnalysis(info));
  const nb = document.getElementById('openNoteBtn');
  if (nb) nb.addEventListener('click', () => openObsidianNote(notePath));
  const ob = document.getElementById('openServerBtn2');
  if (ob) ob.addEventListener('click', openServer);
}

function buildTldr(tldr) {
  if (!tldr) return '';
  const entries = Object.entries(tldr)
    .filter(([, v]) => v)
    .map(([k, v]) => `<div><strong>${escHtml(k.replace(/_/g,' '))}：</strong>${escHtml(v)}</div>`)
    .join('');
  if (!entries) return '';
  return `
    <div class="note-preview">
      <h4>TL;DR</h4>
      <div class="note-tldr">${entries}</div>
    </div>
  `;
}

// ── Analysis flow ─────────────────────────────────────────────────────────────

function startAnalysis(info) {
  const below = $('belowCard');
  below.innerHTML = `
    <div class="progress-wrap" id="progressWrap">
      <div class="progress-phase">
        <span id="progressPhase">準備中...</span>
        <span id="progressPct">0%</span>
      </div>
      <div class="progress-bar-bg">
        <div class="progress-bar-fill" id="progressFill" style="width:0%"></div>
      </div>
      <div class="progress-log" id="progressLog"></div>
    </div>
    <button class="btn btn-secondary" id="cancelBtn" style="margin-top:0">取消</button>
  `;

  document.getElementById('cancelBtn').addEventListener('click', cancelAnalysis);

  chrome.runtime.sendMessage(
    { type: 'ANALYZE_VIDEO', videoId: info.videoId, tabId: currentTab.id },
    res => {
      if (!res || res.error) {
        showError(`分析失敗：${res ? res.error : '無回應'}`);
      }
      // Job updates come via onMessage
    }
  );

  chrome.runtime.onMessage.addListener(handleJobUpdate);
}

function handleJobUpdate(msg) {
  if (msg.type === 'JOB_UPDATE') {
    const job = msg.job;
    const phase = document.getElementById('progressPhase');
    const pct = document.getElementById('progressPct');
    const fill = document.getElementById('progressFill');
    const log = document.getElementById('progressLog');

    if (phase) phase.textContent = job.phase || '處理中';
    if (pct) pct.textContent = `${job.progress || 0}%`;
    if (fill) fill.style.width = `${job.progress || 0}%`;
    if (log && job.log && job.log.length) {
      log.textContent = job.log[job.log.length - 1];
    }

    if (job.status === 'done') {
      chrome.runtime.onMessage.removeListener(handleJobUpdate);
      renderDone();
    } else if (job.status === 'error') {
      chrome.runtime.onMessage.removeListener(handleJobUpdate);
      showError(`分析失敗：${job.log ? job.log[job.log.length - 1] : '未知錯誤'}`);
    }
  }
  if (msg.type === 'JOB_ERROR') {
    chrome.runtime.onMessage.removeListener(handleJobUpdate);
    showError(`連線失敗：${msg.error}`);
  }
}

function renderDone() {
  const below = $('belowCard');
  below.innerHTML = `
    <div class="error-msg" style="background:rgba(74,222,128,.06);color:var(--green)">
      ✅ 筆記已產生並寫入 Obsidian vault！
    </div>
    <button class="btn btn-secondary" id="reloadBtn">重新整理狀態</button>
    <div class="open-server-link" style="margin-top:10px">
      <a href="#" id="openServerBtn3">打開完整介面 →</a>
    </div>
  `;
  document.getElementById('reloadBtn').addEventListener('click', () => {
    chrome.runtime.sendMessage({ type: 'GET_PAGE_INFO' });
    init();
  });
  const ob = document.getElementById('openServerBtn3');
  if (ob) ob.addEventListener('click', openServer);
}

function cancelAnalysis() {
  chrome.runtime.sendMessage({ type: 'STOP_POLLING', tabId: currentTab.id });
  chrome.runtime.onMessage.removeListener(handleJobUpdate);
  init();
}

// ── Utilities ─────────────────────────────────────────────────────────────────

function showError(msg) {
  const below = $('belowCard');
  if (below) {
    const errDiv = document.createElement('div');
    errDiv.className = 'error-msg';
    errDiv.textContent = msg;
    below.prepend(errDiv);
  }
}

function openServer() {
  chrome.storage.local.get('serverPort', data => {
    const port = data.serverPort || 7654;
    chrome.tabs.create({ url: `http://localhost:${port}` });
  });
}

function openObsidianNote(notePath) {
  if (!notePath) return;
  const vaultName = 'arthurwang_DB';
  const rel = notePath.replace(/.*arthurwang_DB\//, '');
  const uri = `obsidian://open?vault=${encodeURIComponent(vaultName)}&file=${encodeURIComponent(rel)}`;
  chrome.tabs.create({ url: uri });
}

function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ── Boot ──────────────────────────────────────────────────────────────────────
init();
