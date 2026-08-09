#!/usr/bin/env bun
/**
 * classify-uncle-stock.ts
 *
 * 將 Uncle Stock Notes 文章分類到以下結構：
 *
 * Uncle Stock Notes/
 * ├── 財報分析/
 * │   ├── NVDA/
 * │   │   ├── 2025 Q4/
 * │   │   └── 2026 Q1/
 * │   └── AMD/ ...
 * ├── 族群/
 * │   ├── 記憶體半導體/
 * │   │   ├── MU/
 * │   │   └── STX/
 * │   ├── AI晶片與GPU/
 * │   │   ├── NVDA/
 * │   │   └── AMD/
 * │   └── ...
 * └── 總體經濟與策略/
 *
 * 用法：
 *   bun classify-uncle-stock.ts
 *   bun classify-uncle-stock.ts --dry-run   （只印分類結果，不移動檔案）
 */

import { readdir, mkdir } from 'node:fs/promises';
import { join, basename, dirname } from 'node:path';
import process from 'node:process';

// ============================================================================
// 設定
// ============================================================================

const BASE_DIR = process.env.UNCLE_STOCK_DIR
  || '/Users/yankesswang/Documents/arthurwang_DB/投資/Uncle Stock Notes';

const DRY_RUN = process.argv.includes('--dry-run');

// ============================================================================
// Ticker → 族群 映射
// ============================================================================

const TICKER_TO_SECTOR: Record<string, string> = {
  // 記憶體半導體
  MU: '記憶體半導體', DRAM: '記憶體半導體', HBM: '記憶體半導體',
  WDC: '記憶體半導體', STX: '記憶體半導體', NAND: '記憶體半導體',
  CXMT: '記憶體半導體',

  // AI晶片與GPU
  NVDA: 'AI晶片與GPU', AMD: 'AI晶片與GPU',
  INTC: 'AI晶片與GPU', QCOM: 'AI晶片與GPU',
  MRVL: 'AI晶片與GPU', ALAB: 'AI晶片與GPU',
  SMCI: 'AI晶片與GPU',

  // 晶圓代工與半導體設備
  TSM: '晶圓代工與半導體設備', ASML: '晶圓代工與半導體設備',
  AMAT: '晶圓代工與半導體設備', LRCX: '晶圓代工與半導體設備',
  KLAC: '晶圓代工與半導體設備', ONTO: '晶圓代工與半導體設備',
  COHU: '晶圓代工與半導體設備', AEHR: '晶圓代工與半導體設備',

  // 光通訊與網路
  AAOI: '光通訊與網路', LITE: '光通訊與網路', CIEN: '光通訊與網路',
  VIAV: '光通訊與網路', ANET: '光通訊與網路', CSCO: '光通訊與網路',

  // 雲端與資料中心基礎設施
  AMZN: '雲端與資料中心', GOOGL: '雲端與資料中心', GOOG: '雲端與資料中心',
  MSFT: '雲端與資料中心', CRWV: '雲端與資料中心',
  VRT: '雲端與資料中心', ETN: '雲端與資料中心', APLD: '雲端與資料中心',

  // AI軟體與平台
  PLTR: 'AI軟體與平台', SNOW: 'AI軟體與平台', CRM: 'AI軟體與平台',
  DDOG: 'AI軟體與平台', MDB: 'AI軟體與平台', CFLT: 'AI軟體與平台',
  ADBE: 'AI軟體與平台', ORCL: 'AI軟體與平台', ADSK: 'AI軟體與平台',
  IBM: 'AI軟體與平台', NOW: 'AI軟體與平台', INTU: 'AI軟體與平台',
  HUBS: 'AI軟體與平台', ZS: 'AI軟體與平台', PANW: 'AI軟體與平台',
  CRWD: 'AI軟體與平台', S: 'AI軟體與平台',

  // 金融科技
  SOFI: '金融科技', PYPL: '金融科技', AFRM: '金融科技',
  FOUR: '金融科技', NU: '金融科技', MELI: '金融科技',
  GRAB: '金融科技', COIN: '金融科技', HOOD: '金融科技',
  UPST: '金融科技', SQ: '金融科技', BILL: '金融科技',
  SMAR: '金融科技', TTD: '金融科技',

  // 電力與能源（含核能）
  VST: '電力與能源', CEG: '電力與能源', GEV: '電力與能源',
  EOSE: '電力與能源', LEU: '電力與能源', UUUU: '電力與能源',
  CCJ: '電力與能源', NLR: '電力與能源', SMR: '電力與能源',

  // 無人機與國防
  AVAV: '無人機與國防', KTOS: '無人機與國防', AXON: '無人機與國防',
  RCAT: '無人機與國防', ONDS: '無人機與國防', ACHR: '無人機與國防',
  ASTS: '無人機與國防', LMT: '無人機與國防', RTX: '無人機與國防',

  // 機器人與自動化
  TSLA: '機器人與自動化', ISRG: '機器人與自動化',
  IONQ: '量子運算', QUBT: '量子運算',

  // 消費、娛樂與媒體
  ABNB: '消費與娛樂', ROKU: '消費與娛樂', RDDT: '消費與娛樂',
  APP: '消費與娛樂', DIS: '消費與娛樂', NFLX: '消費與娛樂',
  SPOT: '消費與娛樂', SNAP: '消費與娛樂',

  // 生技與醫療
  HIMS: '生技與醫療', NVO: '生技與醫療', CELH: '生技與醫療',
  MNST: '生技與醫療', LCID: '生技與醫療', BROS: '生技與醫療',

  // 電商與物流
  SHOP: '電商與物流', SE: '電商與物流',

  // 不動產與金融
  'BRK.A': '傳統金融', 'BRK.B': '傳統金融',
  BAC: '傳統金融', JPM: '傳統金融',

  // 原物料與稀土
  MP: '原物料與稀土', FCX: '原物料與稀土',
};

