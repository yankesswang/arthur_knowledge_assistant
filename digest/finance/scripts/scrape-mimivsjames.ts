#!/usr/bin/env bun
/**
 * scrape-mimivsjames.ts
 *
 * 爬取 mimivsjames2.substack.com 的所有文章（含 Notes 短文）
 * 需要提供 Substack 登入 cookie（substack.sid）才能存取付費內容
 *
 * 用法：
 *   SUBSTACK_COOKIE="substack.sid=XXXX" bun scrape-mimivsjames.ts
 *
 * 選項（環境變數）：
 *   OBSIDIAN_VAULT_PATH  Obsidian vault 根目錄（預設：/Users/yankesswang/Documents/arthurwang_DB）
 *   SUBSTACK_LIMIT       每次 API 呼叫筆數（預設：25，max: 25）
 *   SUBSTACK_MAX_PAGES   最多爬幾頁（預設：無限制）
 *   OUTPUT_DIR           覆蓋輸出目錄（預設：vault/投資/MimiVsJames）
 *   INVEST_DIR           投資資料夾路徑（用於重複 URL 檢查）
 */

import { writeFile, mkdir, readFile, readdir } from 'node:fs/promises';
import { join, extname } from 'node:path';
import process from 'node:process';

// ============================================================================
// 設定
// ============================================================================

const BASE_URL = 'https://mimivsjames2.substack.com';
const SOURCE_NAME = 'MimiVsJames（Substack 付費通訊）';

const OBSIDIAN_VAULT = process.env.OBSIDIAN_VAULT_PATH || '/Users/yankesswang/Documents/arthurwang_DB';
const OUTPUT_DIR = process.env.OUTPUT_DIR || join(OBSIDIAN_VAULT, '投資', 'MimiVsJames');
const INVEST_DIR = process.env.INVEST_DIR || join(OBSIDIAN_VAULT, '投資');

const SUBSTACK_COOKIE = process.env.SUBSTACK_COOKIE || '';
const LIMIT = parseInt(process.env.SUBSTACK_LIMIT || '25', 10);
const MAX_PAGES = process.env.SUBSTACK_MAX_PAGES ? parseInt(process.env.SUBSTACK_MAX_PAGES, 10) : Infinity;

const FETCH_TIMEOUT_MS = 30_000;
const ARTICLE_DELAY_MS = 1_500;

// ============================================================================
// Types
// ============================================================================

interface SubstackPost {
  id: number;
  title: string;
  subtitle?: string;
  slug: string;
  post_date: string;
  canonical_url: string;
  description?: string;
  audience: string;
  type: string;
  tags?: Array<{ name: string; slug: string }>;
}

interface SubstackPostDetail extends SubstackPost {
  body_html?: string;
}

interface SubstackNote {
  id: string;
  body: string;
  date: string;
  url?: string;
  type: string;
}

// ============================================================================
// HTML → Markdown
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

