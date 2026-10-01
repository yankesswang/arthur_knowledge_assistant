const $ = id => document.getElementById(id);

async function load() {
  const data = await chrome.storage.local.get(['serverPort', 'vaultName']);
  if (data.serverPort) $('serverPort').value = data.serverPort;
  if (data.vaultName) $('vaultName').value = data.vaultName;
}

function showStatus(msg, ok) {
  const el = $('statusMsg');
  el.textContent = msg;
  el.className = 'status-msg ' + (ok ? 'ok' : 'err');
  setTimeout(() => { el.className = 'status-msg'; }, 3000);
}

$('saveBtn').addEventListener('click', async () => {
  const port = parseInt($('serverPort').value, 10);
  const vault = $('vaultName').value.trim();
  if (!port || port < 1024 || port > 65535) {
    showStatus('Port 必須在 1024–65535 之間', false);
    return;
  }
  await chrome.storage.local.set({ serverPort: port, vaultName: vault || 'arthurwang_DB' });
  showStatus('✅ 設定已儲存', true);
});

$('testBtn').addEventListener('click', async () => {
  const port = parseInt($('serverPort').value, 10) || 7654;
  try {
    const res = await fetch(`http://localhost:${port}/api/youtube/channels`, {
      signal: AbortSignal.timeout(3000),
    });
    if (res.ok) {
      showStatus(`✅ 連線成功（port ${port}）`, true);
    } else {
      showStatus(`⚠️ Server 回應 HTTP ${res.status}`, false);
    }
  } catch (e) {
    showStatus(`❌ 無法連線：${e.message}`, false);
  }
});

load();