// 關鍵字 → 族群（補充 ticker 映射沒有的情況）
const KEYWORD_TO_SECTOR: Array<[RegExp, string]> = [
  [/記憶體|DRAM|HBM|NAND|flash|海力士|hynix|三星.*記憶|SanDisk/i, '記憶體半導體'],
  [/nvidia|NVDA|cuda|GPU(?!\s*晶圓)|AI\s*晶片/i, 'AI晶片與GPU'],
  [/台積電|TSM(?!C)|晶圓|ASML|AMAT|LRCX|KLAC|製程|EUV/i, '晶圓代工與半導體設備'],
  [/光通訊|光纖|transceiver|AAOI|ANET(?!\s*財)|cisco/i, '光通訊與網路'],
  [/AWS|Azure|Google\s*Cloud|資料中心|data\s*center|CoreWeave|液冷/i, '雲端與資料中心'],
  [/palantir|PLTR|snowflake|SNOW|salesforce|CRM(?!\s*財)|資安|cybersecurity/i, 'AI軟體與平台'],
  [/SoFi|PYPL|Paypal|Affirm|fintech|金融科技|加密|crypto|比特幣|coinbase/i, '金融科技'],
  [/核能|電力|能源|power\s*grid|uranium|GEV|vernova|eaton|ETN(?!\s*)|vistra/i, '電力與能源'],
  [/無人機|drone|defense|國防|AVAV|KTOS|axon|ONDS/i, '無人機與國防'],
  [/機器人|robot|humanoid|tesla(?!\s*財)|TSLA|isrg|直覺外科/i, '機器人與自動化'],
  [/量子|quantum|ionq|IONQ/i, '量子運算'],
  [/ABNB|airbnb|netflix|disney|DIS(?!\s*財)|spotify|reddit|snapchat/i, '消費與娛樂'],
  [/醫療|biotech|生技|HIMS|NVO|諾和諾德|GLP|減重|isrg/i, '生技與醫療'],
  [/巴菲特|berkshire|BRK|銀行|JPM|BAC/i, '傳統金融'],
  [/稀土|銅|copper|鋰|材料|MP\s*Material|FCX/i, '原物料與稀土'],
];

// 總體經濟 / 策略類關鍵字
const MACRO_KEYWORDS = /FOMC|聯準會|Fed |利率|通膨|inflation|GDP|總體|宏觀|macro|川普|關稅|tariff|貿易戰|牛市|熊市|週報|月報|年報|展望|outlook|策略|stock\s*market|大盤|指數|S&P|nasdaq|債券|bond|美元|USD|匯率|巴菲特.*信|股東信|資產配置|ETF(?!\s*財)|心靈|心得|總檢討|觀察清單|清單|private\s*credit|私募|槓桿|IPO|美債/i;

// ============================================================================
// 財報文章判斷
// ============================================================================

