import { writeFile, mkdir } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import process from 'node:process';

// ============================================================================
// Constants
// ============================================================================

const GEMINI_MODEL = process.env.GEMINI_MODEL || 'gemini-2.5-flash';
const FEED_FETCH_TIMEOUT_MS = 15_000;
const ARTICLE_FETCH_TIMEOUT_MS = 20_000;
const FEED_CONCURRENCY = 4;
const ARTICLE_CONCURRENCY = 5;
const GEMINI_BATCH_SIZE = 5;
const MAX_CONCURRENT_GEMINI = 1;

// Obsidian vault path — override with OBSIDIAN_VAULT_PATH env var
const OBSIDIAN_VAULT = process.env.OBSIDIAN_VAULT_PATH || '/Users/yankesswang/Documents/arthurwang_DB';
const OBSIDIAN_DIGEST_FOLDER = 'Finance Digest';

// Source name → Obsidian folder name mapping
const SOURCE_FOLDER: Record<string, string> = {
  'FOMO SOC':        'Finance Digest/FOMO SOC',
  'Vincent Yu':      'Finance Digest/Vincent Yu',
  'Market Viewpoint': 'Finance Digest/M報',
  'Vicky Ho':        'Finance Digest/Vicky Ho',
};

const RSS_FEEDS: Array<{ name: string; xmlUrl: string; htmlUrl: string }> = [
  { name: "FOMO SOC", xmlUrl: "https://fomosoc.substack.com/feed", htmlUrl: "https://fomosoc.substack.com" },
  { name: "Vincent Yu", xmlUrl: "https://vincentcwyu.substack.com/feed", htmlUrl: "https://vincentcwyu.substack.com" },
  { name: "Market Viewpoint", xmlUrl: "https://mviewpoint.substack.com/feed", htmlUrl: "https://mviewpoint.substack.com" },
  { name: "Vicky Ho", xmlUrl: "https://vickyho.substack.com/feed", htmlUrl: "https://vickyho.substack.com" },
];

function localDateString(date = new Date()): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// ============================================================================
// Types
// ============================================================================

type CategoryId = 'macro' | 'stocks' | 'crypto' | 'strategy' | 'opinion' | 'other';

const CATEGORY_META: Record<CategoryId, { emoji: string; label: string }> = {
  'macro':    { emoji: '🌍', label: '總經 / 政策' },
  'stocks':   { emoji: '📈', label: '股市 / 個股' },
  'crypto':   { emoji: '₿', label: '加密貨幣' },
  'strategy': { emoji: '🎯', label: '投資策略' },
  'opinion':  { emoji: '💡', label: '觀點 / 雜談' },
  'other':    { emoji: '📝', label: '其他' },
};

interface Article {
  title: string;
  link: string;
  pubDate: Date;
  description: string;
  fullContent: string;       // full scraped text
  sourceName: string;
  sourceUrl: string;
  obsidianNote?: string;     // saved note filename (without .md)
}

interface ScoredArticle extends Article {
  score: number;
  scoreBreakdown: {
    relevance: number;
    quality: number;
    timeliness: number;
  };
  category: CategoryId;
  keywords: string[];
  titleZh: string;
  summary: string;
  reason: string;
}

interface GeminiScoringResult {
  results: Array<{
    index: number;
    relevance: number;
    quality: number;
    timeliness: number;
    category: string;
    keywords: string[];
  }>;
}

interface GeminiSummaryResult {
  results: Array<{
    index: number;
    titleZh: string;
    summary: string;
    reason: string;
  }>;
}

// ============================================================================
// RSS/Atom Parsing
// ============================================================================

function decodeEntities(html: string): string {
  return html
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&#(\d+);/g, (_, code) => String.fromCharCode(parseInt(code)));
}

function stripHtml(html: string): string {
  return decodeEntities(html.replace(/<[^>]*>/g, ''))
    .replace(/\s{3,}/g, '\n\n')
    .trim();
}

// Convert HTML to Markdown, preserving images, headings, links, and formatting
function htmlToMarkdown(html: string): string {
  let md = html;

  // Remove script/style blocks entirely
  md = md.replace(/<script[\s\S]*?<\/script>/gi, '');
  md = md.replace(/<style[\s\S]*?<\/style>/gi, '');

  // Headings
  md = md.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, (_, t) => `\n\n# ${stripHtml(t)}\n\n`);
  md = md.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, (_, t) => `\n\n## ${stripHtml(t)}\n\n`);
  md = md.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, (_, t) => `\n\n### ${stripHtml(t)}\n\n`);
  md = md.replace(/<h[456][^>]*>([\s\S]*?)<\/h[456]>/gi, (_, t) => `\n\n#### ${stripHtml(t)}\n\n`);

  // Images — keep as Markdown image syntax (remote URL, no download needed)
  md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*alt=["']([^"']*)["'][^>]*\/?>/gi,
    (_, src, alt) => `\n\n![${alt || ''}](${src})\n\n`);
  md = md.replace(/<img[^>]+alt=["']([^"']*)["'][^>]+src=["']([^"']+)["'][^>]*\/?>/gi,
    (_, alt, src) => `\n\n![${alt || ''}](${src})\n\n`);
  // img tags without alt
  md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*\/?>/gi,
    (_, src) => `\n\n![](${src})\n\n`);

  // Block elements
  md = md.replace(/<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi,
    (_, t) => `\n\n> ${stripHtml(t).split('\n').join('\n> ')}\n\n`);
  md = md.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, (_, t) => `\n- ${stripHtml(t)}`);
  md = md.replace(/<\/?(ul|ol)[^>]*>/gi, '\n');
  md = md.replace(/<p[^>]*>([\s\S]*?)<\/p>/gi, (_, t) => `\n\n${stripHtml(t)}\n\n`);
  md = md.replace(/<br\s*\/?>/gi, '\n');
  md = md.replace(/<hr\s*\/?>/gi, '\n\n---\n\n');

  // Inline formatting
  md = md.replace(/<strong[^>]*>([\s\S]*?)<\/strong>/gi, (_, t) => `**${stripHtml(t)}**`);
  md = md.replace(/<b[^>]*>([\s\S]*?)<\/b>/gi, (_, t) => `**${stripHtml(t)}**`);
  md = md.replace(/<em[^>]*>([\s\S]*?)<\/em>/gi, (_, t) => `*${stripHtml(t)}*`);
  md = md.replace(/<i[^>]*>([\s\S]*?)<\/i>/gi, (_, t) => `*${stripHtml(t)}*`);
  md = md.replace(/<code[^>]*>([\s\S]*?)<\/code>/gi, (_, t) => `\`${stripHtml(t)}\``);
  md = md.replace(/<a[^>]+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi,
    (_, href, text) => `[${stripHtml(text)}](${href})`);

  // Strip remaining tags
  md = md.replace(/<[^>]*>/g, '');

  return decodeEntities(md)
    .replace(/\n{4,}/g, '\n\n\n')
    .trim();
}

