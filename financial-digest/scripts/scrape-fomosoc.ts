#!/usr/bin/env bun
/**
 * scrape-fomosoc.ts
 *
 * 爬取 fomosoc.com (FOMO SOC) 的所有文章，存為 Obsidian Markdown
 * 付費深度分析按產業自動分類（對齊 Uncle Stock Notes 結構）
 *
 * 用法：
 *   FOMOSOC_COOKIE="substack.sid=XXXX" bun scrape-fomosoc.ts
 *
 * 如何取得 cookie：
 *   1. Chrome → F12 → Application → Cookies → https://www.fomosoc.com
 *   2. 複製 substack.sid 的值
 *   3. 若找不到，改看 https://substack.com 底下的同名 cookie
 *   4. export FOMOSOC_COOKIE="substack.sid=<值>"
 *
 * 環境變數：
 *   FOMOSOC_COOKIE      登入 cookie（必填，付費文章用）
 *   OBSIDIAN_VAULT_PATH Obsidian vault 根目錄
 *   OUTPUT_DIR          覆蓋根目錄（預設：vault/Finance Digest/FOMO SOC）
 *   SCRAPE_LIMIT        每次 API 呼叫筆數（預設：25）
 *   SCRAPE_MAX_PAGES    最多爬幾頁（預設：無限制）
 *   SCRAPE_FORCE        設為 "1" 強制重新下載
 *   SCRAPE_NO_MIGRATE   設為 "1" 跳過舊檔搬移
 *
 * 目錄結構（對齊 Uncle Stock Notes）：
 *   付費/
 *     商周專欄/
 *     深度分析/
 *       AI晶片與GPU/
 *       AI軟體與SaaS/
 *       光通訊與網路/
 *       半導體設備/
 *       先進封裝/
 *       原物料與稀土/
 *       傳統金融/
 *       國防與軍工/
 *       總體經濟與策略/
 *       衛星與航太/
 *       記憶體半導體/
 *       量子運算/
 *       電力與能源/
 *       網路安全/
 *       雲端與資料中心/
 *       其他/
 *   免費/
 */

import { writeFile, mkdir, readdir, readFile, rename } from 'node:fs/promises';
import { join } from 'node:path';
import process from 'node:process';

// ============================================================================
// 設定
// ============================================================================

const BASE_URL = 'https://www.fomosoc.com';
const SOURCE_NAME = 'FOMO SOC';

const OBSIDIAN_VAULT = process.env.OBSIDIAN_VAULT_PATH || '/Users/yankesswang/Documents/arthurwang_DB';
const ROOT_DIR = process.env.OUTPUT_DIR || join(OBSIDIAN_VAULT, 'Finance Digest', 'FOMO SOC');
const PAID_DIR = join(ROOT_DIR, '付費');
const PAID_COLUMN_DIR = join(PAID_DIR, '商周專欄');
const PAID_ANALYSIS_DIR = join(PAID_DIR, '深度分析');
const FREE_DIR = join(ROOT_DIR, '免費');

// 深度分析 5 大產業子目錄
const ANALYSIS_CATS = [
  'AI半導體',        // GPU/晶片/光通訊/設備/封裝/記憶體
  '雲端與AI軟體',    // 雲端/AI應用/SaaS/網路安全
  '能源與原物料',    // 電力/核能/儲能/石油/稀土/銅
  '總體經濟與策略',  // 宏觀/地緣/國防/金融/衛星/量子
  '其他',
] as const;

type AnalysisCat = typeof ANALYSIS_CATS[number];

const FOMOSOC_COOKIE = process.env.FOMOSOC_COOKIE || '';
const LIMIT = parseInt(process.env.SCRAPE_LIMIT || '25', 10);
const MAX_PAGES = process.env.SCRAPE_MAX_PAGES ? parseInt(process.env.SCRAPE_MAX_PAGES, 10) : Infinity;
const FORCE = process.env.SCRAPE_FORCE === '1';
const NO_MIGRATE = process.env.SCRAPE_NO_MIGRATE === '1';

const FETCH_TIMEOUT_MS = 30_000;
const ARTICLE_DELAY_MS = 1_500;

// ============================================================================
// Types
// ============================================================================

interface FomoPost {
  id: number;
  title: string;
  subtitle?: string;
  slug: string;
  post_date: string;
  canonical_url: string;
  audience: string;
  type: string;
  tags?: Array<{ name: string; slug: string }>;
}

interface FomoPostDetail extends FomoPost {
  body_html?: string;
}

// ============================================================================
// 產業分類
// ============================================================================

