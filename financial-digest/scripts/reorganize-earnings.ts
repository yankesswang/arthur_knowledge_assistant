#!/usr/bin/env bun
/**
 * reorganize-earnings.ts
 *
 * 在 財報分析/ 下加一層族群：
 *   財報分析/{族群}/{TICKER}/{QUARTER}/
 *
 * 用法：
 *   bun reorganize-earnings.ts           （實際執行）
 *   bun reorganize-earnings.ts --dry-run  （預覽）
 */

import { readdir, mkdir, stat } from 'node:fs/promises';
import { join, basename, dirname } from 'node:path';
import process from 'node:process';

const BASE_DIR = process.env.UNCLE_STOCK_DIR
  || '/Users/yankesswang/Documents/arthurwang_DB/投資/Uncle Stock Notes';

const EARNINGS_DIR = join(BASE_DIR, '財報分析');
const DRY_RUN = process.argv.includes('--dry-run');

// ============================================================================
// Ticker → 族群（財報分析用，比族群資料夾更粗粒度）
// ============================================================================

const TICKER_SECTOR: Record<string, string> = {
  // 半導體（設計）
  NVDA: '半導體', NVIDIA: '半導體', AMD: '半導體', INTC: '半導體',
  QCOM: '半導體', MRVL: '半導體', ALAB: '半導體', SMCI: '半導體',
  AVGO: '半導體', AAOI: '半導體', COHR: '半導體', CRDO: '半導體',
  LITE: '半導體', LPTH: '半導體', NVTS: '半導體', RMBS: '半導體',
  SNDK: '半導體',

  // 半導體（記憶體）
  MU: '半導體', WDC: '半導體', STX: '半導體',

  // 半導體設備與晶圓代工
  ASML: '半導體', AMAT: '半導體', LRCX: '半導體', GLW: '半導體', AEHR: '半導體',

  // 雲端與資料中心基礎設施
  AMZN: '雲端與資料中心', GOOGL: '雲端與資料中心', MSFT: '雲端與資料中心',
  META: '雲端與資料中心', BABA: '雲端與資料中心',
  CRWV: '雲端與資料中心', VRT: '雲端與資料中心', ETN: '雲端與資料中心',
  APLD: '雲端與資料中心', ANET: '雲端與資料中心', IREN: '雲端與資料中心',
  DOCN: '雲端與資料中心', GE: '雲端與資料中心',

  // AI軟體與SaaS
  PLTR: 'AI軟體與SaaS', SNOW: 'AI軟體與SaaS', CRM: 'AI軟體與SaaS',
  DDOG: 'AI軟體與SaaS', MDB: 'AI軟體與SaaS', ADBE: 'AI軟體與SaaS',
  IBM: 'AI軟體與SaaS', NOW: 'AI軟體與SaaS', INTU: 'AI軟體與SaaS',
  ORCL: 'AI軟體與SaaS', GTLB: 'AI軟體與SaaS', IOT: 'AI軟體與SaaS',
  PATH: 'AI軟體與SaaS', U: 'AI軟體與SaaS', BBAI: 'AI軟體與SaaS',
  NBIS: 'AI軟體與SaaS', CHYM: 'AI軟體與SaaS', AI: 'AI軟體與SaaS',

  // 網路安全
  PANW: '網路安全', CRWD: '網路安全', ZS: '網路安全',
  OKTA: '網路安全', S: '網路安全', RBRK: '網路安全',

  // 金融科技
  SOFI: '金融科技', PYPL: '金融科技', AFRM: '金融科技',
  FOUR: '金融科技', NU: '金融科技', MELI: '金融科技',
  GRAB: '金融科技', COIN: '金融科技', HOOD: '金融科技',
  SQ: '金融科技', TTD: '金融科技', TTDTHE: '金融科技',
  MA: '金融科技', V: '金融科技', VISA: '金融科技',
  FI: '金融科技', GS: '金融科技', GLXY: '金融科技',

  // 電力與能源（含核能）
  VST: '電力與能源', CEG: '電力與能源', GEV: '電力與能源',
  EOSE: '電力與能源', LEU: '電力與能源', UUUU: '電力與能源',
  OKLO: '電力與能源', SMR: '電力與能源', BWXT: '電力與能源',

  // 無人機與國防
  AVAV: '無人機與國防', KTOS: '無人機與國防', AXON: '無人機與國防',
  RCAT: '無人機與國防', ONDS: '無人機與國防', ACHR: '無人機與國防',
  ASTS: '無人機與國防', LMT: '無人機與國防', RKLB: '無人機與國防',

  // 量子運算
  IONQ: '量子運算', RGTI: '量子運算',

  // 機器人與自動化
  ISRG: '機器人與自動化', TESLA: '機器人與自動化',

  // 生技與醫療
  HIMS: '生技與醫療', LLY: '生技與醫療', OSCR: '生技與醫療',
  TMDX: '生技與醫療',

  // 消費與品牌
  AAPL: '消費與品牌', ABNB: '消費與品牌', ROKU: '消費與品牌',
  RDDT: '消費與品牌', APP: '消費與品牌', DUOL: '消費與品牌',
  LULU: '消費與品牌', NKE: '消費與品牌', CROX: '消費與品牌',
  SHOP: '消費與品牌', SE: '消費與品牌', UBER: '消費與品牌',
  CHGG: '消費與品牌', BBY: '消費與品牌',

  // 餐飲與消費
  BROS: '消費與品牌', DPZ: '消費與品牌', CAVA: '消費與品牌',
  MNST: '消費與品牌', CELH: '消費與品牌', COST: '消費與品牌',

  // 原物料
  MP: '原物料', HP: '原物料',

  // 其他科技
  TWLO: '其他科技', NET: '其他科技', FIG: '其他科技',
  SES: '其他科技', SIDU: '其他科技', LCID: '其他科技',
  BE: '其他科技', TEM: '其他科技', TEMPUS: '其他科技',
  CRCL: '其他科技',
};