function extractCDATA(text: string): string {
  const cdataMatch = text.match(/<!\[CDATA\[([\s\S]*?)\]\]>/);
  return cdataMatch ? cdataMatch[1] : text;
}

function getTagContent(xml: string, tagName: string): string {
  const patterns = [
    new RegExp(`<${tagName}[^>]*>([\\s\\S]*?)</${tagName}>`, 'i'),
    new RegExp(`<${tagName}[^>]*/>`, 'i'),
  ];
  for (const pattern of patterns) {
    const match = xml.match(pattern);
    if (match?.[1]) {
      return extractCDATA(match[1]).trim();
    }
  }
  return '';
}

function getAttrValue(xml: string, tagName: string, attrName: string): string {
  const pattern = new RegExp(`<${tagName}[^>]*\\s${attrName}=["']([^"']*)["'][^>]*/?>`, 'i');
  const match = xml.match(pattern);
  return match?.[1] || '';
}

function parseDate(dateStr: string): Date | null {
  if (!dateStr) return null;
  const d = new Date(dateStr);
  if (!isNaN(d.getTime())) return d;
  return null;
}

function parseRSSItems(xml: string): Array<{ title: string; link: string; pubDate: string; description: string }> {
  const items: Array<{ title: string; link: string; pubDate: string; description: string }> = [];

  const isAtom = (xml.includes('<feed') && xml.includes('xmlns="http://www.w3.org/2005/Atom"')) || xml.includes('<feed ');

  if (isAtom) {
    const entryPattern = /<entry[\s>]([\s\S]*?)<\/entry>/gi;
    let entryMatch;
    while ((entryMatch = entryPattern.exec(xml)) !== null) {
      const entryXml = entryMatch[1];
      const title = stripHtml(getTagContent(entryXml, 'title'));
      let link = getAttrValue(entryXml, 'link[^>]*rel="alternate"', 'href');
      if (!link) link = getAttrValue(entryXml, 'link', 'href');
      const pubDate = getTagContent(entryXml, 'published') || getTagContent(entryXml, 'updated');
      const description = stripHtml(
        getTagContent(entryXml, 'summary') || getTagContent(entryXml, 'content')
      );
      if (title || link) {
        items.push({ title, link, pubDate, description: description.slice(0, 1000) });
      }
    }
  } else {
    const itemPattern = /<item[\s>]([\s\S]*?)<\/item>/gi;
    let itemMatch;
    while ((itemMatch = itemPattern.exec(xml)) !== null) {
      const itemXml = itemMatch[1];
      const title = stripHtml(getTagContent(itemXml, 'title'));
      const link = getTagContent(itemXml, 'link') || getTagContent(itemXml, 'guid');
      const pubDate = getTagContent(itemXml, 'pubDate') || getTagContent(itemXml, 'dc:date') || getTagContent(itemXml, 'date');
      const description = stripHtml(
        getTagContent(itemXml, 'description') || getTagContent(itemXml, 'content:encoded')
      );
      if (title || link) {
        items.push({ title, link, pubDate, description: description.slice(0, 1000) });
      }
    }
  }

  return items;
}

// ============================================================================
// Feed Fetching
// ============================================================================

async function fetchFeed(feed: { name: string; xmlUrl: string; htmlUrl: string }): Promise<Article[]> {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), FEED_FETCH_TIMEOUT_MS);

    const response = await fetch(feed.xmlUrl, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Newsletter-Digest/1.0 (RSS Reader)',
        'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
      },
    });

    clearTimeout(timeout);

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const xml = await response.text();
    const items = parseRSSItems(xml);

    return items.map(item => ({
      title: item.title,
      link: item.link,
      pubDate: parseDate(item.pubDate) || new Date(0),
      description: item.description,
      fullContent: '',
      sourceName: feed.name,
      sourceUrl: feed.htmlUrl,
    }));
  } catch (error) {
    const msg = error instanceof Error ? error.message : String(error);
    console.warn(`[digest] ✗ ${feed.name}: ${msg.includes('abort') ? 'timeout' : msg}`);
    return [];
  }
}

async function fetchAllFeeds(feeds: typeof RSS_FEEDS): Promise<Article[]> {
  const allArticles: Article[] = [];
  let successCount = 0;
  let failCount = 0;

  for (let i = 0; i < feeds.length; i += FEED_CONCURRENCY) {
    const batch = feeds.slice(i, i + FEED_CONCURRENCY);
    const results = await Promise.allSettled(batch.map(fetchFeed));

    for (const result of results) {
      if (result.status === 'fulfilled' && result.value.length > 0) {
        allArticles.push(...result.value);
        successCount++;
      } else {
        failCount++;
      }
    }
  }

  console.log(`[digest] Fetched ${allArticles.length} articles from ${successCount} feeds (${failCount} failed)`);
  return allArticles;
}

// ============================================================================
// Full Article Content Scraping
// ============================================================================

