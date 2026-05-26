// Background service worker

const DEFAULT_PORT = 7654;

async function getServerUrl() {
  const data = await chrome.storage.local.get('serverPort');
  const port = data.serverPort || DEFAULT_PORT;
  return `http://localhost:${port}`;
}

// ── Open side panel on icon click ────────────────────────────────────────────

chrome.action.onClicked.addListener(async (tab) => {
  await chrome.sidePanel.open({ windowId: tab.windowId });
});

// ── Message handler ──────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  (async () => {
    try {
      switch (msg.type) {

        case 'GET_SERVER_URL': {
          const url = await getServerUrl();
          sendResponse({ url });
          break;
        }

        case 'GET_PAGE_INFO': {
          // Ask content script in active tab for YouTube video info
          const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (!tab || !tab.url || !tab.url.includes('youtube.com/watch')) {
            sendResponse({ isVideoPage: false });
            break;
          }
          try {
            const info = await chrome.tabs.sendMessage(tab.id, { type: 'GET_PAGE_INFO' });
            sendResponse(info);
          } catch (_) {
            sendResponse({ isVideoPage: false });
          }
          break;
        }

        // ── Native Messaging (serverless mode) ───────────────────────

        case 'NATIVE_PING': {
          try {
            const port = chrome.runtime.connectNative('com.alphanote.host');
            port.postMessage({ type: 'ping' });
            port.onMessage.addListener((m) => { sendResponse(m); port.disconnect(); });
            port.onDisconnect.addListener(() => {
              if (chrome.runtime.lastError)
                sendResponse({ error: chrome.runtime.lastError.message });
            });
          } catch (e) { sendResponse({ error: e.message }); }
          break;
        }

        case 'NATIVE_ANALYZE_YT': {
          // Fire-and-forget: stream progress via chrome.storage so sidepanel can poll
          const jobId = `native_${Date.now()}`;
          await chrome.storage.local.set({ [jobId]: { phase: '準備中', pct: 0 } });
          sendResponse({ jobId });

          const port = chrome.runtime.connectNative('com.alphanote.host');
          port.postMessage({
            type:       'analyze_yt',
            url:        msg.url,
            vault_root: msg.vault_root,
            settings:   msg.settings || {},
          });
          port.onMessage.addListener(async (m) => {
            if (m.type === 'progress') {
              await chrome.storage.local.set({ [jobId]: { phase: m.phase, pct: m.pct } });
            } else {
              await chrome.storage.local.set({ [jobId]: { ...m, done: true } });
              port.disconnect();
            }
          });
          port.onDisconnect.addListener(async () => {
            if (chrome.runtime.lastError) {
              await chrome.storage.local.set({
                [jobId]: { error: chrome.runtime.lastError.message, done: true },
              });
            }
          });
          break;
        }

        default:
          sendResponse({ error: 'Unknown message type' });
      }
    } catch (e) {
      sendResponse({ error: e.message });
    }
  })();
  return true;
});
