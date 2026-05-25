// Content script — runs on youtube.com, extracts video metadata and relays to popup

function getVideoId() {
  const url = new URL(location.href);
  return url.searchParams.get('v') || null;
}

function getVideoTitle() {
  // Try multiple selectors — YouTube changes these occasionally
  const selectors = [
    'h1.ytd-watch-metadata yt-formatted-string',
    '#title h1 yt-formatted-string',
    '#title h1',
    'ytd-watch-metadata h1',
  ];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el && el.textContent.trim()) return el.textContent.trim();
  }
  return document.title.replace(' - YouTube', '').trim();
}

function getChannelName() {
  const selectors = [
    '#channel-name #text a',
    '#owner #channel-name a',
    'ytd-channel-name a',
  ];
  for (const sel of selectors) {
    const el = document.querySelector(sel);
    if (el && el.textContent.trim()) return el.textContent.trim();
  }
  return null;
}

function getVideoInfo() {
  return {
    videoId: getVideoId(),
    title: getVideoTitle(),
    channel: getChannelName(),
    url: location.href,
    isVideoPage: location.pathname === '/watch' && !!getVideoId(),
  };
}

// Listen for popup asking for video info
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type === 'GET_PAGE_INFO') {
    sendResponse(getVideoInfo());
  }
  return true;
});

// Notify badge update when navigating (YouTube is SPA)
let lastVideoId = null;
const observer = new MutationObserver(() => {
  const info = getVideoInfo();
  if (info.videoId !== lastVideoId) {
    lastVideoId = info.videoId;
    chrome.runtime.sendMessage({ type: 'PAGE_CHANGED', info }).catch(() => {});
  }
});
observer.observe(document.body, { childList: true, subtree: true });