// Remove a block element (and all its nested children) starting at `startIdx` in html.
// Handles nested tags so we don't stop at the first inner </tag>.
function removeNestedBlock(html: string, startIdx: number, tag: string): string {
  const openRe = new RegExp(`<${tag}(\\s[^>]*)?>`, 'gi');
  const closeRe = new RegExp(`</${tag}>`, 'gi');

  // find the matching closing tag by counting depth
  let depth = 1;
  let pos = startIdx;

  // skip past the opening tag itself
  const firstClose = html.indexOf('>', startIdx);
  if (firstClose === -1) return html;
  pos = firstClose + 1;

  while (pos < html.length && depth > 0) {
    openRe.lastIndex = pos;
    closeRe.lastIndex = pos;
    const nextOpen = openRe.exec(html);
    const nextClose = closeRe.exec(html);

    if (!nextClose) break;

    if (nextOpen && nextOpen.index < nextClose.index) {
      depth++;
      pos = nextOpen.index + nextOpen[0].length;
    } else {
      depth--;
      pos = nextClose.index + nextClose[0].length;
    }
  }

  return html.slice(0, startIdx) + html.slice(pos);
}

// Repeatedly strip all matching blocks (handles multiple occurrences)
function removeAllMatchingBlocks(html: string, pattern: RegExp, tag: string): string {
  let result = html;
  let match: RegExpExecArray | null;
  pattern.lastIndex = 0;

  // Collect start positions first (right-to-left removal to preserve indices)
  const starts: number[] = [];
  while ((match = pattern.exec(result)) !== null) {
    starts.push(match.index);
    pattern.lastIndex = match.index + 1; // avoid infinite loop on zero-width
  }

  // Remove from last to first so earlier indices stay valid
  for (let i = starts.length - 1; i >= 0; i--) {
    result = removeNestedBlock(result, starts[i]!, tag);
  }
  return result;
}

// Remove Substack paywall/subscribe blocks before parsing
function removeSubscribeWalls(html: string): string {
  let result = html;

  // subscription-widget-wrap — outermost wrapper (contains preamble text + form)
  result = removeAllMatchingBlocks(result, /<div[^>]+class="[^"]*subscription-widget-wrap[^"]*"[^>]*>/gi, 'div');

  // data-component-name="SubscribeWidget" — injected inline mid-article
  result = removeAllMatchingBlocks(result, /<div[^>]+data-component-name="SubscribeWidget"[^>]*>/gi, 'div');

  // class="subscribe-widget" (exact Substack class)
  result = removeAllMatchingBlocks(result, /<div[^>]+class="[^"]*subscribe-widget[^"]*"[^>]*>/gi, 'div');

  // paywall / truncation containers
  result = removeAllMatchingBlocks(result, /<div[^>]+class="[^"]*paywall[^"]*"[^>]*>/gi, 'div');
  result = removeAllMatchingBlocks(result, /<div[^>]+class="[^"]*truncat[^"]*"[^>]*>/gi, 'div');

  // subscription CTA sections
  result = removeAllMatchingBlocks(result, /<div[^>]+class="[^"]*(?:subscription|subscribe)-cta[^"]*"[^>]*>/gi, 'div');
  result = removeAllMatchingBlocks(result, /<section[^>]+class="[^"]*subscri[^"]*"[^>]*>/gi, 'section');

  // noncontributor CTA button
  result = result.replace(/<button[^>]+data-testid="noncontributor-cta-button"[^>]*>[\s\S]*?<\/button>/gi, '');

  return result;
}

// Extract the full inner content of the first matching tag using depth tracking
function extractNestedContent(html: string, openPattern: RegExp): string | null {
  openPattern.lastIndex = 0;
  const opening = openPattern.exec(html);
  if (!opening) return null;

  const afterOpen = opening.index + opening[0].length;

  // Determine the tag name from the match
  const tagMatch = opening[0].match(/^<([a-zA-Z][a-zA-Z0-9]*)/);
  const tag = tagMatch?.[1]?.toLowerCase() ?? 'div';

  const openRe = new RegExp(`<${tag}(\\s[^>]*)?>`, 'gi');
  const closeRe = new RegExp(`</${tag}>`, 'gi');

  let depth = 1;
  let pos = afterOpen;

  while (pos < html.length && depth > 0) {
    openRe.lastIndex = pos;
    closeRe.lastIndex = pos;
    const nextOpen = openRe.exec(html);
    const nextClose = closeRe.exec(html);

    if (!nextClose) break;

    if (nextOpen && nextOpen.index < nextClose.index) {
      depth++;
      pos = nextOpen.index + nextOpen[0].length;
    } else {
      depth--;
      if (depth === 0) {
        // Return inner content (between opening and closing tag)
        return html.slice(afterOpen, nextClose.index);
      }
      pos = nextClose.index + nextClose[0].length;
    }
  }

  // Depth never closed — return everything after opening tag as fallback
  return html.slice(afterOpen);
}

function extractSubstackContent(html: string): string {
  const cleaned = removeSubscribeWalls(html);

  // Priority order: most specific Substack containers first
  const candidates = [
    // <div class="available-content"> — wraps freely visible article content
    /<div[^>]+class="[^"]*available-content[^"]*"[^>]*>/i,
    // <div class="body markup"> — direct article body
    /<div[^>]+class="[^"]*body\s+markup[^"]*"[^>]*>/i,
    // <div class="post-content">
    /<div[^>]+class="[^"]*post-content[^"]*"[^>]*>/i,
    // <article>
    /<article[^>]*>/i,
  ];

  for (const pattern of candidates) {
    const inner = extractNestedContent(cleaned, pattern);
    if (inner) {
      const md = htmlToMarkdown(inner);
      if (md.length > 200) return md;
    }
  }

  // Fallback: full body
  const bodyInner = extractNestedContent(cleaned, /<body[^>]*>/i);
  if (bodyInner) return htmlToMarkdown(bodyInner);

  return htmlToMarkdown(cleaned);
}