function htmlToMarkdown(html: string): string {
  let md = html;

  md = md.replace(/<script[\s\S]*?<\/script>/gi, '');
  md = md.replace(/<style[\s\S]*?<\/style>/gi, '');

  md = md.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, (_, t) => `\n\n# ${stripHtml(t)}\n\n`);
  md = md.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, (_, t) => `\n\n## ${stripHtml(t)}\n\n`);
  md = md.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, (_, t) => `\n\n### ${stripHtml(t)}\n\n`);
  md = md.replace(/<h[456][^>]*>([\s\S]*?)<\/h[456]>/gi, (_, t) => `\n\n#### ${stripHtml(t)}\n\n`);

  // 圖片：優先從 data-attrs 取真實 S3 URL，避免 Substack CDN 佔位符 $s_!GIFH!
  md = md.replace(/<img[^>]+>/gi, (imgTag) => {
    // 從 data-attrs 解析原始 src
    const dataAttrsMatch = imgTag.match(/data-attrs=["']([^"']+)["']/i);
    let src = '';
    if (dataAttrsMatch) {
      try {
        const attrs = JSON.parse(dataAttrsMatch[1].replace(/&quot;/g, '"'));
        if (attrs.src) src = attrs.src;
      } catch { /* ignore */ }
    }
    // fallback：從 src 屬性取，並嘗試解碼 CDN 裡的原始 URL
    if (!src) {
      const srcMatch = imgTag.match(/src=["']([^"']+)["']/i);
      if (srcMatch) {
        const raw = srcMatch[1];
        // CDN URL 格式: .../fetch/.../https%3A%2F%2F...
        const encodedIdx = raw.lastIndexOf('https%3A');
        if (encodedIdx !== -1) {
          src = decodeURIComponent(raw.slice(encodedIdx));
        } else {
          src = raw;
        }
      }
    }
    if (!src) return '';
    const altMatch = imgTag.match(/alt=["']([^"']*)["']/i);
    const alt = altMatch ? altMatch[1] : '';
    return `\n\n![${alt}](${src})\n\n`;
  });

  md = md.replace(/<blockquote[^>]*>([\s\S]*?)<\/blockquote>/gi,
    (_, t) => `\n\n> ${stripHtml(t).split('\n').join('\n> ')}\n\n`);
  md = md.replace(/<li[^>]*>([\s\S]*?)<\/li>/gi, (_, t) => `\n- ${stripHtml(t)}`);
  md = md.replace(/<\/?(ul|ol)[^>]*>/gi, '\n');
  md = md.replace(/<p[^>]*>([\s\S]*?)<\/p>/gi, (_, t) => `\n\n${stripHtml(t)}\n\n`);
  md = md.replace(/<br\s*\/?>/gi, '\n');
  md = md.replace(/<hr\s*\/?>/gi, '\n\n---\n\n');

  md = md.replace(/<strong[^>]*>([\s\S]*?)<\/strong>/gi, (_, t) => `**${stripHtml(t)}**`);
  md = md.replace(/<b[^>]*>([\s\S]*?)<\/b>/gi, (_, t) => `**${stripHtml(t)}**`);
  md = md.replace(/<em[^>]*>([\s\S]*?)<\/em>/gi, (_, t) => `*${stripHtml(t)}*`);
  md = md.replace(/<i[^>]*>([\s\S]*?)<\/i>/gi, (_, t) => `*${stripHtml(t)}*`);
  md = md.replace(/<code[^>]*>([\s\S]*?)<\/code>/gi, (_, t) => `\`${stripHtml(t)}\``);
  md = md.replace(/<a[^>]+href=["']([^"']+)["'][^>]*>([\s\S]*?)<\/a>/gi,
    (_, href, text) => `[${stripHtml(text)}](${href})`);

  md = md.replace(/<[^>]*>/g, '');

  return decodeEntities(md)
    .replace(/\n{4,}/g, '\n\n\n')
    .trim();
}

function extractSubstackBodyFromHtml(html: string): string {
  let cleaned = html;
  cleaned = cleaned.replace(/<div[^>]+class="[^"]*paywall[^"]*"[^>]*>[\s\S]*?<\/div>/gi, '');
  cleaned = cleaned.replace(/<div[^>]+class="[^"]*subscription-widget[^"]*"[^>]*>[\s\S]*?<\/div>/gi, '');

  const patterns = [
    /<div[^>]+class="[^"]*available-content[^"]*"[^>]*>([\s\S]*?)<\/div>\s*(?:<\/div>|<div[^>]+id="footer)/i,
    /<div[^>]+class="[^"]*body\s+markup[^"]*"[^>]*>([\s\S]*)/i,
    /<div[^>]+class="[^"]*post-content[^"]*"[^>]*>([\s\S]*)/i,
    /<article[^>]*>([\s\S]*?)<\/article>/i,
  ];

  for (const pat of patterns) {
    const m = cleaned.match(pat);
    if (m?.[1]) {
      const md = htmlToMarkdown(m[1]);
      if (md.length > 200) return md;
    }
  }

  const bodyMatch = cleaned.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch?.[1]) return htmlToMarkdown(bodyMatch[1]);

  return htmlToMarkdown(cleaned);
}