function analysisSubcategoryFor(title: string): AnalysisCat {
  // 光通訊關鍵字優先排除（避免「銅」誤觸能源）
  if (/光通訊|OFC|CPO|LPO|矽光子|COHR|LITE/.test(title)) return 'AI半導體';

  // 衛星/太空優先（含亞馬遜的衛星文章避免誤判雲端）
  if (/Starlink|SpaceX|RocketLab|低軌衛星|星艦|AST SpaceMobile/.test(title)) return '總體經濟與策略';

  // 亞馬遜為主角的文章 → 雲端（避免標題含 Nvidia 誤判 AI半導體）
  if (/深度分析.*亞馬遜|亞馬遜.*深度分析/.test(title)) return '雲端與AI軟體';

  // 能源與原物料
  if (/GE Vernova|Bloom Energy|Caterpillar|CEG|VST|TLN|OKLO|Fluence|核能|儲能|BESS|電力|電網|公用事業|電池|鋰|石油|稀土|銅|礦物|鑽探/.test(title)) return '能源與原物料';

  // AI半導體（晶片/設備/封裝/記憶體）
  if (/NVDA|Nvidia|GPU|CUDA|ASIC|AMD|Intel|ARM|Groq|TPU|AVGO|Broadcom|博通|ASML|LRCX|AMAT|KLAC|封裝|CoWoS|記憶體|海力士|美光|SanDisk|HBM/.test(title)) return 'AI半導體';

  // 雲端與AI軟體（含資安）
  if (/雲端|AWS|Azure|CoreWeave|Nebius|亞馬遜|Amazon|Oracle|資料中心|SaaS|OpenAI|Meta\b|Palantir|軟體|軟件|資訊安全|資安|PANW|CRWD|ZS|OKTA/.test(title)) return '雲端與AI軟體';

  // 總體經濟與策略（宏觀/地緣/國防/金融/量子）
  if (/降息|宏觀|日本|VIX|滯脹|日元|財政|貨幣政策|美伊|投資指南|戰爭|軍工|國防|軍費|銀行|美債|債券|量子/.test(title)) return '總體經濟與策略';

  return '其他';
}

function outputDirFor(post: FomoPost): string {
  if (post.audience !== 'only_paid') return FREE_DIR;
  if (/商周專欄/.test(post.title)) return PAID_COLUMN_DIR;
  if (/深[度入]分析/.test(post.title)) {
    return join(PAID_ANALYSIS_DIR, analysisSubcategoryFor(post.title));
  }
  return PAID_DIR;
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
  md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*alt=["']([^"']*)["'][^>]*\/?>/gi,
    (_, src, alt) => `\n\n![${alt || ''}](${src})\n\n`);
  md = md.replace(/<img[^>]+alt=["']([^"']*)["'][^>]+src=["']([^"']+)["'][^>]*\/?>/gi,
    (_, alt, src) => `\n\n![${alt || ''}](${src})\n\n`);
  md = md.replace(/<img[^>]+src=["']([^"']+)["'][^>]*\/?>/gi,
    (_, src) => `\n\n![](${src})\n\n`);
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
  return decodeEntities(md).replace(/\n{4,}/g, '\n\n\n').trim();
}

function extractBodyFromHtml(html: string): string {
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
    if (m?.[1]) { const md = htmlToMarkdown(m[1]); if (md.length > 200) return md; }
  }
  const bodyMatch = cleaned.match(/<body[^>]*>([\s\S]*?)<\/body>/i);
  if (bodyMatch?.[1]) return htmlToMarkdown(bodyMatch[1]);
  return htmlToMarkdown(cleaned);
}

// ============================================================================
// Fetch
// ============================================================================

function makeHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8',
    'Referer': BASE_URL,
  };
  if (FOMOSOC_COOKIE) headers['Cookie'] = FOMOSOC_COOKIE;
  return headers;
}

async function fetchUrl(url: string, asJson = true): Promise<unknown> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS);
  try {
    const headers = makeHeaders();
    if (asJson) headers['Accept'] = 'application/json';
    const res = await fetch(url, { signal: controller.signal, headers });
    clearTimeout(timeout);
    if (!res.ok) throw new Error(`HTTP ${res.status} — ${url}`);
    return asJson ? res.json() : res.text();
  } catch (err) {
    clearTimeout(timeout);
    throw err;
  }
}

// ============================================================================
// API
// ============================================================================

async function fetchPostsPage(offset: number): Promise<FomoPost[]> {
  const url = `${BASE_URL}/api/v1/posts?limit=${LIMIT}&offset=${offset}`;
  console.log(`[scrape] 取得文章列表 offset=${offset}`);
  const data = await fetchUrl(url) as { posts?: FomoPost[] } | FomoPost[];
  if (Array.isArray(data)) return data;
  if (data && typeof data === 'object' && 'posts' in data && Array.isArray(data.posts)) return data.posts;
  return [];
}