async function fetchArticleContent(article: Article): Promise<string> {
  if (!article.link || !article.link.startsWith('http')) return '';

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), ARTICLE_FETCH_TIMEOUT_MS);

    const response = await fetch(article.link, {
      signal: controller.signal,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'zh-TW,zh;q=0.9,en;q=0.8',
      },
    });

    clearTimeout(timeout);

    if (!response.ok) return '';

    const html = await response.text();
    return extractSubstackContent(html);
  } catch {
    return '';
  }
}

async function fetchAllArticleContents(articles: Article[]): Promise<Article[]> {
  const results: Article[] = [...articles];

  console.log(`[digest] Fetching full content for ${articles.length} articles...`);

  for (let i = 0; i < articles.length; i += ARTICLE_CONCURRENCY) {
    const batch = articles.slice(i, i + ARTICLE_CONCURRENCY);
    const contents = await Promise.all(batch.map(fetchArticleContent));

    for (let j = 0; j < batch.length; j++) {
      const idx = i + j;
      results[idx] = { ...results[idx], fullContent: contents[j] };
    }

    const progress = Math.min(i + ARTICLE_CONCURRENCY, articles.length);
    process.stdout.write(`\r[digest] Content progress: ${progress}/${articles.length}`);
  }
  console.log('');

  const withContent = results.filter(a => a.fullContent.length > 100).length;
  console.log(`[digest] Got full content for ${withContent}/${articles.length} articles`);

  return results;
}

// ============================================================================
// Obsidian Note Saving
// ============================================================================

function sanitizeFilename(name: string): string {
  return name
    .replace(/[/\\:*?"<>|#^[\]]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 80);
}

function formatObsidianNote(article: Article, dateStr: string): string {
  const pubDateStr = article.pubDate.getTime() > 0
    ? article.pubDate.toISOString().split('T')[0]
    : dateStr;
  const pubTimeStr = article.pubDate.getTime() > 0
    ? article.pubDate.toISOString().replace('T', ' ').slice(0, 16) + ' UTC'
    : dateStr;

  const content = article.fullContent || article.description || '（無法取得完整內容）';

  const frontmatter = [
    '---',
    `title: "${article.title.replace(/"/g, "'")}"`,
    `source: "${article.sourceName}"`,
    `url: "${article.link}"`,
    `date: ${pubDateStr}`,
    `fetched: ${dateStr}`,
    `tags:`,
    `  - finance-digest`,
    `  - ${article.sourceName.toLowerCase().replace(/\s+/g, '-')}`,
    '---',
    '',
  ].join('\n');

  const header =
    `# ${article.title}\n\n` +
    `| 欄位 | 內容 |\n` +
    `|---|---|\n` +
    `| 來源 | [${article.sourceName}](${article.sourceUrl}) |\n` +
    `| 發布時間 | ${pubTimeStr} |\n` +
    `| 擷取日期 | ${dateStr} |\n` +
    `| 原文連結 | [閱讀原文](${article.link}) |\n\n` +
    `---\n\n`;

  return frontmatter + header + content;
}

async function saveArticleNotes(articles: Article[], dateStr: string): Promise<Article[]> {
  const results: Article[] = [];

  for (const article of articles) {
    const sourceFolder = SOURCE_FOLDER[article.sourceName] ?? `Finance Digest/${sanitizeFilename(article.sourceName)}`;
    const folderPath = join(OBSIDIAN_VAULT, sourceFolder);
    await mkdir(folderPath, { recursive: true });

    const noteName = sanitizeFilename(article.title);
    const filePath = join(folderPath, `${noteName}.md`);
    const noteContent = formatObsidianNote(article, dateStr);

    try {
      await writeFile(filePath, noteContent);
      results.push({ ...article, obsidianNote: `${sourceFolder}/${noteName}` });
    } catch (error) {
      console.warn(`[digest] Failed to save note: ${noteName} — ${error}`);
      results.push(article);
    }
  }

  console.log(`[digest] Saved ${results.filter(a => a.obsidianNote).length} article notes to Obsidian`);
  return results;
}

// ============================================================================
// Gemini API
// ============================================================================

async function callGemini(prompt: string, apiKey: string): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent?key=${apiKey}`;

  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: prompt }] }],
      generationConfig: { temperature: 0.3, topP: 0.8 },
    }),
  });

  if (!response.ok) {
    const errorText = await response.text().catch(() => 'Unknown error');
    throw new Error(`Gemini API error (${response.status}): ${errorText}`);
  }

  const data = await response.json() as {
    candidates?: Array<{ content?: { parts?: Array<{ text?: string }> } }>;
  };

  return data.candidates?.[0]?.content?.parts?.[0]?.text || '';
}

function parseJsonResponse<T>(text: string): T {
  let jsonText = text.trim();
  if (jsonText.startsWith('```')) {
    jsonText = jsonText.replace(/^```(?:json)?\n?/, '').replace(/\n?```$/, '');
  }
  return JSON.parse(jsonText) as T;
}

// ============================================================================
// AI Scoring
// ============================================================================

