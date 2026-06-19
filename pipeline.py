"""
Pipeline: 포트폴리오 최고 수익률 티커 → 뉴스 수집 → 필터링 → 본문 파싱
Usage: python pipeline.py [YYYY-MM-DD]
  날짜 생략 시 가장 최근 평일 기준
"""

import sys, os, re, json, urllib.request
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

import time
import requests
import yfinance as yf
from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors

from ticker_name import get_ticker_keywords

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")
_genai = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

ET = ZoneInfo("America/New_York")
API_BASE = "https://coresixteen-api-732000271547.asia-northeast3.run.app"
NEWS_TARGET = 50
EXCLUDE_PUBLISHER = "barrons.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


# ── 1. 거래일 결정 ─────────────────────────────────────────────────────────────
def resolve_trading_date(arg: str | None) -> date:
    if arg:
        return date.fromisoformat(arg)
    start = (date.today() - timedelta(days=7)).isoformat()
    end   = date.today().isoformat()
    prices = yf.download("SPY", start=start, end=end, auto_adjust=True, progress=False)["Close"]
    return prices.index[-1].date()


# ── 2. 일간 수익률 계산 ────────────────────────────────────────────────────────
def get_daily_return(ticker: str, trading_date: date) -> float:
    start = (trading_date - timedelta(days=7)).isoformat()
    end   = date.today().isoformat()
    raw   = yf.download([ticker], start=start, end=end, auto_adjust=True, progress=False)["Close"]
    df    = raw if hasattr(raw, "columns") else raw.to_frame()
    available = [d for d in df.index if d.date() <= trading_date]
    if len(available) < 2:
        return 0.0
    daily = ((df.loc[available[-1]] - df.loc[available[-2]]) / df.loc[available[-2]] * 100).dropna()
    return round(float(daily.get(ticker, 0.0)), 2)


# ── 4. Yahoo Finance 뉴스 스크래핑 ────────────────────────────────────────────
def scrape_news(page, ticker: str, target: int) -> list[dict]:
    page.goto(f"https://finance.yahoo.com/quote/{ticker}/news/", wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    try:
        page.click('button:has-text("Accept all")', timeout=3000)
        page.wait_for_timeout(1000)
    except Exception:
        pass

    articles, seen = [], set()
    for _ in range(30):
        for item in page.query_selector_all("li.stream-item, li[class*='stream']"):
            h3 = item.query_selector("h3")
            a_tag = item.query_selector("a[href]")
            pub_div = item.query_selector("div[class*='publishing']")
            if not (h3 and a_tag):
                continue
            title = h3.inner_text().strip()
            href = a_tag.get_attribute("href") or ""
            url = href if href.startswith("http") else f"https://finance.yahoo.com{href}"
            publisher = pub_div.inner_text().split("•")[0].strip() if pub_div else ""
            if url in seen:
                continue
            seen.add(url)
            articles.append({"title": title, "url": url, "publisher": publisher})
            if len(articles) >= target:
                return articles
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(2000)
    return articles


# ── 5. 제목 키워드 필터링 ──────────────────────────────────────────────────────
def filter_by_keywords(articles: list[dict], ticker: str, keywords: list[str]) -> list[dict]:
    terms = {ticker.upper()} | {k.lower() for k in keywords}
    return [a for a in articles if any(t.lower() in a["title"].lower() for t in terms)]


# ── 6. 정규장 마감 후 필터링 ───────────────────────────────────────────────────
def fetch_published_at(url: str) -> datetime | None:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        m = re.search(r'<time\b[^>]*datetime="([^"]+)"', html) or \
            re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        if m:
            return datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).astimezone(ET)
    except Exception as e:
        print(f"    [날짜 오류] {e}")
    return None

def filter_after_close(articles: list[dict], trading_date: date) -> list[dict]:
    market_close = datetime(trading_date.year, trading_date.month, trading_date.day, 16, 0, 0, tzinfo=ET)
    cutoff       = datetime(trading_date.year, trading_date.month, trading_date.day, 21, 0, 0, tzinfo=ET)
    result = []
    for a in articles:
        pub = fetch_published_at(a["url"])
        if pub is None:
            print(f"    날짜 없음: {a['title'][:55]}")
            continue
        in_window = market_close < pub <= cutoff
        flag = "✓" if in_window else "✗"
        print(f"    {flag} {pub.strftime('%Y-%m-%d %H:%M ET')} | {a['title'][:50]}")
        if in_window:
            result.append({**a, "published_et": pub.isoformat()})
    return result


# ── 7. 본문 파싱 ──────────────────────────────────────────────────────────────
def fetch_body(page, url: str) -> str:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    try:
        page.click('button:has-text("Accept all")', timeout=3000)
        page.wait_for_timeout(1000)
    except Exception:
        pass
    for selector in ['[data-testid="article-body"]', "article"]:
        el = page.query_selector(selector)
        if el:
            paras = el.query_selector_all("p")
            return "\n\n".join(p.inner_text().strip() for p in paras if p.inner_text().strip())
    return ""


