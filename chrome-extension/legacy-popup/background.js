// Background service worker — handles all API calls to localhost:7654

const DEFAULT_PORT = 7654;

async function getServerUrl() {
  const data = await chrome.storage.local.get('serverPort');
  const port = data.serverPort || DEFAULT_PORT;
  return `http://localhost:${port}`;
}

// ── API helpers ──────────────────────────────────────────────────────────────

async function apiGet(path) {
  const base = await getServerUrl();
  const res = await fetch(`${base}${path}`);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function apiPost(path, body = {}) {
  const base = await getServerUrl();
  const res = await fetch(`${base}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Job polling ───────────────────────────────────────────────────────────────

const activePolls = new Map(); // tabId → intervalId

function startPolling(tabId, jobId) {
  stopPolling(tabId);
  const id = setInterval(async () => {
    try {
      const job = await apiGet(`/api/jobs/${jobId}`);
      chrome.runtime.sendMessage({ type: 'JOB_UPDATE', tabId, job }).catch(() => {});
      if (job.status === 'done' || job.status === 'error') {
        stopPolling(tabId);
      }
    } catch (e) {
      chrome.runtime.sendMessage({ type: 'JOB_ERROR', tabId, error: e.message }).catch(() => {});
    }
  }, 2000);
  activePolls.set(tabId, id);
}

function stopPolling(tabId) {
  if (activePolls.has(tabId)) {
    clearInterval(activePolls.get(tabId));
    activePolls.delete(tabId);
  }
}

// ── Message handler ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.type) {

        case 'CHECK_SERVER': {
          const base = await getServerUrl();
          const res = await fetch(`${base}/api/youtube/channels`, { signal: AbortSignal.timeout(3000) });
          sendResponse({ ok: res.ok });
          break;
        }

        case 'GET_VIDEO_STATUS': {
          // Check if video already has a transcript / note
          const { videoId } = msg;
          const channels = await apiGet('/api/youtube/channels');
          let found = null;
          for (const ch of channels) {
            const vid = (ch.videos || []).find(v => v.video_id === videoId);
            if (vid) { found = vid; break; }
          }
          // Also try direct note endpoint
          if (!found) {
            try {
              const note = await apiGet(`/api/youtube/videos/${videoId}/note`);
              found = note;
            } catch (_) {}
          }
          sendResponse({ video: found });
          break;
        }

        case 'ANALYZE_VIDEO': {
          const { videoId, tabId } = msg;
          // Enqueue if not already queued
          try {
            await apiPost('/api/youtube/queue', { url: `https://www.youtube.com/watch?v=${videoId}` });
          } catch (_) {}
          // Trigger analysis
          const result = await apiPost(`/api/youtube/videos/${videoId}/analyze`);
          const jobId = result.job_id;
          if (jobId) {
            startPolling(tabId, jobId);
            sendResponse({ ok: true, jobId });
          } else {
            sendResponse({ ok: false, error: 'No job_id returned' });
          }
          break;
        }

        case 'STOP_POLLING': {
          stopPolling(msg.tabId);
          sendResponse({ ok: true });
          break;
        }

        case 'GET_INBOX': {
          const inbox = await apiGet('/api/inbox');
          sendResponse({ inbox });
          break;
        }

        case 'DISMISS_INBOX': {
          await apiPost(`/api/inbox/${msg.itemId}/dismiss`);
          sendResponse({ ok: true });
          break;
        }

        default:
          sendResponse({ error: 'Unknown message type' });
      }
    } catch (e) {
      sendResponse({ error: e.message });
    }
  })();
  return true; // keep channel open for async
});