function buildScoringPrompt(articles: Array<{ index: number; title: string; content: string; sourceName: string }>): string {
  const articlesList = articles.map(a =>
    `Index ${a.index}: [${a.sourceName}] ${a.title}\n${a.content.slice(0, 400)}`
  ).join('\n\n---\n\n');

  return `你是一位財經內容策展人，正在為一份面向投資者與財經愛好者的每日精選摘要篩選文章。

請對以下文章進行三個維度的評分（1-10 整數，10 分最高），並為每篇文章分配一個分類標籤和提取 2-4 個關鍵詞。

## 評分維度

### 1. 相關性 (relevance) - 對投資者或財經從業者的實用價值
- 10: 重大市場事件、政策轉向、必看的投資洞見
- 7-9: 對大多數投資者有參考價值
- 4-6: 對特定市場或資產類別有價值
- 1-3: 與投資/財經關聯不大

### 2. 質量 (quality) - 文章本身的深度和分析品質
- 10: 深度分析，有獨到觀點，論據充分
- 7-9: 有深度，觀點清晰
- 4-6: 資訊準確，表達清晰
- 1-3: 淺嚐即止或純轉述新聞

### 3. 時效性 (timeliness) - 當前是否值得閱讀
- 10: 正在發生的重大市場事件或政策變動
- 7-9: 近期市場熱點相關
- 4-6: 長青投資觀念，不過時
- 1-3: 過時或無時效價值

## 分類標籤（必須從以下選一個）
- macro: 總體經濟、Fed 政策、利率、通膨、地緣政治
- stocks: 股市、個股分析、產業研究、財報
- crypto: 加密貨幣、區塊鏈、DeFi、NFT
- strategy: 投資策略、資產配置、風險管理、選股方法
- opinion: 市場觀點、個人思考、投資哲學、書評
- other: 以上都不太適合的

## 關鍵詞提取
提取 2-4 個最能代表文章主題的關鍵詞（可中英混用，如 "Fed", "降息", "比特幣", "AI stocks"）

## 待評分文章

${articlesList}

請嚴格按 JSON 格式回傳，不要包含 markdown 程式碼區塊或其他文字：
{
  "results": [
    {
      "index": 0,
      "relevance": 8,
      "quality": 7,
      "timeliness": 9,
      "category": "macro",
      "keywords": ["Fed", "降息", "美債"]
    }
  ]
}`;
}

async function scoreArticlesWithAI(
  articles: Article[],
  apiKey: string
): Promise<Map<number, { relevance: number; quality: number; timeliness: number; category: CategoryId; keywords: string[] }>> {
  const allScores = new Map<number, { relevance: number; quality: number; timeliness: number; category: CategoryId; keywords: string[] }>();

  const indexed = articles.map((article, index) => ({
    index,
    title: article.title,
    // Use full content if available, otherwise fallback to description
    content: article.fullContent || article.description,
    sourceName: article.sourceName,
  }));

  const batches: typeof indexed[] = [];
  for (let i = 0; i < indexed.length; i += GEMINI_BATCH_SIZE) {
    batches.push(indexed.slice(i, i + GEMINI_BATCH_SIZE));
  }

  console.log(`[digest] AI scoring: ${articles.length} articles in ${batches.length} batches`);

  const validCategories = new Set<string>(['macro', 'stocks', 'crypto', 'strategy', 'opinion', 'other']);

  for (let i = 0; i < batches.length; i += MAX_CONCURRENT_GEMINI) {
    const batchGroup = batches.slice(i, i + MAX_CONCURRENT_GEMINI);
    const promises = batchGroup.map(async (batch) => {
      try {
        const prompt = buildScoringPrompt(batch);
        const responseText = await callGemini(prompt, apiKey);
        const parsed = parseJsonResponse<GeminiScoringResult>(responseText);

        if (parsed.results && Array.isArray(parsed.results)) {
          for (const result of parsed.results) {
            const clamp = (v: number) => Math.min(10, Math.max(1, Math.round(v)));
            const cat = (validCategories.has(result.category) ? result.category : 'other') as CategoryId;
            allScores.set(result.index, {
              relevance: clamp(result.relevance),
              quality: clamp(result.quality),
              timeliness: clamp(result.timeliness),
              category: cat,
              keywords: Array.isArray(result.keywords) ? result.keywords.slice(0, 4) : [],
            });
          }
        }
      } catch (error) {
        console.warn(`[digest] Scoring batch failed: ${error instanceof Error ? error.message : String(error)}`);
        for (const item of batch) {
          allScores.set(item.index, { relevance: 5, quality: 5, timeliness: 5, category: 'other', keywords: [] });
        }
      }
    });

    await Promise.all(promises);
    console.log(`[digest] Scoring progress: ${Math.min(i + MAX_CONCURRENT_GEMINI, batches.length)}/${batches.length} batches`);
  }

  return allScores;
}

// ============================================================================
// AI Summarization
// ============================================================================

function buildSummaryPrompt(
  articles: Array<{ index: number; title: string; content: string; sourceName: string; link: string }>,
  lang: 'zh' | 'en'
): string {
  const articlesList = articles.map(a =>
    `Index ${a.index}: [${a.sourceName}] ${a.title}\nURL: ${a.link}\n${a.content.slice(0, 1500)}`
  ).join('\n\n---\n\n');

  const langInstruction = lang === 'zh'
    ? '請使用繁體中文撰寫摘要和推薦理由。如果原文是英文，請翻譯為繁體中文。標題翻譯也使用繁體中文。'
    : 'Write summaries, reasons, and title translations in English.';

  return `你是一位財經內容摘要專家。請為以下文章完成三件事：

1. **繁體中文標題** (titleZh): 將標題翻譯或整理成自然的繁體中文。如果原標題已是中文則保持並轉為繁體。
2. **摘要** (summary): 4-6 句話的結構化摘要，讓讀者不點進原文也能了解核心觀點。包含：
   - 作者討論的核心市場問題或主題（1 句）
   - 關鍵論點、數據或市場判斷（2-3 句）
   - 作者的結論或行動建議（1 句）
3. **推薦理由** (reason): 1 句話說明「為什麼現在值得讀」，聚焦當下市場環境的相關性。

${langInstruction}

摘要要求：
- 直接說重點，不要用「本文討論了⋯」這種開頭
- 保留具體的市場數據、指數點位、漲跌幅、時間節點
- 如果有明確的投資觀點（看多/看空），要點出來
- 如果有提到具體標的（股票、ETF、幣種），要保留
- 目標：讀者花 30 秒讀完摘要，就能決定是否值得讀原文

## 待摘要文章

${articlesList}

請嚴格按 JSON 格式回傳：
{
  "results": [
    {
      "index": 0,
      "titleZh": "繁體中文標題",
      "summary": "摘要內容...",
      "reason": "推薦理由..."
    }
  ]
}`;
}