// ============================================================================
// 重複 URL 檢查：掃描 投資 資料夾所有 .md frontmatter
// ============================================================================

async function collectExistingUrls(dir: string): Promise<Set<string>> {
  const urls = new Set<string>();

  async function walk(d: string) {
    let entries: Awaited<ReturnType<typeof readdir<{ withFileTypes: true }>>>;
    try {
      entries = await readdir(d, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      if (entry.name.startsWith('.')) continue;
      const fullPath = join(d, entry.name);

      if (entry.isDirectory()) {
        await walk(fullPath);
      } else if (entry.isFile() && extname(entry.name) === '.md') {
        try {
          const content = await readFile(fullPath, 'utf-8');
          const urlMatch = content.match(/^url:\s*["']?([^\s"'\n]+)["']?\s*$/m);
          if (urlMatch?.[1]) urls.add(urlMatch[1].trim());
        } catch {
          // skip unreadable files
        }
      }
    }
  }

  await walk(dir);
  return urls;
}

// ============================================================================
// Authenticated Fetch
// ============================================================================

function makeHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8',
    'Referer': `${BASE_URL}/notes`,
  };
  if (SUBSTACK_COOKIE) {
    headers['Cookie'] = SUBSTACK_COOKIE;
  }
  return headers;
}

async function fetchWithAuth(url: string, asJson = true): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);

  try {
    const headers = makeHeaders();
    if (asJson) headers['Accept'] = 'application/json';

    const res = await fetch(url, { signal: controller.signal, headers });
    clearTimeout(timeout);

    if (!res.ok) throw new Error(`HTTP ${res.status} ${res.statusText} — ${url}`);
    return asJson ? res.json() : res.text();
  } catch (err) {
    clearTimeout(timeout);
    throw err;
  }
}

// ============================================================================
// Substack API — 取得所有文章
// ============================================================================

async function fetchAllPosts(): Promise<SubstackPost[]> {
  const all: SubstackPost[] = [];
  let offset = 0;
  let page = 0;

  while (page < MAX_PAGES) {
    const url = `${BASE_URL}/api/v1/posts?limit=${LIMIT}&offset=${offset}`;
    console.log(`[posts] 抓取文章列表 offset=${offset}`);

    let batch: SubstackPost[] = [];
    try {
      const data = await fetchWithAuth(url) as SubstackPost[] | { posts?: SubstackPost[] };
      if (Array.isArray(data)) batch = data;
      else if (data && 'posts' in data && Array.isArray(data.posts)) batch = data.posts;
    } catch (err) {
      console.warn(`[posts] 抓取失敗：${err instanceof Error ? err.message : err}`);
      break;
    }

    if (batch.length === 0) break;
    all.push(...batch);
    console.log(`[posts] 已取得 ${all.length} 篇（本批 ${batch.length} 篇）`);

    if (batch.length < LIMIT) break;
    offset += LIMIT;
    page++;
    await new Promise(r => setTimeout(r, 500));
  }

  return all;
}

// ============================================================================
// Substack API — 取得 Notes（短文）
// ============================================================================

async function fetchNotes(): Promise<SubstackNote[]> {
  const all: SubstackNote[] = [];

  // 嘗試 publication notes API
  const endpoints = [
    `${BASE_URL}/api/v1/notes?limit=50`,
    `${BASE_URL}/api/v1/reader/feed/notes?limit=50`,
  ];

  for (const url of endpoints) {
    try {
      console.log(`[notes] 嘗試 ${url}`);
      const data = await fetchWithAuth(url) as unknown;

      let items: SubstackNote[] = [];
      if (Array.isArray(data)) items = data as SubstackNote[];
      else if (data && typeof data === 'object') {
        const d = data as Record<string, unknown>;
        if (Array.isArray(d['notes'])) items = d['notes'] as SubstackNote[];
        else if (Array.isArray(d['items'])) items = d['items'] as SubstackNote[];
      }

      if (items.length > 0) {
        all.push(...items);
        console.log(`[notes] 取得 ${items.length} 則 Notes`);
        break;
      }
    } catch (err) {
      console.warn(`[notes] ${url} 失敗：${err instanceof Error ? err.message : err}`);
    }
  }

  return all;
}