async function fetchAllPosts(): Promise<FomoPost[]> {
  const all: FomoPost[] = [];
  let offset = 0, page = 0;
  while (page < MAX_PAGES) {
    const posts = await fetchPostsPage(offset);
    if (posts.length === 0) break;
    all.push(...posts);
    console.log(`[scrape] 已取得 ${all.length} 篇（本批 ${posts.length} 篇）`);
    if (posts.length < LIMIT) break;
    offset += LIMIT; page++;
    await new Promise(r => setTimeout(r, 500));
  }
  return all;
}

async function fetchPostContent(post: FomoPost): Promise<string> {
  try {
    const detail = await fetchUrl(`${BASE_URL}/api/v1/posts/${post.slug}`) as FomoPostDetail;
    if (detail.body_html && detail.body_html.length > 100) return htmlToMarkdown(detail.body_html);
  } catch (err) {
    console.warn(`[scrape]   API 失敗 (${post.slug}): ${err instanceof Error ? err.message : err}，改用 HTML`);
  }
  try {
    const html = await fetchUrl(post.canonical_url, false) as string;
    return extractBodyFromHtml(html);
  } catch (err) {
    console.warn(`[scrape]   HTML 失敗 (${post.slug}): ${err instanceof Error ? err.message : err}`);
    return '';
  }
}

// ============================================================================
// 格式化
// ============================================================================