async function summarizeArticles(
  articles: Array<Article & { index: number }>,
  apiKey: string,
  lang: 'zh' | 'en'
): Promise<Map<number, { titleZh: string; summary: string; reason: string }>> {
  const summaries = new Map<number, { titleZh: string; summary: string; reason: string }>();

  const indexed = articles.map(a => ({
    index: a.index,
    title: a.title,
    content: a.fullContent || a.description,
    sourceName: a.sourceName,
    link: a.link,
  }));

  const batches: typeof indexed[] = [];
  for (let i = 0; i < indexed.length; i += GEMINI_BATCH_SIZE) {
    batches.push(indexed.slice(i, i + GEMINI_BATCH_SIZE));
  }

  console.log(`[digest] Generating summaries for ${articles.length} articles in ${batches.length} batches`);

  for (let i = 0; i < batches.length; i += MAX_CONCURRENT_GEMINI) {
    const batchGroup = batches.slice(i, i + MAX_CONCURRENT_GEMINI);
    const promises = batchGroup.map(async (batch) => {
      try {
        const prompt = buildSummaryPrompt(batch, lang);
        const responseText = await callGemini(prompt, apiKey);
        const parsed = parseJsonResponse<GeminiSummaryResult>(responseText);

        if (parsed.results && Array.isArray(parsed.results)) {
          for (const result of parsed.results) {
            summaries.set(result.index, {
              titleZh: result.titleZh || '',
              summary: result.summary || '',
              reason: result.reason || '',
            });
          }
        }
      } catch (error) {
        console.warn(`[digest] Summary batch failed: ${error instanceof Error ? error.message : String(error)}`);
        for (const item of batch) {
          summaries.set(item.index, { titleZh: item.title, summary: '', reason: '' });
        }
      }
    });

    await Promise.all(promises);
    console.log(`[digest] Summary progress: ${Math.min(i + MAX_CONCURRENT_GEMINI, batches.length)}/${batches.length} batches`);
  }

  return summaries;
}

// ============================================================================
// AI Highlights (Market Pulse)
// ============================================================================

async function generateHighlights(
  articles: ScoredArticle[],
  apiKey: string,
  lang: 'zh' | 'en'
): Promise<string> {
  const articleList = articles.slice(0, 10).map((a, i) =>
    `${i + 1}. [${a.category}] ${a.titleZh || a.title} — ${a.summary.slice(0, 150)}`
  ).join('\n');

  const langNote = lang === 'zh' ? '請使用繁體中文回答。' : 'Write in English.';

  const prompt = `根據以下今日精選財經文章列表，寫一段 3-5 句話的「市場脈動」總結。
要求：
- 提煉出今天這些作者共同關注的 2-3 個市場主題或趨勢
- 如果各作者觀點有分歧，要點出分歧所在
- 不要逐篇列舉，要做宏觀歸納
- 風格簡潔有力，像財經媒體的市場早報導語
${langNote}

文章列表：
${articleList}

直接返回純文字總結，不要 JSON，不要 markdown 格式。`;

  try {
    const text = await callGemini(prompt, apiKey);
    return text.trim();
  } catch (error) {
    console.warn(`[digest] Highlights generation failed: ${error instanceof Error ? error.message : String(error)}`);
    return '';
  }
}

// ============================================================================
// Visualization Helpers
// ============================================================================

function humanizeTime(pubDate: Date): string {
  const diffMs = Date.now() - pubDate.getTime();
  const diffMins = Math.floor(diffMs / 60_000);
  const diffHours = Math.floor(diffMs / 3_600_000);
  const diffDays = Math.floor(diffMs / 86_400_000);

  if (diffMins < 60) return `${diffMins} 分鐘前`;
  if (diffHours < 24) return `${diffHours} 小時前`;
  if (diffDays < 7) return `${diffDays} 天前`;
  return pubDate.toISOString().slice(0, 10);
}

function generateCategoryPieChart(articles: ScoredArticle[]): string {
  const catCount = new Map<CategoryId, number>();
  for (const a of articles) catCount.set(a.category, (catCount.get(a.category) || 0) + 1);
  if (catCount.size === 0) return '';

  const sorted = Array.from(catCount.entries()).sort((a, b) => b[1] - a[1]);
  let chart = '```mermaid\npie showData\n    title "文章分類分佈"\n';
  for (const [cat, count] of sorted) {
    const meta = CATEGORY_META[cat];
    chart += `    "${meta.emoji} ${meta.label}" : ${count}\n`;
  }
  return chart + '```\n';
}

function generateTagCloud(articles: ScoredArticle[]): string {
  const kwCount = new Map<string, number>();
  for (const a of articles) {
    for (const kw of a.keywords) {
      const normalized = kw.toLowerCase();
      kwCount.set(normalized, (kwCount.get(normalized) || 0) + 1);
    }
  }

  const sorted = Array.from(kwCount.entries()).sort((a, b) => b[1] - a[1]).slice(0, 20);
  if (sorted.length === 0) return '';
  return sorted.map(([word, count], i) => i < 3 ? `**${word}**(${count})` : `${word}(${count})`).join(' · ');
}

// ============================================================================
// Report Generation (with Obsidian wikilinks)
// ============================================================================