// ============================================================================
// 抓取單篇文章內容
// ============================================================================

async function fetchPostContent(post: SubstackPost): Promise<string> {
  try {
    const detail = await fetchWithAuth(`${BASE_URL}/api/v1/posts/${post.slug}`) as SubstackPostDetail;
    if (detail.body_html && detail.body_html.length > 100) {
      return htmlToMarkdown(detail.body_html);
    }
  } catch (err) {
    console.warn(`[fetch] API 失敗 (${post.slug})：${err instanceof Error ? err.message : err}`);
  }

  try {
    const html = await fetchWithAuth(post.canonical_url, false) as string;
    return extractSubstackBodyFromHtml(html);
  } catch (err) {
    console.warn(`[fetch] HTML 備用失敗 (${post.slug})：${err instanceof Error ? err.message : err}`);
    return '';
  }
}

// ============================================================================
// 格式化 Obsidian 筆記
// ============================================================================

function sanitizeFilename(name: string): string {
  return name
    .replace(/[/\\:*?"<>|#^[\]]/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, 100);
}

function formatPostNote(post: SubstackPost, content: string): string {
  const pubDate = post.post_date
    ? new Date(post.post_date).toISOString().split('T')[0]
    : new Date().toISOString().split('T')[0];

  const tagLines = post.tags?.map(t => `  - ${t.slug}`).join('\n') || '';

  const frontmatter = [
    '---',
    `title: "${post.title.replace(/"/g, "'")}"`,
    `date: ${pubDate}`,
    `source: ${SOURCE_NAME}`,
    `url: "${post.canonical_url}"`,
    `audience: ${post.audience}`,
    `tags:`,
    `  - mimi-vs-james`,
    tagLines,
    '---',
    '',
  ].filter((l, i, arr) => l !== '' || i < arr.length - 1).join('\n');

  const subtitle = post.subtitle ? `\n*${post.subtitle}*\n` : '';

  return `${frontmatter}\n# ${post.title}\n${subtitle}\n${content || '（無法取得完整內容，可能為免費預覽限制）'}\n`;
}

function formatNoteEntry(note: SubstackNote): { filename: string; content: string } {
  const pubDate = note.date
    ? new Date(note.date).toISOString().split('T')[0]
    : new Date().toISOString().split('T')[0];

  const noteUrl = note.url || `${BASE_URL}/note/${note.id}`;
  const preview = note.body?.slice(0, 60).replace(/\n/g, ' ').trim() || note.id;

  const frontmatter = [
    '---',
    `title: "Note: ${preview.replace(/"/g, "'")}"`,
    `date: ${pubDate}`,
    `source: ${SOURCE_NAME}`,
    `url: "${noteUrl}"`,
    `type: note`,
    `tags:`,
    `  - mimi-vs-james`,
    `  - substack-note`,
    '---',
    '',
  ].join('\n');

  const body = note.body || '（無內容）';
  const filename = `${pubDate} Note-${note.id}.md`;

  return { filename, content: `${frontmatter}\n${body}\n` };
}

// ============================================================================
// 主程式
// ============================================================================

async function main() {
  console.log('============================================================');
  console.log('MimiVsJames Substack 爬取工具');
  console.log(`目標：${BASE_URL}/notes`);
  console.log(`輸出：${OUTPUT_DIR}`);
  console.log(`投資資料夾（重複檢查）：${INVEST_DIR}`);
  console.log('============================================================');

  if (!SUBSTACK_COOKIE) {
    console.error(`
❌ 未設定 SUBSTACK_COOKIE 環境變數！

付費文章需要認證 cookie。請執行：
  export SUBSTACK_COOKIE="substack.sid=<你的值>"
  bun scrape-mimivsjames.ts

或一次性執行：
  SUBSTACK_COOKIE="substack.sid=<值>" bun scrape-mimivsjames.ts
`);
    process.exit(1);
  }

  await mkdir(OUTPUT_DIR, { recursive: true });

  // --- 掃描既有筆記 URL，建立重複排除集合 ---
  console.log(`\n[dedup] 掃描 ${INVEST_DIR} 既有筆記 URL...`);
  const existingUrls = await collectExistingUrls(INVEST_DIR);
  console.log(`[dedup] 找到 ${existingUrls.size} 個已存 URL`);

  // --- 抓取文章列表 ---
  console.log(`\n[posts] 開始抓取文章列表...`);
  const posts = await fetchAllPosts();
  console.log(`[posts] 共取得 ${posts.length} 篇文章`);

  // --- 抓取 Notes ---
  console.log(`\n[notes] 嘗試抓取 Notes（短文）...`);
  const notes = await fetchNotes();
  console.log(`[notes] 共取得 ${notes.length} 則 Notes`);

  // --- 處理文章 ---
  let saved = 0;
  let skipped = 0;
  let failed = 0;

  console.log(`\n${'='.repeat(60)}`);
  console.log('開始下載文章內容...');
  console.log('='.repeat(60));

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i]!;
    const idx = `[${i + 1}/${posts.length}]`;

    // 重複檢查
    if (existingUrls.has(post.canonical_url)) {
      console.log(`${idx} ⏭  已存在，跳過：${post.title}`);
      skipped++;
      continue;
    }

    console.log(`${idx} ↓  ${post.title}`);
    console.log(`     ${post.canonical_url}`);

    const content = await fetchPostContent(post);

    if (!content || content.length < 50) {
      console.warn(`${idx} ⚠️  內容為空（可能是免費預覽限制）`);
      failed++;
    }

    const noteContent = formatPostNote(post, content);
    const pubDate = post.post_date
      ? new Date(post.post_date).toISOString().split('T')[0]
      : 'undated';
    const filename = `${pubDate} ${sanitizeFilename(post.title)}.md`;
    const filepath = join(OUTPUT_DIR, filename);

    await writeFile(filepath, noteContent, 'utf-8');
    console.log(`${idx} 💾 ${filename}\n`);
    saved++;

    if (i < posts.length - 1) {
      await new Promise(r => setTimeout(r, ARTICLE_DELAY_MS));
    }
  }

  // --- 處理 Notes ---
  if (notes.length > 0) {
    console.log(`\n${'='.repeat(60)}`);
    console.log('處理 Notes...');
    const notesDir = join(OUTPUT_DIR, 'Notes');
    await mkdir(notesDir, { recursive: true });

    for (const note of notes) {
      const noteUrl = note.url || `${BASE_URL}/note/${note.id}`;
      if (existingUrls.has(noteUrl)) {
        console.log(`[note] ⏭  已存在，跳過：${note.id}`);
        skipped++;
        continue;
      }

      const { filename, content } = formatNoteEntry(note);
      await writeFile(join(notesDir, filename), content, 'utf-8');
      console.log(`[note] 💾 ${filename}`);
      saved++;
    }
  }

  // --- 總結 ---
  console.log('\n============================================================');
  console.log(`完成！`);
  console.log(`  💾 新增存檔：${saved} 篇`);
  console.log(`  ⏭  已存在跳過：${skipped} 篇`);
  console.log(`  ⚠️  內容為空：${failed} 篇`);
  console.log(`  📁 儲存位置：${OUTPUT_DIR}`);
  console.log('============================================================');
}

main().catch(err => {
  console.error('[scrape] 嚴重錯誤：', err);
  process.exit(1);
});
