const $ = id => document.getElementById(id);

let serverUrl = 'http://localhost:7654';

async function getServerUrl() {
  const data = await chrome.storage.local.get('serverPort');
  const port = data.serverPort || 7654;
  return `http://localhost:${port}`;
}

// ── Connection settings ───────────────────────────────────────────────────────

async function load() {
  const data = await chrome.storage.local.get(['serverPort', 'vaultName', 'promptCustomised']);
  if (data.serverPort) $('serverPort').value = data.serverPort;
  if (data.vaultName) $('vaultName').value = data.vaultName;

  serverUrl = await getServerUrl();
  await loadOutputSettings();
  await loadPrompt();
}

// ── Output settings ───────────────────────────────────────────────────────────

function syncFolderFieldVisibility() {
  const mode = document.querySelector('input[name="outputMode"]:checked')?.value;
  $('folderPathField').style.display = mode === 'folder' ? 'block' : 'none';
}

document.querySelectorAll('input[name="outputMode"]').forEach(r => {
  r.addEventListener('change', syncFolderFieldVisibility);
});

async function loadOutputSettings() {
  try {
    const res = await fetch(`${serverUrl}/api/settings/output`, {
      signal: AbortSignal.timeout(3000),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const cfg = await res.json();
    const radio = document.querySelector(`input[name="outputMode"][value="${cfg.mode}"]`);
    if (radio) radio.checked = true;
    if (cfg.folder_path) $('folderPath').value = cfg.folder_path;
  } catch (_) {
    // server offline — leave defaults
  }
  syncFolderFieldVisibility();
}

$('saveOutputBtn').addEventListener('click', async () => {
  const mode = document.querySelector('input[name="outputMode"]:checked')?.value || 'obsidian';
  const folder_path = $('folderPath').value.trim() || '~/Documents/AlphaNote';
  try {
    const res = await fetch(`${serverUrl}/api/settings/output`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mode, folder_path }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    showStatus('outputStatusMsg', '✅ 輸出設定已儲存', true);
  } catch (e) {
    showStatus('outputStatusMsg', `❌ 儲存失敗：${e.message}`, false);
  }
});

function showStatus(elId, msg, ok) {
  const el = $(elId);
  el.textContent = msg;
  el.className = 'status-msg ' + (ok ? 'ok' : 'err');
  setTimeout(() => { el.className = 'status-msg'; }, 3500);
}

$('saveBtn').addEventListener('click', async () => {
  const port = parseInt($('serverPort').value, 10);
  const vault = $('vaultName').value.trim();
  if (!port || port < 1024 || port > 65535) {
    showStatus('statusMsg', 'Port 必須在 1024–65535 之間', false);
    return;
  }
  await chrome.storage.local.set({ serverPort: port, vaultName: vault || 'arthurwang_DB' });
  serverUrl = `http://localhost:${port}`;
  showStatus('statusMsg', '✅ 設定已儲存', true);
});

$('testBtn').addEventListener('click', async () => {
  const port = parseInt($('serverPort').value, 10) || 7654;
  try {
    const res = await fetch(`http://localhost:${port}/api/youtube/channels`, {
      signal: AbortSignal.timeout(3000),
    });
    showStatus('statusMsg', res.ok ? `✅ 連線成功（port ${port}）` : `⚠️ Server 回應 HTTP ${res.status}`, res.ok);
  } catch (e) {
    showStatus('statusMsg', `❌ 無法連線：${e.message}`, false);
  }
});

// ── Prompt editor ─────────────────────────────────────────────────────────────

async function loadPrompt() {
  try {
    const res = await fetch(`${serverUrl}/api/settings/prompt`);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const text = await res.text();
    $('promptEditor').value = text;
    await updateCustomBadge();
  } catch (e) {
    $('promptEditor').placeholder = `無法載入 prompt（${e.message}）\n請確認 server 正在運行。`;
  }
}

async function updateCustomBadge() {
  const data = await chrome.storage.local.get('promptCustomised');
  $('customBadge').className = 'custom-badge' + (data.promptCustomised ? ' visible' : '');
}

$('savePromptBtn').addEventListener('click', async () => {
  const content = $('promptEditor').value;
  try {
    const res = await fetch(`${serverUrl}/api/settings/prompt`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    await chrome.storage.local.set({ promptCustomised: true });
    $('customBadge').className = 'custom-badge visible';
    showStatus('promptStatusMsg', '✅ Prompt 已儲存，下次分析生效', true);
  } catch (e) {
    showStatus('promptStatusMsg', `❌ 儲存失敗：${e.message}`, false);
  }
});

$('reloadPromptBtn').addEventListener('click', async () => {
  await loadPrompt();
  showStatus('promptStatusMsg', '🔄 已重新載入', true);
});

$('resetPromptBtn').addEventListener('click', async () => {
  if (!confirm('確定要恢復預設 prompt？自訂內容將清除。')) return;
  try {
    await fetch(`${serverUrl}/api/settings/prompt`, { method: 'DELETE' });
    await chrome.storage.local.set({ promptCustomised: false });
    $('customBadge').className = 'custom-badge';
    await loadPrompt();
    showStatus('promptStatusMsg', '✅ 已恢復預設 prompt', true);
  } catch (e) {
    showStatus('promptStatusMsg', `❌ 重設失敗：${e.message}`, false);
  }
});

load();