function generateDigestReport(
  articles: ScoredArticle[],
  allArticles: Article[],
  highlights: string,
  stats: {
    totalFeeds: number;
    successFeeds: number;
    totalArticles: number;
    filteredArticles: number;
    hours: number;
  }
): string {
  const now = new Date();
  const dateStr = localDateString(now);

  let report = `# 📊 財經電子報每日精選 — ${dateStr}\n\n`;
  report += `> 來自 ${stats.totalFeeds} 個精選財經 Substack，AI 精選 Top ${articles.length}，共存入 ${allArticles.length} 篇筆記\n\n`;

  // ── Market Pulse ──
  if (highlights) {
    report += `## 📡 市場脈動\n\n${highlights}\n\n---\n\n`;
  }

  // ── Top 3 Deep Showcase ──
  if (articles.length >= 1) {
    report += `## 🏆 今日必讀\n\n`;
    for (let i = 0; i < Math.min(3, articles.length); i++) {
      const a = articles[i];
      const medal = ['🥇', '🥈', '🥉'][i];
      const catMeta = CATEGORY_META[a.category];

      report += `${medal} **${a.titleZh || a.title}**\n\n`;

      // Link to Obsidian note if exists, otherwise external link
      if (a.obsidianNote) {
        report += `[[${a.obsidianNote}|${a.title}]] — ${a.sourceName} · ${humanizeTime(a.pubDate)} · ${catMeta.emoji} ${catMeta.label}\n\n`;
      } else {
        report += `[${a.title}](${a.link}) — ${a.sourceName} · ${humanizeTime(a.pubDate)} · ${catMeta.emoji} ${catMeta.label}\n\n`;
      }

      report += `> ${a.summary}\n\n`;
      if (a.reason) report += `💡 **為什麼現在值得讀**: ${a.reason}\n\n`;
      if (a.keywords.length > 0) report += `🏷️ ${a.keywords.join(', ')}\n\n`;
    }
    report += `---\n\n`;
  }

  // ── Stats ──
  report += `## 📊 數據概覽\n\n`;
  report += `| 掃描源 | 抓取文章 | 時間範圍 | 精選 | 存入 Obsidian |\n`;
  report += `|:---:|:---:|:---:|:---:|:---:|\n`;
  report += `| ${stats.successFeeds}/${stats.totalFeeds} | ${stats.totalArticles} 篇 → ${stats.filteredArticles} 篇 | ${stats.hours}h | **${articles.length} 篇** | ${allArticles.filter(a => a.obsidianNote).length} 篇 |\n\n`;

  const pieChart = generateCategoryPieChart(articles);
  if (pieChart) report += `### 分類分佈\n\n${pieChart}\n`;

  const tagCloud = generateTagCloud(articles);
  if (tagCloud) report += `### 🏷️ 市場話題\n\n${tagCloud}\n\n`;

  report += `---\n\n`;

  // ── All Articles Index (by source) ──
  report += `## 📚 所有文章索引\n\n`;
  const bySource = new Map<string, Article[]>();
  for (const a of allArticles) {
    const list = bySource.get(a.sourceName) || [];
    list.push(a);
    bySource.set(a.sourceName, list);
  }

  for (const [source, sourceArticles] of bySource) {
    report += `### ${source}\n\n`;
    for (const a of sourceArticles) {
      const pubDate = a.pubDate.getTime() > 0 ? a.pubDate.toISOString().split('T')[0] : '?';
      if (a.obsidianNote) {
        report += `- [[${a.obsidianNote}|${a.title}]] · ${pubDate}\n`;
      } else {
        report += `- [${a.title}](${a.link}) · ${pubDate}\n`;
      }
    }
    report += '\n';
  }

  report += `---\n\n`;

  // ── Category-Grouped Top Articles ──
  const categoryGroups = new Map<CategoryId, ScoredArticle[]>();
  for (const a of articles) {
    const list = categoryGroups.get(a.category) || [];
    list.push(a);
    categoryGroups.set(a.category, list);
  }

  const sortedCategories = Array.from(categoryGroups.entries()).sort((a, b) => b[1].length - a[1].length);

  let globalIndex = 0;
  for (const [catId, catArticles] of sortedCategories) {
    const catMeta = CATEGORY_META[catId];
    report += `## ${catMeta.emoji} ${catMeta.label}\n\n`;

    for (const a of catArticles) {
      globalIndex++;
      const scoreTotal = a.scoreBreakdown.relevance + a.scoreBreakdown.quality + a.scoreBreakdown.timeliness;

      report += `### ${globalIndex}. ${a.titleZh || a.title}\n\n`;

      if (a.obsidianNote) {
        report += `[[${a.obsidianNote}|${a.title}]] — **${a.sourceName}** · ${humanizeTime(a.pubDate)} · ⭐ ${scoreTotal}/30\n\n`;
      } else {
        report += `[${a.title}](${a.link}) — **${a.sourceName}** · ${humanizeTime(a.pubDate)} · ⭐ ${scoreTotal}/30\n\n`;
      }

      report += `> ${a.summary}\n\n`;
      if (a.keywords.length > 0) report += `🏷️ ${a.keywords.join(', ')}\n\n`;
      report += `---\n\n`;
    }
  }

  // ── Footer ──
  const timeStr = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  report += `*生成於 ${dateStr} ${timeStr} | 掃描 ${stats.successFeeds} 源 → 獲取 ${stats.totalArticles} 篇 → 精選 ${articles.length} 篇*\n`;
  report += `*來源：FOMO SOC · Vincent Yu · Market Viewpoint · Vicky Ho*\n`;

  return report;
}

// ============================================================================
// CLI
// ============================================================================

function printUsage(): void {
  console.log(`Newsletter Digest - Fetch, archive to Obsidian, and summarize finance Substacks

Usage:
  bun digest-substack.ts [options]

Options:
  --hours <n>     Time range in hours (default: 168 = 7 days)
  --top-n <n>     Number of top articles to highlight (default: 10)
  --lang <lang>   Summary language: zh or en (default: zh)
  --no-scrape     Skip full-content scraping (use RSS description only)
  --help          Show this help

Environment:
  GEMINI_API_KEY        Gemini API key (required)
  GEMINI_MODEL          Model name (default: gemini-2.5-flash)
  OBSIDIAN_VAULT_PATH   Path to Obsidian vault (default: ~/Documents/arthurwang_DB)

Output:
  Individual notes → <vault>/Finance Digest/<Source Folder>/<date> <Title>.md
  Digest report   → <vault>/Finance Digest/<date> digest.md

Examples:
  bun digest-substack.ts
  bun digest-substack.ts --hours 72 --top-n 8
  bun digest-substack.ts --no-scrape
`);
  process.exit(0);
}