// ============================================================================
// 主程式
// ============================================================================

async function main() {
  console.log('============================================================');
  console.log('財報分析 → 加族群層');
  if (DRY_RUN) console.log('** DRY RUN 模式 **');
  console.log('============================================================\n');

  // 讀取 財報分析/ 下的所有 ticker 資料夾
  const tickerDirs = await readdir(EARNINGS_DIR);

  const moves: Array<{ src: string; dest: string }> = [];
  const unmapped: string[] = [];

  for (const ticker of tickerDirs) {
    const tickerPath = join(EARNINGS_DIR, ticker);
    const s = await stat(tickerPath);
    if (!s.isDirectory()) continue;

    const sector = TICKER_SECTOR[ticker] || null;

    if (!sector) {
      unmapped.push(ticker);
      continue;
    }

    // 讀取季度子資料夾
    const quarters = await readdir(tickerPath);
    for (const quarter of quarters) {
      const quarterPath = join(tickerPath, quarter);
      const qs = await stat(quarterPath);
      if (!qs.isDirectory()) continue;

      // 讀取該季度下的所有 .md 檔
      const files = await readdir(quarterPath);
      for (const file of files) {
        if (!file.endsWith('.md')) continue;
        const src = join(quarterPath, file);
        const dest = join(EARNINGS_DIR, sector, ticker, quarter, file);
        moves.push({ src, dest });
      }
    }
  }

  console.log(`共 ${tickerDirs.length} 個 ticker`);
  if (unmapped.length > 0) {
    console.log(`⚠️  未對應族群（將留在原位）：${unmapped.join(', ')}`);
  }
  console.log(`移動 ${moves.length} 個檔案\n`);

  // 統計族群分布
  const sectorCount: Record<string, number> = {};
  for (const m of moves) {
    const parts = m.dest.replace(EARNINGS_DIR + '/', '').split('/');
    const sec = parts[0]!;
    sectorCount[sec] = (sectorCount[sec] || 0) + 1;
  }
  console.log('族群分布：');
  for (const [s, n] of Object.entries(sectorCount).sort((a,b) => b[1]-a[1])) {
    console.log(`  ${s.padEnd(20)}：${n} 篇`);
  }
  console.log('');

  if (DRY_RUN) {
    console.log('--- 前 20 筆預覽 ---');
    for (const m of moves.slice(0, 20)) {
      const rel = m.dest.replace(EARNINGS_DIR + '/', '');
      console.log(`  → 財報分析/${rel}`);
    }
    return;
  }

  // 實際移動
  let moved = 0;
  let errors = 0;

  for (const m of moves) {
    try {
      await mkdir(dirname(m.dest), { recursive: true });
      const proc = Bun.spawn(['mv', m.src, m.dest], { stderr: 'pipe' });
      const code = await proc.exited;
      if (code !== 0) throw new Error(await new Response(proc.stderr).text());
      moved++;
    } catch (err) {
      console.error(`❌ ${basename(m.src)}: ${err instanceof Error ? err.message : err}`);
      errors++;
    }
  }

  // 清理空的舊 ticker 資料夾
  console.log('\n清理舊空資料夾...');
  for (const ticker of tickerDirs) {
    if (!TICKER_SECTOR[ticker]) continue;
    const tickerPath = join(EARNINGS_DIR, ticker);
    try {
      // 嘗試刪除（只有空目錄才會成功）
      const proc = Bun.spawn(['find', tickerPath, '-type', 'd', '-empty', '-delete'], { stderr: 'pipe' });
      await proc.exited;
    } catch {}
    try {
      const proc2 = Bun.spawn(['rmdir', tickerPath], { stderr: 'pipe' });
      await proc2.exited;
    } catch {}
  }

  console.log(`\n完成！移動 ${moved} 篇，失敗 ${errors} 篇`);
}

main().catch(err => {
  console.error('錯誤：', err);
  process.exit(1);
});
