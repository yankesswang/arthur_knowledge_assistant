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

        default:
          sendResponse({ error: 'Unknown message type' });
      }
    } catch (e) {
      sendResponse({ error: e.message });
    }
  })();
  return true;
});