async function main(): Promise<void> {
  const args = process.argv.slice(2);
  if (args.includes('--help') || args.includes('-h')) printUsage();

  let hours = 168;
  let topN = 10;
  let lang: 'zh' | 'en' = 'zh';
  let doScrape = true;

  for (let i = 0; i < args.length; i++) {
    const arg = args[i]!;
    if (arg === '--hours' && args[i + 1]) hours = parseInt(args[++i]!, 10);
    else if (arg === '--top-n' && args[i + 1]) topN = parseInt(args[++i]!, 10);
    else if (arg === '--lang' && args[i + 1]) lang = args[++i] as 'zh' | 'en';
    else if (arg === '--no-scrape') doScrape = false;
  }

  const apiKey = process.env.GEMINI_API_KEY || (process.env.GEMINI_API_KEYS || '').split(',')[0]?.trim() || '';
  if (!apiKey) {
    console.error('[digest] Error: GEMINI_API_KEY not set.');
    process.exit(1);
  }

  const dateStr = localDateString();
  const digestPath = join(OBSIDIAN_VAULT, OBSIDIAN_DIGEST_FOLDER, `${dateStr} digest.md`);

  console.log(`[digest] === Newsletter Digest ===`);
  console.log(`[digest] Sources: ${RSS_FEEDS.map(f => f.name).join(', ')}`);
  console.log(`[digest] Time range: ${hours}h | Top N: ${topN} | Lang: ${lang}`);
  console.log(`[digest] Vault: ${OBSIDIAN_VAULT}`);
  console.log(`[digest] Output: ${digestPath}`);
  console.log('');

  // Step 1: Fetch RSS feeds
  console.log(`[digest] Step 1/6: Fetching ${RSS_FEEDS.length} RSS feeds...`);
  let allArticles = await fetchAllFeeds(RSS_FEEDS);

  if (allArticles.length === 0) {
    console.error('[digest] Error: No articles fetched. Check network connection.');
    process.exit(1);
  }

  // Step 2: Filter by time
  console.log(`[digest] Step 2/6: Filtering by time range (${hours} hours)...`);
  const cutoffTime = new Date(Date.now() - hours * 60 * 60 * 1000);
  let recentArticles = allArticles.filter(a => a.pubDate.getTime() > cutoffTime.getTime());
  console.log(`[digest] Found ${recentArticles.length} articles within last ${hours} hours`);

  if (recentArticles.length === 0) {
    console.error(`[digest] No articles in last ${hours}h. Try --hours 336`);
    process.exit(1);
  }

  // Step 3: Scrape full content
  if (doScrape) {
    console.log(`[digest] Step 3/6: Scraping full article content...`);
    recentArticles = await fetchAllArticleContents(recentArticles);
  } else {
    console.log(`[digest] Step 3/6: Skipping scrape (--no-scrape)`);
  }

  // Step 4: Save all articles to Obsidian
  console.log(`[digest] Step 4/6: Saving ${recentArticles.length} articles to Obsidian...`);
  recentArticles = await saveArticleNotes(recentArticles, dateStr);

  // Step 5: AI score all articles, pick top N
  console.log(`[digest] Step 5/6: AI scoring & summarizing...`);
  const scores = await scoreArticlesWithAI(recentArticles, apiKey);

  const scoredArticles = recentArticles.map((article, index) => {
    const score = scores.get(index) || { relevance: 5, quality: 5, timeliness: 5, category: 'other' as CategoryId, keywords: [] };
    return { ...article, totalScore: score.relevance + score.quality + score.timeliness, breakdown: score };
  });

  scoredArticles.sort((a, b) => b.totalScore - a.totalScore);
  const topArticles = scoredArticles.slice(0, topN);

  console.log(`[digest] Top ${topN} selected (score: ${topArticles[topArticles.length - 1]?.totalScore || 0}–${topArticles[0]?.totalScore || 0})`);

  const indexedTopArticles = topArticles.map((a, i) => ({ ...a, index: i }));
  const summaries = await summarizeArticles(indexedTopArticles, apiKey, lang);

  const finalArticles: ScoredArticle[] = topArticles.map((a, i) => {
    const sm = summaries.get(i) || { titleZh: a.title, summary: a.description.slice(0, 200), reason: '' };
    return {
      ...a,
      score: a.totalScore,
      scoreBreakdown: { relevance: a.breakdown.relevance, quality: a.breakdown.quality, timeliness: a.breakdown.timeliness },
      category: a.breakdown.category,
      keywords: a.breakdown.keywords,
      titleZh: sm.titleZh,
      summary: sm.summary,
      reason: sm.reason,
    };
  });

  // Step 6: Generate highlights and write digest report
  console.log(`[digest] Step 6/6: Generating market pulse & writing digest...`);
  const highlights = await generateHighlights(finalArticles, apiKey, lang);

  const successfulSources = new Set(allArticles.map(a => a.sourceName));
  const report = generateDigestReport(finalArticles, recentArticles, highlights, {
    totalFeeds: RSS_FEEDS.length,
    successFeeds: successfulSources.size,
    totalArticles: allArticles.length,
    filteredArticles: recentArticles.length,
    hours,
  });

  await mkdir(dirname(digestPath), { recursive: true });
  await writeFile(digestPath, report);

  console.log('');
  console.log(`[digest] ✅ Done!`);
  console.log(`[digest] 📁 Digest report: ${digestPath}`);
  console.log(`[digest] 📚 Article notes saved to per-source folders under: ${OBSIDIAN_VAULT}/${OBSIDIAN_DIGEST_FOLDER}/`);
  console.log(`[digest] 📊 ${successfulSources.size} sources → ${allArticles.length} total → ${recentArticles.length} recent → ${finalArticles.length} highlighted`);

  if (finalArticles.length > 0) {
    console.log('');
    console.log(`[digest] 🏆 Top 3:`);
    for (let i = 0; i < Math.min(3, finalArticles.length); i++) {
      const a = finalArticles[i];
      console.log(`  ${i + 1}. ${a.titleZh || a.title}`);
      if (a.summary) console.log(`     ${a.summary.slice(0, 80)}...`);
    }
  }
}

await main().catch((err) => {
  console.error(`[digest] Fatal error: ${err instanceof Error ? err.message : String(err)}`);
  process.exit(1);
});
