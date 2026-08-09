#!/usr/bin/env bun
/**
 * scrape-uncle-stock.ts
 *
 * 爬取 unclestocknotes.substack.com/t/financialanaysis 的所有付費文章
 * 需要提供 Substack 登入 cookie（substack.sid）才能存取付費內容
 *
 * 用法：
 *   SUBSTACK_COOKIE="substack.sid=XXXX; substack.lli=1" bun scrape-uncle-stock.ts
 *
 * 如何取得 cookie：
 *   1. Chrome → 開 F12 DevTools → Application → Cookies → substack.com
 *   2. 複製 substack.sid 的值
 *   3. 設定環境變數：export SUBSTACK_COOKIE="substack.sid=<值>"
 *
 * 選項（環境變數）：
 *   OBSIDIAN_VAULT_PATH  Obsidian vault 根目錄（預設：/Users/yankesswang/Documents/arthurwang_DB）
 *   SUBSTACK_LIMIT       每次 API 呼叫筆數（預設：25，max: 25）
 *   SUBSTACK_MAX_PAGES   最多爬幾頁（預設：無限制）
 *   OUTPUT_DIR           覆蓋輸出目錄（預設：vault/投資/Uncle Stock Notes）
 */

import { writeFile, mkdir, readdir } from 'node:fs/promises';
import { join } from 'node:path';
import process from 'node:process';

// ============================================================================
// 設定
// ============================================================================

const BASE_URL = 'https://unclestocknotes.substack.com';
const TAG_SLUG = 'financialanaysis';
const SOURCE_NAME = 'Uncle Stock Notes';

const OBSIDIAN_VAULT = process.env.OBSIDIAN_VAULT_PATH || '/Users/yankesswang/Documents/arthurwang_DB';
const OUTPUT_DIR = process.env.OUTPUT_DIR || join(OBSIDIAN_VAULT, '投資', 'Uncle Stock Notes');

const SUBSTACK_COOKIE = process.env.SUBSTACK_COOKIE || '';
const LIMIT = parseInt(process.env.SUBSTACK_LIMIT || '25', 10);
const MAX_PAGES = process.env.SUBSTACK_MAX_PAGES ? parseInt(process.env.SUBSTACK_MAX_PAGES, 10) : Infinity;

const FETCH_TIMEOUT_MS = 30_000;
const ARTICLE_DELAY_MS = 1_500; // 避免被 rate limit

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
  audience: string; // 'everyone' | 'only_paid' | 'founding'
  type: string;     // 'newsletter' | 'podcast' | etc.
  tags?: Array<{ name: string; slug: string }>;
}

interface SubstackPostDetail extends SubstackPost {
  body_html?: string;
  truncated_body_text?: string;
}

// ============================================================================
// HTML → Markdown（沿用 digest-substack.ts 的邏輯）
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

  // Headings
  md = md.replace(/<h1[^>]*>([\s\S]*?)<\/h1>/gi, (_, t) => `\n\n# ${stripHtml(t)}\n\n`);
  md = md.replace(/<h2[^>]*>([\s\S]*?)<\/h2>/gi, (_, t) => `\n\n## ${stripHtml(t)}\n\n`);
  md = md.replace(/<h3[^>]*>([\s\S]*?)<\/h3>/gi, (_, t) => `\n\n### ${stripHtml(t)}\n\n`);
  md = md.replace(/<h[456][^>]*>([\s\S]*?)<\/h[456]>/gi, (_, t) => `\n\n#### ${stripHtml(t)}\n\n`);

  // Images — 保留外部 URL
  md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*alt=["']([^"']*)["'][^>]*\/?>/gi,
    (_, src, alt) => `\n\n![${alt || ''}](${src})\n\n`);
  md = md.replace(/<img[^>]+alt=["']([^"']*)["'][^>]+src=["']([^"']+)["'][^>]*\/?>/gi,
    (_, alt, src) => `\n\n![${alt || ''}](${src})\n\n`);
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

  md = md.replace(/<[^>]*>/g, '');

  return decodeEntities(md)
    .replace(/\n{4,}/g, '\n\n\n')
    .trim();
}

// ============================================================================
// 從 Substack HTML 頁面抽取文章內容（備用，當 API 沒有 body_html 時）
// ============================================================================

