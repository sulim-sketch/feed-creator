"""
BOBP 포트폴리오 일간 수익률 HTML 생성
Usage: python generate_portfolio.py
"""

import sys, os, glob, requests, yfinance as yf
import pandas as pd
from datetime import date, timedelta
from dotenv import load_dotenv

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

API_BASE  = "https://coresixteen-api-732000271547.asia-northeast3.run.app"
XLSX_DIR  = os.path.join(os.path.dirname(__file__), "xlsx")


def load_ticker_names() -> dict[str, str]:
    files = glob.glob(os.path.join(XLSX_DIR, "*.xlsx"))
    if not files:
        return {}
    df = pd.read_excel(files[0], header=None)
    data = df.iloc[14:].dropna(subset=[1])
    return {str(row[1]).strip(): str(row[2]).strip() for _, row in data.iterrows()}


def resolve_trading_date() -> date:
    start = (date.today() - timedelta(days=7)).isoformat()
    end   = date.today().isoformat()
    prices = yf.download("SPY", start=start, end=end, auto_adjust=True, progress=False)["Close"]
    return prices.index[-1].date()


def fetch_returns() -> list[dict]:
    res = requests.get(f"{API_BASE}/bobp/last-portfolio-returns?exclude=BIL", timeout=15)
    res.raise_for_status()
    items = res.json()["items"]
    return sorted(
        [{"ticker": it["ticker"], "d1": round(it["d1"] * 100, 2), "w1": round(it["w1"] * 100, 2)} for it in items],
        key=lambda x: x["d1"],
        reverse=True,
    )


def _pick_highlight(rows: list[dict]) -> str | None:
    # 1순위: 1일 수익률 8% 이상 중 최고
    top8 = [r for r in rows if r["d1"] >= 8.0]
    if top8:
        return max(top8, key=lambda r: r["d1"])["ticker"]
    # 2순위: 5일 수익률 20% 이상 & 오늘 양수 중 최고
    candidates = [r for r in rows if r["w1"] >= 20.0 and r["d1"] > 0]
    if candidates:
        return max(candidates, key=lambda r: r["d1"])["ticker"]
    return None