function sanitizeFilename(name: string): string {
  return name.replace(/[/\\:*?"<>|#^[\]]/g, '').replace(/\s+/g, ' ').trim().slice(0, 100);
}

function formatObsidianNote(post: FomoPost, content: string): string {
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
    `slug: ${post.slug}`,
    `audience: ${post.audience}`,
    `tags:`,
    `  - fomo-soc`,
    tagLines,
    '---', '',
  ].join('\n');
  const subtitle = post.subtitle ? `\n*${post.subtitle}*\n` : '';
  return `${frontmatter}\n# ${post.title}\n${subtitle}\n${content || '（無法取得完整內容，請確認 cookie 是否有效）'}\n`;
}

// ============================================================================
// 已存在索引（遞迴掃描整個 ROOT_DIR）
// ============================================================================

async function buildExistingIndex(): Promise<Set<string>> {
  const titles = new Set<string>();
  async function scan(dir: string): Promise<void> {
    try {
      const entries = await readdir(dir, { withFileTypes: true });
      for (const e of entries) {
        if (e.isDirectory()) { await scan(join(dir, e.name)); continue; }
        if (!e.name.endsWith('.md')) continue;
        titles.add(e.name.replace(/^\d{4}-\d{2}-\d{2} /, '').replace(/\.md$/, ''));
      }
    } catch { /* 目錄不存在，跳過 */ }
  }
  await scan(ROOT_DIR);
  return titles;
}

function shouldSkip(post: FomoPost, existing: Set<string>): boolean {
  return existing.has(sanitizeFilename(post.title));
}

// ============================================================================
// 搬移：從任意舊位置搬到正確位置
// ============================================================================

async function migrateDir(
  srcDir: string,
  label: string,
  getDestDir: (f: string, content: string) => string,
): Promise<number> {
  let files: string[];
  try { files = (await readdir(srcDir)).filter(f => f.endsWith('.md')); }
  catch { return 0; }
  if (files.length === 0) return 0;

  console.log(`[migrate] ${label}：發現 ${files.length} 個 .md 檔`);
  let moved = 0;
  for (const f of files) {
    const srcPath = join(srcDir, f);
    let content: string;
    try { content = await readFile(srcPath, 'utf-8'); } catch { continue; }
    const destDir = getDestDir(f, content);
    if (destDir === srcDir) continue;
    try {
      await mkdir(destDir, { recursive: true });
      await rename(srcPath, join(destDir, f));
      console.log(`[migrate]   → ${destDir.replace(ROOT_DIR + '/', '')}/${f}`);
      moved++;
    } catch (err) {
      console.warn(`[migrate] 失敗 ${f}: ${err instanceof Error ? err.message : err}`);
    }
  }
  return moved;
}

function getDirFromFrontmatter(content: string, filename: string): string {
  const audienceMatch = content.match(/^audience:\s*(\S+)/m);
  const audience = audienceMatch?.[1] ?? 'everyone';
  const titleMatch = content.match(/^title:\s*"?(.+?)"?\s*$/m);
  const title = titleMatch?.[1] ?? filename.replace(/^\d{4}-\d{2}-\d{2} /, '').replace(/\.md$/, '');
  if (audience !== 'only_paid') return FREE_DIR;
  if (/商周專欄/.test(title)) return PAID_COLUMN_DIR;
  if (/深[度入]分析/.test(title)) return join(PAID_ANALYSIS_DIR, analysisSubcategoryFor(title));
  return PAID_DIR;
}

async function migrateAll(): Promise<void> {
  let total = 0;

  // 1. 根目錄 → 正確目的地
  total += await migrateDir(ROOT_DIR, '根目錄', (_f, content) => getDirFromFrontmatter(content, _f));

  // 2. 付費/ 根層 → 正確目的地
  total += await migrateDir(PAID_DIR, '付費根層', (_f, content) => getDirFromFrontmatter(content, _f));

  // 3. 付費/深度分析/ 根層（舊的未分類）→ 產業子目錄
  total += await migrateDir(PAID_ANALYSIS_DIR, '深度分析根層', (_f, content) => {
    const titleMatch = content.match(/^title:\s*"?(.+?)"?\s*$/m);
    const title = titleMatch?.[1] ?? _f;
    return join(PAID_ANALYSIS_DIR, analysisSubcategoryFor(title));
  });

  if (total > 0) console.log(`\n[migrate] 共搬移 ${total} 篇\n`);
  else console.log('[migrate] 無需搬移\n');
}

// ============================================================================
// 主程式
// ============================================================================

async function main() {
  console.log('============================================================');
  console.log('FOMO SOC 爬取工具');
  console.log(`來源：${BASE_URL}`);
  console.log(`根目錄：${ROOT_DIR}`);
  console.log(`模式：${FORCE ? '強制重新下載（SCRAPE_FORCE=1）' : '跳過已存在檔案'}`);
  console.log('============================================================');

  if (!FOMOSOC_COOKIE) {
    console.warn(`
⚠️  未設定 FOMOSOC_COOKIE，只能存取免費文章。

取得方式：Chrome → F12 → Application → Cookies → fomosoc.com → 複製 substack.sid
export FOMOSOC_COOKIE="substack.sid=<值>"
bun scrape-fomosoc.ts
`);
  }

  // 建立所有目錄
  await mkdir(PAID_COLUMN_DIR, { recursive: true });
  for (const cat of ANALYSIS_CATS) {
    await mkdir(join(PAID_ANALYSIS_DIR, cat), { recursive: true });
  }
  await mkdir(FREE_DIR, { recursive: true });

  // 搬移舊檔
  if (!NO_MIGRATE) await migrateAll();

  // 跳過索引
  const existingTitles = FORCE ? new Set<string>() : await buildExistingIndex();
  console.log(`[scrape] 已存在 ${existingTitles.size} 篇（將跳過）\n`);

  // 取得文章列表
  console.log('[scrape] 開始取得文章列表...');
  const allPosts = await fetchAllPosts();
  if (allPosts.length === 0) {
    console.error('[scrape] ⚠️  沒有取得任何文章。'); process.exit(1);
  }
  console.log(`\n[scrape] 共取得 ${allPosts.length} 篇，開始逐篇處理...\n`);

  let downloaded = 0, skipped = 0, failed = 0;

  for (let i = 0; i < allPosts.length; i++) {
    const post = allPosts[i]!;
    const idx = `[${i + 1}/${allPosts.length}]`;

    if (!FORCE && shouldSkip(post, existingTitles)) {
      console.log(`${idx} ⏭  跳過（已存在）：${post.title}`);
      skipped++; continue;
    }

    console.log(`${idx} ⬇  ${post.title}`);
    console.log(`     ${post.canonical_url} [${post.audience}]`);

    const content = await fetchPostContent(post);
    const isEmpty = !content || content.length < 50;
    if (isEmpty) { console.warn(`${idx} ⚠️  內容為空`); failed++; }
    else { console.log(`${idx} ✓  ${content.length} 字元`); downloaded++; }

    const pubDate = post.post_date
      ? new Date(post.post_date).toISOString().split('T')[0] : 'undated';
    const destDir = outputDirFor(post);
    const filename = `${pubDate} ${sanitizeFilename(post.title)}.md`;

    await mkdir(destDir, { recursive: true });
    await writeFile(join(destDir, filename), formatObsidianNote(post, content), 'utf-8');
    console.log(`${idx} 💾 ${destDir.replace(ROOT_DIR + '/', '')}/${filename}\n`);

    if (i < allPosts.length - 1) await new Promise(r => setTimeout(r, ARTICLE_DELAY_MS));
  }

  console.log('============================================================');
  console.log(`完成！共處理 ${allPosts.length} 篇`);
  console.log(`  ⬇  新下載：${downloaded} 篇`);
  console.log(`  ⏭  跳過：${skipped} 篇`);
  console.log(`  ⚠️  內容為空：${failed} 篇`);
  console.log(`  📁 ${ROOT_DIR}`);
  console.log('============================================================');
}

main().catch(err => { console.error('[scrape] 嚴重錯誤：', err); process.exit(1); });