// 從標題抽取季度
function extractQuarter(filename: string): { ticker: string; quarter: string } | null {
  const name = filename.replace(/\.md$/, '').replace(/^\d{4}-\d{2}-\d{2}\s+/, '');

  // 嘗試各種財報標題模式
  const patterns: Array<RegExp> = [
    // "NVDA NVIDIA 2026 Q1 財報分析"
    /^([A-Z]{1,6})\s+.*?(\d{4})\s*(Q[1-4]|第[一二三四]季)/i,
    // "NVDA 2025年第四季財報"
    /^([A-Z]{1,6})\s+.*?(\d{4}).*?第([一二三四])季/i,
    // "$MU CEO ... Q2 財報"
    /^\$?([A-Z]{1,6})\s+.*?(\d{4})\s*(Q[1-4])/i,
    // "AMD 2025 年第二季財報亮點"
    /^([A-Z]{1,6})\s+.*?(\d{4})\s*年?\s*第([一二三四])季/i,
    // "AI Podcast PLTR Palantir 2025 年第四季財報亮點"
    /AI\s*Podcast\s+([A-Z]{1,6})\s+.*?(\d{4})\s*(?:年?\s*)?(?:財年)?第([一二三四])季/i,
    // "AFRM Affirm 2025第四季"
    /^([A-Z]{1,6})\s+.*?(\d{4})年?\s*第([一二三四])季/i,
    // "Roundhill Memory ETF #DRAM" style — no quarter, skip
  ];

  const chineseQMap: Record<string, string> = { 一: '1', 二: '2', 三: '3', 四: '4' };

  for (const pat of patterns) {
    const m = name.match(pat);
    if (!m) continue;

    let ticker = m[1]!.toUpperCase();
    const year = m[2]!;

    // Q格式 or 中文季
    let qStr = m[3] || '';
    if (/^Q[1-4]$/i.test(qStr)) {
      qStr = qStr.toUpperCase();
    } else if (chineseQMap[qStr]) {
      qStr = `Q${chineseQMap[qStr]}`;
    } else {
      continue;
    }

    // 優先使用全大寫的真實 ticker（排除年份和季度字串）
    const realTickerMatch = name.match(/\b([A-Z]{2,6})\b/);
    if (realTickerMatch) {
      const candidate = realTickerMatch[1]!;
      if (candidate !== year && !/^Q[1-4]$/.test(candidate) &&
          candidate !== 'AI' && candidate !== 'CEO' && candidate !== 'ETF') {
        ticker = candidate;
      }
    }

    return { ticker, quarter: `${year} ${qStr}` };
  }

  return null;
}

function isEarningsReport(filename: string): boolean {
  const name = filename.toLowerCase();
  return (
    (name.includes('財報') || name.includes('業績') || name.includes('亮點') ||
     name.includes('earnings') || name.includes('q1') || name.includes('q2') ||
     name.includes('q3') || name.includes('q4') || name.includes('第一季') ||
     name.includes('第二季') || name.includes('第三季') || name.includes('第四季')) &&
    // 排除非財報文章
    !name.includes('觀察清單') && !name.includes('展望') && !name.includes('預測')
  );
}

// ============================================================================
// 主要分類邏輯
// ============================================================================