function extractSubstackBodyFromHtml(html: string): string {
  // 先移除訂閱牆
  let cleaned = html;
  cleaned = cleaned.replace(/<div[^>]+class="[^"]*paywall[^"]*"[^>]*>[\s\S]*?<\/div>/gi, '');
  cleaned = cleaned.replace(/<div[^>]+class="[^"]*subscription-widget[^"]*"[^>]*>[\s\S]*?<\/div>/gi, '');

  // 嘗試多個 Substack 文章容器 selector
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

  // 最後備用：整個 body
  const bodyMatch = cleaned.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch?.[1]) return htmlToMarkdown(bodyMatch[1]);

  return htmlToMarkdown(cleaned);
}

// ============================================================================
// Authenticated Fetch
// ============================================================================

function makeHeaders(): HeadersInit {
  const headers: Record<string, string> = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8',
    'Referer': `${BASE_URL}/t/${TAG_SLUG}`,
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
    if (asJson) {
      (headers as Record<string, string>)['Accept'] = 'application/json';
    }

    const res = await fetch(url, { signal: controller.signal, headers });
    clearTimeout(timeout);

    if (!res.ok) {
      throw new Error(`HTTP ${res.status} ${res.statusText} — ${url}`);
    }

    return asJson ? res.json() : res.text();
  } catch (err) {
    clearTimeout(timeout);
    throw err;
  }
}

// ============================================================================
// Substack API — 取得標籤下的文章列表
// ============================================================================

async function fetchPostsByTag(offset: number): Promise<SubstackPost[]> {
  // Substack 的 API endpoint for tag posts
  const url = `${BASE_URL}/api/v1/posts?tag=${TAG_SLUG}&limit=${LIMIT}&offset=${offset}`;
  console.log(`[scrape] 抓取文章列表 offset=${offset} → ${url}`);

  const data = await fetchWithAuth(url) as { posts?: SubstackPost[] } | SubstackPost[];

  // API 有時回傳 { posts: [...] }，有時直接回傳 array
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object' && 'posts' in data && Array.isArray(data.posts)) return data.posts;
  return [];
}

async function fetchAllPostsList(): Promise<SubstackPost[]> {
  const all: SubstackPost[] = [];
  let offset = 0;
  let page = 0;

  while (page < MAX_PAGES) {
    const posts = await fetchPostsByTag(offset);
    if (posts.length === 0) break;

    all.push(...posts);
    console.log(`[scrape] 已取得 ${all.length} 篇（本批 ${posts.length} 篇）`);

    if (posts.length < LIMIT) break; // 最後一頁

    offset += LIMIT;
    page++;

    // 避免 rate limit
    await new Promise(r => setTimeout(r, 500));
  }

  return all;
}

// ============================================================================
// 抓取單篇文章完整內容（用 API 或 HTML 備用）
// ============================================================================