# ── 8. Gemma 요약 ─────────────────────────────────────────────────────────────
def _parse_versions(text: str) -> dict:
    def extract(marker: str) -> str:
        m = re.search(rf'---{marker}---\n(.*?)---END {marker}---', text, re.DOTALL)
        raw = m.group(1).strip() if m else text.strip()
        paragraphs = [p.strip() for p in re.split(r'\n{2,}', raw) if p.strip()]
        return '\n\n'.join(paragraphs)
    return {"x": extract("X"), "linkedin": extract("LINKEDIN")}


def summarize_reason(ticker: str, articles: list[dict]) -> dict:
    combined = "\n\n---\n\n".join(
        f"[{a['title']}]\n{a['body']}" for a in articles
        if a.get("body") and EXCLUDE_PUBLISHER.lower() not in a.get("publisher", "").lower()
    )
    prompt = (
        f"The following are news articles published after market close about {ticker}, "
        f"which posted the highest return in the portfolio today.\n\n"
        f"{combined}\n\n"
        f"Generate two versions of a post about today's move. Output them in the exact format below — "
        f"no labels beyond the markers, no extra commentary.\n\n"
        f"---X---\n"
        f"One sentence: the real driver behind today's move — not the headline, but what actually caused the reprice. "
        f"Tight and specific. Write in your own words.\n"
        f"[blank line]\n"
        f"One sentence only: the sharpest unresolved tension or forward-looking question this move raises. "
        f"Must be under 100 characters. Punchy, not academic. Neutral — no buy/sell signals.\n"
        f"---END X---\n\n"
        f"---LINKEDIN---\n"
        f"Two to three sentences unpacking today's move. Start with the core driver, then briefly explain the mechanism — "
        f"why does this matter structurally, not just for today? Make it feel like a knowledgeable colleague connecting the dots, "
        f"not a news recap. Write in your own words.\n"
        f"[blank line]\n"
        f"One to two sentences that give the reader something to think about — a forward-looking tension, a broader implication, "
        f"or a question worth sitting with. More reflective than provocative. Neutral — no buy/sell signals.\n"
        f"---END LINKEDIN---"
    )
    models = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]
    last_err = None
    for model in models:
        for attempt in range(3):
            try:
                resp = _genai.models.generate_content(model=model, contents=prompt)
                return _parse_versions(resp.text)
            except genai_errors.ServerError as e:
                last_err = e
                time.sleep(5 * (attempt + 1))
        if last_err is None:
            break
    raise last_err


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    # Usage: python pipeline.py TICKER [YYYY-MM-DD]
    args = sys.argv[1:]
    date_arg   = next((a for a in args if re.match(r"\d{4}-\d{2}-\d{2}", a)), None)
    ticker_arg = next((a for a in args if not re.match(r"\d{4}-\d{2}-\d{2}", a)), None)

    if not ticker_arg:
        print("에러: 티커를 인자로 넘겨주세요. 예) python pipeline.py MU 2026-06-12")
        sys.exit(1)

    trading_date = resolve_trading_date(date_arg)
    ticker = ticker_arg.upper()
    print(f"\n[1/5] 거래일: {trading_date}  티커: {ticker}")

    print(f"[2/5] 일간 수익률 계산...")
    ret = get_daily_return(ticker, trading_date)
    print(f"  -> {ret:+.2f}%")

    print(f"[3/5] 키워드 추출...")
    keywords = get_ticker_keywords(ticker)
    print(f"  -> {keywords}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        print(f"[4/5] 뉴스 스크래핑 (최대 {NEWS_TARGET}개)...")
        raw_news = scrape_news(page, ticker, NEWS_TARGET)
        print(f"  -> {len(raw_news)}개 수집")

        filtered = filter_by_keywords(raw_news, ticker, keywords)
        print(f"  -> 제목 필터링 후 {len(filtered)}개")

        print(f"  -> 정규장 마감({trading_date} 16:00 ET) 이후 필터링...")
        after_close = filter_after_close(filtered, trading_date)
        print(f"  -> {len(after_close)}개 통과")

        print("[4/5] 본문 파싱...")
        final = []
        for a in after_close:
            print(f"  파싱: {a['title'][:60]}...")
            body = fetch_body(page, a["url"])
            print(f"    -> {len(body)}자")
            final.append({**a, "body": body})

        browser.close()

    print("[5/5] Gemma 요약 생성...")
    date_label = trading_date.strftime("%B %-d, %Y") if sys.platform != "win32" else trading_date.strftime("%B %#d, %Y")
    headline = f"${ticker} rose {ret:.2f}% on {date_label}. $BOBP index includes ${ticker}."
    empty = {"x": "(기사 없음)", "linkedin": "(기사 없음)"}
    versions = summarize_reason(ticker, final) if final else empty
    summary_x        = f"{headline}\n{versions['x']}"
    summary_linkedin = f"{headline}\n{versions['linkedin']}"
    print(f"\n[X]\n{summary_x}")
    print(f"\n[LinkedIn]\n{summary_linkedin}")

    output = {
        "ticker": ticker,
        "trading_date": trading_date.isoformat(),
        "return_pct": round(ret, 2),
        "keywords": keywords,
        "summary_x": summary_x,
        "summary_linkedin": summary_linkedin,
        "articles": final,
    }
    out_path = f"{ticker.lower()}_{trading_date}_news.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n완료: {out_path} ({len(final)}개 기사)")


if __name__ == "__main__":
    main()