function extractLeadingTicker(filename: string): string | null {
  const name = filename.replace(/^\d{4}-\d{2}-\d{2}\s+/, '').replace(/\.md$/, '');

  // "$MU CEO..." or "#DRAM..."
  const dollarHash = name.match(/^[\$#]([A-Z]{2,6})\b/);
  if (dollarHash) return dollarHash[1]!.toUpperCase();

  // "NVDA NVIDIA..." — 2-6 uppercase letters at start
  const leading = name.match(/^([A-Z]{2,6})\b/);
  if (leading && leading[1] !== 'AI' && leading[1] !== 'BE') return leading[1]!;

  // "AI Podcast NVDA NVIDIA..." — skip "AI Podcast" prefix
  const afterPodcast = name.match(/AI\s*Podcast\s+([A-Z]{2,6})\b/);
  if (afterPodcast) return afterPodcast[1]!.toUpperCase();

  return null;
}

function classifyFile(filename: string): {
  type: 'earnings' | 'sector' | 'macro' | 'other';
  destDir: string;
  ticker?: string;
  sector?: string;
  quarter?: string;
} {
  const name = filename.replace(/^\d{4}-\d{2}-\d{2}\s+/, '').replace(/\.md$/, '');

  // 1. 總體經濟 / 策略
  if (MACRO_KEYWORDS.test(name)) {
    return { type: 'macro', destDir: join(BASE_DIR, '總體經濟與策略') };
  }

  // 2. 財報分析
  if (isEarningsReport(filename)) {
    const q = extractQuarter(filename);
    if (q) {
      const ticker = q.ticker;
      const destDir = join(BASE_DIR, '財報分析', ticker, q.quarter);
      return { type: 'earnings', destDir, ticker, quarter: q.quarter };
    }
  }

  // 3. 族群分類
  const leadTicker = extractLeadingTicker(filename);

  // 先查 ticker map
  if (leadTicker && TICKER_TO_SECTOR[leadTicker]) {
    const sector = TICKER_TO_SECTOR[leadTicker]!;
    const destDir = join(BASE_DIR, '族群', sector, leadTicker);
    return { type: 'sector', destDir, ticker: leadTicker, sector };
  }

  // 再查 keyword map
  for (const [re, sector] of KEYWORD_TO_SECTOR) {
    if (re.test(name)) {
      const ticker = leadTicker || '其他';
      const destDir = join(BASE_DIR, '族群', sector, ticker);
      return { type: 'sector', destDir, ticker, sector };
    }
  }

  // fallback
  return { type: 'other', destDir: join(BASE_DIR, '其他') };
}

// ============================================================================
// 主程式
// ============================================================================

async function main() {
  console.log('============================================================');
  console.log('Uncle Stock Notes 分類工具');
  if (DRY_RUN) console.log('** DRY RUN 模式：不實際移動檔案 **');
  console.log(`來源目錄：${BASE_DIR}`);
  console.log('============================================================\n');

  // 讀取根目錄所有 .md 文件（不遞迴）
  const allFiles = await readdir(BASE_DIR);
  const mdFiles = allFiles.filter(f => f.endsWith('.md'));

  console.log(`共找到 ${mdFiles.length} 個 .md 文件\n`);

  // 統計
  const stats: Record<string, number> = { earnings: 0, sector: 0, macro: 0, other: 0 };
  const sectorCounts: Record<string, number> = {};
  const moves: Array<{ src: string; dest: string; label: string }> = [];

  for (const file of mdFiles) {
    const result = classifyFile(file);
    stats[result.type]++;

    const label = result.type === 'earnings'
      ? `財報分析/${result.ticker}/${result.quarter}`
      : result.type === 'sector'
        ? `族群/${result.sector}/${result.ticker}`
        : result.type === 'macro'
          ? '總體經濟與策略'
          : '其他';

    if (result.sector) {
      sectorCounts[result.sector] = (sectorCounts[result.sector] || 0) + 1;
    }

    moves.push({
      src: join(BASE_DIR, file),
      dest: join(result.destDir, file),
      label,
    });
  }

  // 印統計
  console.log('分類統計：');
  console.log(`  財報分析：${stats.earnings} 篇`);
  console.log(`  族群文章：${stats.sector} 篇`);
  console.log(`  總體經濟：${stats.macro} 篇`);
  console.log(`  其他：    ${stats.other} 篇`);
  console.log('\n族群明細：');
  for (const [s, n] of Object.entries(sectorCounts).sort((a, b) => b[1] - a[1])) {
    console.log(`  ${s.padEnd(20)}：${n} 篇`);
  }
  console.log('');

  if (DRY_RUN) {
    console.log('--- 前 30 筆移動預覽 ---');
    for (const m of moves.slice(0, 30)) {
      console.log(`  ${basename(m.src)}`);
      console.log(`    → ${m.label}`);
    }
    console.log('\n使用不含 --dry-run 執行以實際移動檔案。');
    return;
  }

  // 實際執行移動（用 shell mv 處理 Unicode 路徑）
  let moved = 0;
  let errors = 0;

  for (const m of moves) {
    try {
      await mkdir(dirname(m.dest), { recursive: true });
      const proc = Bun.spawn(['mv', m.src, m.dest], { stderr: 'pipe' });
      const exitCode = await proc.exited;
      if (exitCode !== 0) {
        const errText = await new Response(proc.stderr).text();
        throw new Error(errText.trim() || `exit code ${exitCode}`);
      }
      moved++;
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`❌ 移動失敗：${basename(m.src)} → ${msg}`);
      errors++;
    }
  }

  console.log(`\n完成！移動 ${moved} 篇，失敗 ${errors} 篇`);
  console.log(`\n目錄結構已建立於：${BASE_DIR}`);
}

main().catch(err => {
  console.error('嚴重錯誤：', err);
  process.exit(1);
});
