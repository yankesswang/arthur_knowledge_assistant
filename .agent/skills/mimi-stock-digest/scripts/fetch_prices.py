#!/usr/bin/env python3
"""
mimi-stock-digest 抓價工具。

用法：
  # 首推當時價 + 現價 + 報酬率（給 TICKER:DATE 清單）
  python3 fetch_prices.py AVGO:2026-03-06 INTC:2026-04-24 2454.TW:2026-04-28

  # 只抓現價快照（給多個 ticker）
  python3 fetch_prices.py --now AVGO NVDA MU TSM

輸出：CSV 到 stdout（ticker,rec_date,rec_close,cur_date,cur_close,return_pct,warn）。
- 台股 .TW（TWD）、深滬 .SZ/.SS（CNY）；美股 USD。
- <$10 標 LOWPRICE⚠️（yfinance ticker 對映常與現實不符，需人工複核）。
- 未上市/查無 → NODATA。
需要：pip install yfinance
"""
import sys, datetime

try:
    import yfinance as yf
except ImportError:
    sys.exit("需要 yfinance：pip install yfinance")


def close_on(tk, d, span=8):
    """回傳 d 當日（或之後第一個交易日）收盤與實際 bar 日期。"""
    end = (datetime.date.fromisoformat(d) + datetime.timedelta(days=span)).isoformat()
    try:
        h = yf.Ticker(tk).history(start=d, end=end)
        if len(h):
            return float(h["Close"].iloc[0]), h.index[0].strftime("%Y-%m-%d")
    except Exception:
        pass
    return None, ""


def latest_close(tk):
    try:
        h = yf.Ticker(tk).history(period="7d")
        if len(h):
            return float(h["Close"].iloc[-1]), h.index[-1].strftime("%Y-%m-%d")
    except Exception:
        pass
    return None, ""


def warn_for(tk, px):
    if px is not None and px < 10:
        return "LOWPRICE⚠️複核ticker"
    if tk.endswith(".TW"):
        return "TWD"
    if tk.endswith((".SZ", ".SS")):
        return "CNY"
    return ""


def main():
    args = sys.argv[1:]
    if not args:
        sys.exit(__doc__)

    print("ticker,rec_date,rec_close,cur_date,cur_close,return_pct,warn")

    if args[0] == "--now":
        for tk in args[1:]:
            cp, cd = latest_close(tk)
            cp_s = f"{cp:.2f}" if cp else "NODATA"
            print(f"{tk},,,{cd},{cp_s},,{warn_for(tk, cp)}")
        return

    for item in args:
        tk, _, d = item.partition(":")
        rp, rd = close_on(tk, d) if d else (None, "")
        cp, cd = latest_close(tk)
        ret = f"{(cp / rp - 1) * 100:+.1f}%" if (rp and cp) else ""
        rp_s = f"{rp:.2f}" if rp else "NODATA"
        cp_s = f"{cp:.2f}" if cp else "NODATA"
        print(f"{tk},{rd or d},{rp_s},{cd},{cp_s},{ret},{warn_for(tk, cp)}")


if __name__ == "__main__":
    main()