def generate_html(rows: list[dict], trading_date: date, names: dict[str, str]) -> str:
    max_abs   = max(abs(r["d1"]) for r in rows) or 1
    highlight = _pick_highlight(rows)

    def row_html(rank: int, r: dict) -> str:
        ret    = r["d1"]
        w1     = r["w1"]
        color  = "#0a9e5c" if ret >= 0 else "#d93025"
        w1color= "#0a9e5c" if w1 >= 0 else "#d93025"
        bg     = "rgba(10,158,92,0.05)" if ret >= 0 else "rgba(217,48,37,0.05)"
        sign   = "+" if ret >= 0 else ""
        w1sign = "+" if w1 >= 0 else ""
        bar_w  = round(abs(ret) / max_abs * 100, 1)
        name   = names.get(r["ticker"], "")
        is_hl  = r["ticker"] == highlight

        hl_style = ' highlight' if is_hl else ''
        return f"""
        <tr style="background:{bg};" class="data-row{hl_style}">
          <td class="rank">{rank}</td>
          <td class="ticker-cell">
            <span class="ticker">{r['ticker']}</span>
            {f'<span class="company">{name}</span>' if name else ''}
            {'<span class="feed-badge">FEED</span>' if is_hl else ''}
          </td>
          <td class="bar-cell">
            <div class="bar-inline">
              <span class="ret-label" style="color:{color};">{sign}{ret:.2f}%</span>
              <div class="bar-track">
                <div class="bar-fill" style="width:{bar_w}%;background:{color};{'margin-left:50%;' if ret >= 0 else f'margin-left:{50 - bar_w}%;'}"></div>
                <div class="bar-center"></div>
              </div>
            </div>
          </td>
          <td class="w1-ret" style="color:{w1color};">{w1sign}{w1:.2f}%</td>
        </tr>"""

    top_html  = "".join(row_html(i + 1, r) for i, r in enumerate(rows[:5]))
    rest_html = "".join(row_html(i + 6, r) for i, r in enumerate(rows[5:]))
    rows_html = top_html
    positive  = sum(1 for r in rows if r["d1"] >= 0)
    negative  = len(rows) - positive
    avg       = sum(r["d1"] for r in rows) / len(rows)
    avg_sign  = "+" if avg >= 0 else ""
    avg_color = "#0a9e5c" if avg >= 0 else "#d93025"
    date_str  = trading_date.strftime("%B %#d, %Y") if sys.platform == "win32" else trading_date.strftime("%B %-d, %Y")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>BOBP Portfolio — {date_str}</title>
  <style>
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: #f4f6f9;
      color: #1a2233;
      font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif;
      min-height: 100vh;
      padding: 40px 24px 60px;
    }}

    .page-wrap {{
      max-width: 820px;
      margin: 0 auto;
    }}

    /* ── header ── */
    header {{
      display: flex;
      align-items: flex-end;
      justify-content: space-between;
      border-bottom: 1px solid #dce3ed;
      padding-bottom: 18px;
      margin-bottom: 28px;
    }}
    .brand {{ font-size: 11px; letter-spacing: 0.12em; color: #8a9ab0; text-transform: uppercase; }}
    h1 {{
      font-size: 22px;
      font-weight: 600;
      color: #0f1a2e;
      letter-spacing: -0.02em;
      margin-top: 4px;
    }}
    .date-badge {{
      font-size: 12px;
      color: #5a7090;
      background: #ffffff;
      border: 1px solid #dce3ed;
      border-radius: 6px;
      padding: 6px 14px;
      white-space: nowrap;
    }}

    /* ── stats row ── */
    .stats {{
      display: flex;
      gap: 12px;
      margin-bottom: 28px;
    }}
    .stat-card {{
      flex: 1;
      background: #ffffff;
      border: 1px solid #dce3ed;
      border-radius: 10px;
      padding: 14px 18px;
    }}
    .stat-label {{ font-size: 10px; letter-spacing: 0.1em; color: #8a9ab0; text-transform: uppercase; margin-bottom: 6px; }}
    .stat-value {{ font-size: 20px; font-weight: 600; letter-spacing: -0.02em; }}

    /* ── table ── */
    .table-wrap {{
      background: #ffffff;
      border: 1px solid #dce3ed;
      border-radius: 12px;
      overflow: hidden;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
    }}
    thead tr {{
      background: #f8fafc;
    }}
    th {{
      font-size: 10px;
      letter-spacing: 0.1em;
      color: #8a9ab0;
      text-transform: uppercase;
      padding: 12px 16px;
      text-align: left;
      font-weight: 500;
      border-bottom: 1px solid #dce3ed;
    }}
    th.ret, td.ret {{ text-align: right; }}
    th.w1-ret, td.w1-ret {{ text-align: right; font-weight: 600; font-size: 14px; font-variant-numeric: tabular-nums; white-space: nowrap; }}
    th.bar-cell, td.bar-cell {{ width: 42%; }}

    tbody tr {{
      border-bottom: 1px solid #eef1f6;
      transition: background 0.15s;
    }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody tr:hover {{ background: #f4f7fb !important; }}

    td {{
      padding: 11px 16px;
      font-size: 13.5px;
    }}
    td.rank {{
      color: #b0bece;
      font-size: 12px;
      width: 44px;
    }}
    td.ticker-cell {{
      font-size: 13.5px;
    }}
    .ticker {{
      font-weight: 600;
      font-size: 14px;
      color: #0f1a2e;
      letter-spacing: 0.03em;
      display: inline-block;
      margin-right: 8px;
    }}
    .company {{
      font-size: 12px;
      color: #8a9ab0;
      font-weight: 400;
    }}
    td.ticker {{
      font-weight: 600;
      font-size: 14px;
      color: #0f1a2e;
      letter-spacing: 0.03em;
    }}
    td.ret {{
      font-weight: 600;
      font-size: 14px;
      font-variant-numeric: tabular-nums;
    }}

    /* ── bar ── */
    .bar-cell {{ padding: 11px 16px 11px 8px; }}
    .bar-track {{
      position: relative;
      height: 6px;
      background: #0a1018;
      border-radius: 3px;
      overflow: hidden;
    }}
    .bar-inline {{
      display: flex;
      align-items: center;
      gap: 10px;
    }}
    .ret-label {{
      font-weight: 600;
      font-size: 14px;
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
      min-width: 60px;
      text-align: right;
    }}
    .bar-fill {{
      position: absolute;
      top: 0;
      height: 100%;
      border-radius: 3px;
      min-width: 2px;
    }}
    .bar-center {{
      position: absolute;
      left: 50%;
      top: 0;
      width: 1px;
      height: 100%;
      background: #dce3ed;
    }}

    /* ── highlight ── */
    tr.highlight {{
      outline: 2px solid #f5a623;
      outline-offset: -2px;
      background: rgba(245,166,35,0.07) !important;
    }}
    tr.highlight:hover {{ background: rgba(245,166,35,0.12) !important; }}
    .feed-badge {{
      display: inline-block;
      margin-left: 8px;
      padding: 1px 7px;
      font-size: 10px;
      font-weight: 700;
      letter-spacing: 0.08em;
      color: #f5a623;
      background: rgba(245,166,35,0.12);
      border: 1px solid rgba(245,166,35,0.4);
      border-radius: 4px;
      vertical-align: middle;
    }}

    /* ── expand button ── */
    .expand-btn {{
      display: block;
      width: 100%;
      padding: 12px;
      background: #f8fafc;
      border: none;
      border-top: 1px solid #eef1f6;
      color: #5a7090;
      font-size: 12px;
      font-weight: 500;
      letter-spacing: 0.04em;
      cursor: pointer;
      transition: background 0.15s, color 0.15s;
    }}
    .expand-btn:hover {{
      background: #eef1f6;
      color: #1a2233;
    }}

    /* ── footer ── */
    footer {{
      margin-top: 20px;
      text-align: right;
      font-size: 11px;
      color: #b0bece;
    }}
  </style>
</head>
<body>
  <div class="page-wrap">
    <header>
      <div>
        <div class="brand">Core Sixteen</div>
        <h1>BOBP Portfolio Returns</h1>
      </div>
      <div class="date-badge">{date_str}</div>
    </header>

    <div class="stats">
      <div class="stat-card">
        <div class="stat-label">Holdings</div>
        <div class="stat-value" style="color:#d0ddf0;">{len(rows)}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Avg Daily Return</div>
        <div class="stat-value" style="color:{avg_color};">{avg_sign}{avg:.2f}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Advancing</div>
        <div class="stat-value" style="color:#0a9e5c;">{positive}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Declining</div>
        <div class="stat-value" style="color:#d93025;">{negative}</div>
      </div>
    </div>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>#</th>
            <th>Ticker / Company</th>
            <th class="bar-cell">1D Return</th>
            <th class="w1-ret">5D Return</th>
          </tr>
        </thead>
        <tbody id="top-rows">
          {rows_html}
        </tbody>
        <tbody id="rest-rows" style="display:none;">
          {rest_html}
        </tbody>
      </table>
      <button class="expand-btn" id="expand-btn" onclick="toggleRows()">
        Show {len(rows) - 5} more ▾
      </button>
    </div>

    <footer>1D = daily return &nbsp;·&nbsp; 5D = 5-business-day return (API w1) &nbsp;·&nbsp; BOBP excludes BIL &nbsp;·&nbsp; Data via Yahoo Finance</footer>
    <script>
      function toggleRows() {{
        var rest = document.getElementById('rest-rows');
        var btn  = document.getElementById('expand-btn');
        if (rest.style.display === 'none') {{
          rest.style.display = '';
          btn.textContent = 'Show less ▴';
        }} else {{
          rest.style.display = 'none';
          btn.textContent = 'Show {len(rows) - 5} more ▾';
        }}
      }}
    </script>
  </div>
</body>
</html>"""


def main():
    print("거래일 확인 중...")
    trading_date = resolve_trading_date()
    print(f"  -> {trading_date}")

    print("종목명 로드 중...")
    names = load_ticker_names()
    print(f"  -> {len(names)}개 매핑")

    print("포트폴리오 수익률 조회 중...")
    rows = fetch_returns()
    print(f"  -> {len(rows)}개 종목")

    html = generate_html(rows, trading_date, names)
    out_path = "portfolio.html"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n완료: {out_path}")


if __name__ == "__main__":
    main()