async function fetchPostContent(post: SubstackPost): Promise<string> {
  // 方法一：Substack API — 單篇文章 endpoint（含 body_html）
  try {
    const apiUrl = `${BASE_URL}/api/v1/posts/${post.slug}`;
    const detail = await fetchWithAuth(apiUrl) as SubstackPostDetail;

    if (detail.body_html && detail.body_html.length > 100) {
      return htmlToMarkdown(detail.body_html);
    }
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(`[scrape] API 抓取失敗 (${post.slug}): ${msg}，改用 HTML 備用`);
  }

  // 方法二：直接抓 HTML 頁面
  try {
    const html = await fetchWithAuth(post.canonical_url, false) as string;
    return extractSubstackBodyFromHtml(html);
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.warn(`[scrape] HTML 抓取失敗 (${post.slug}): ${msg}`);
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

function formatObsidianNote(post: SubstackPost, content: string): string {
  const pubDate = post.post_date
    ? new Date(post.post_date).toISOString().split('T')[0]
    : new Date().toISOString().split('T')[0];

  const tags = post.tags?.map(t => `  - ${t.slug}`).join('\n') || '';

  const frontmatter = [
    '---',
    `title: "${post.title.replace(/"/g, "'")}"`,
    `date: ${pubDate}`,
    `source: ${SOURCE_NAME}`,
    `url: "${post.canonical_url}"`,
    `audience: ${post.audience}`,
    `tags:`,
    `  - uncle-stock-notes`,
    `  - financial-analysis`,
    tags,
    '---',
    '',
  ].filter(line => line !== '' || line === '').join('\n');

  const subtitle = post.subtitle ? `\n*${post.subtitle}*\n` : '';

  return `${frontmatter}\n# ${post.title}\n${subtitle}\n${content || '（無法取得完整內容）'}\n`;
}

// ============================================================================
// 掃描已存在的檔案（遞迴），回傳檔名 Set（不含路徑）
// ============================================================================

async function collectExistingFilenames(dir: string): Promise<Set<string>> {
  const names = new Set<string>();
  async function walk(current: string) {
    let entries;
    try {
      entries = await readdir(current, { withFileTypes: true });
    } catch {
      return;
    }
    for (const entry of entries) {
      if (entry.isDirectory()) {
        await walk(join(current, entry.name));
      } else if (entry.name.endsWith('.md')) {
        names.add(entry.name);
      }
    }
  }
  await walk(dir);
  return names;
}

// ============================================================================
// 主程式
// ============================================================================

async function main() {
  console.log('============================================================');
  console.log(`Uncle Stock Notes — Financial Analysis 爬取工具`);
  console.log(`目標：${BASE_URL}/t/${TAG_SLUG}`);
  console.log(`輸出：${OUTPUT_DIR}`);
  console.log('============================================================');

  if (!SUBSTACK_COOKIE) {
    console.error(`
❌ 未設定 SUBSTACK_COOKIE 環境變數！

付費文章需要認證 cookie。請按以下步驟取得：

1. 在 Chrome/Firefox 開啟 ${BASE_URL}，確認已登入
2. 按 F12 開啟 DevTools
3. 前往 Application（Chrome）或 Storage（Firefox）→ Cookies → substack.com
4. 找到 "substack.sid" 欄位，複製其 Value
5. 執行：
   export SUBSTACK_COOKIE="substack.sid=<你的值>"
   bun scrape-uncle-stock.ts

或一次性執行：
   SUBSTACK_COOKIE="substack.sid=<你的值>" bun scrape-uncle-stock.ts
`);
    process.exit(1);
  }

  // 建立輸出目錄
  await mkdir(OUTPUT_DIR, { recursive: true });
  console.log(`[scrape] 輸出目錄：${OUTPUT_DIR}`);

  // 掃描已存在的筆記（含所有子目錄）
  console.log(`[scrape] 掃描已存在的筆記...`);
  const existingFiles = await collectExistingFilenames(OUTPUT_DIR);
  console.log(`[scrape] 已找到 ${existingFiles.size} 個現有筆記\n`);

  // 取得文章列表
  console.log(`[scrape] 開始取得文章列表...`);
  const posts = await fetchAllPostsList();

  if (posts.length === 0) {
    console.error('[scrape] ⚠️  沒有取得任何文章。可能原因：');
    console.error('  - Cookie 已過期或無效');
    console.error('  - Tag slug 錯誤（目前：financialanaysis）');
    console.error('  - 網路問題');
    process.exit(1);
  }

  console.log(`\n[scrape] 共取得 ${posts.length} 篇文章，開始逐篇下載內容...\n`);

  let success = 0;
  let skipped = 0;
  let failed = 0;

  for (let i = 0; i < posts.length; i++) {
    const post = posts[i]!;
    const idx = `[${i + 1}/${posts.length}]`;

    const pubDate = post.post_date
      ? new Date(post.post_date).toISOString().split('T')[0]
      : 'undated';
    const filename = `${pubDate} ${sanitizeFilename(post.title)}.md`;

    if (existingFiles.has(filename)) {
      console.log(`${idx} ⏭  已存在，略過：${filename}`);
      skipped++;
      continue;
    }

    console.log(`${idx} ${post.title}`);
    console.log(`     ${post.canonical_url}`);

    const content = await fetchPostContent(post);

    if (!content || content.length < 50) {
      console.warn(`${idx} ⚠️  內容為空（可能是免費預覽限制或 cookie 問題）`);
      failed++;
    } else {
      console.log(`${idx} ✓ 內容長度：${content.length} 字元`);
      success++;
    }

    const noteContent = formatObsidianNote(post, content);
    const filepath = join(OUTPUT_DIR, filename);

    await writeFile(filepath, noteContent, 'utf-8');
    console.log(`${idx} 💾 已存：${filename}\n`);

    // Rate limit 保護
    if (i < posts.length - 1) {
      await new Promise(r => setTimeout(r, ARTICLE_DELAY_MS));
    }
  }

  console.log('============================================================');
  console.log(`完成！共處理 ${posts.length} 篇`);
  console.log(`  ⏭  已略過（既有）：${skipped} 篇`);
  console.log(`  ✓ 成功取得完整內容：${success} 篇`);
  console.log(`  ⚠️  內容為空：${failed} 篇`);
  console.log(`  📁 儲存位置：${OUTPUT_DIR}`);
  console.log('============================================================');
}

main().catch(err => {
  console.error('[scrape] 嚴重錯誤：', err);
  process.exit(1);
});
