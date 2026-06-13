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
NEWS_TARGET = 20
EXCLUDE_PUBLISHER = "barrons.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


# ── 1. 거래일 결정 ─────────────────────────────────────────────────────────────
def resolve_trading_date(arg: str | None) -> date:
    if arg:
        return date.fromisoformat(arg)
    d = date.today()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


# ── 2. 포트폴리오 티커 조회 ────────────────────────────────────────────────────
def fetch_tickers() -> list[str]:
    res = requests.get(f"{API_BASE}/bobp/last-portfolio-returns?exclude=BIL", timeout=15)
    res.raise_for_status()
    return [item["ticker"] for item in res.json()["items"]]


# ── 3. 종목 선정 ──────────────────────────────────────────────────────────────
def select_ticker(tickers: list[str], trading_date: date) -> tuple[str, float] | None:
    start = (trading_date - timedelta(days=14)).isoformat()
    end   = (trading_date + timedelta(days=1)).isoformat()
    raw = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    df = raw if hasattr(raw, "columns") else raw.to_frame()

    day_str  = trading_date.isoformat()
    available = [d for d in df.index if str(d.date()) <= day_str]
    if len(available) < 2:
        raise ValueError(f"수익률 계산에 충분한 데이터 없음 ({trading_date})")

    daily = ((df.loc[available[-1]] - df.loc[available[-2]]) / df.loc[available[-2]] * 100).dropna()

    # 1순위: 오늘 상승률 1위가 8% 이상
    best = str(daily.idxmax())
    best_ret = float(daily[best])
    if best_ret >= 8.0:
        print(f"  -> 1순위 조건 충족: {best} ({best_ret:+.2f}%)")
        return best, best_ret

    # 2순위: 최근 5 영업일 20% 이상 상승 종목 중 오늘 상승률 최고
    print(f"  -> 1순위 미충족 (최고 {best_ret:+.2f}%), 2순위 조건 탐색...")
    if len(available) >= 6:
        five_day = ((df.loc[available[-1]] - df.loc[available[-6]]) / df.loc[available[-6]] * 100).dropna()
        qualified = five_day[five_day >= 20.0]
        if not qualified.empty:
            candidates = daily[daily.index.isin(qualified.index)]
            if not candidates.empty:
                pick = str(candidates.idxmax())
                pick_ret = float(candidates[pick])
                print(f"  -> 2순위 조건 충족: {pick} ({pick_ret:+.2f}%, 5일 수익률 {five_day[pick]:+.2f}%)")
                return pick, pick_ret

    return None


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
            if url in seen or EXCLUDE_PUBLISHER.lower() in publisher.lower():
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
    result = []
    for a in articles:
        pub = fetch_published_at(a["url"])
        if pub is None:
            print(f"    날짜 없음: {a['title'][:55]}")
            continue
        flag = "✓" if pub > market_close else "✗"
        print(f"    {flag} {pub.strftime('%Y-%m-%d %H:%M ET')} | {a['title'][:50]}")
        if pub > market_close:
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
def summarize_reason(ticker: str, articles: list[dict]) -> str:
    combined = "\n\n---\n\n".join(
        f"[{a['title']}]\n{a['body']}" for a in articles if a.get("body")
    )
    prompt = (
        f"The following are news articles published after market close about {ticker} stock, "
        f"which had the highest daily return in the portfolio today.\n\n"
        f"{combined}\n\n"
        f"In 1-2 sentences, explain why {ticker} stock rose today. "
        f"Be concise and direct — synthesize only the single most important reason in your own words. "
        f"Do not copy phrases from the articles. Write naturally, like a person giving a quick explanation to a colleague. "
        f"Then leave exactly one blank line, and write one concise hook sentence that draws the reader's curiosity. "
        f"Keep it short and sharp. Sometimes pose it as a direct question, other times as a brief observation — "
        f"choose whichever feels more natural for today's context. "
        f"Strictly neutral: no buy/sell recommendations, no urgency to act. "
        f"Sound like a knowledgeable market observer, not a news article. "
        f"Do not add any labels or section headers. Output only plain text."
    )
    models = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]
    last_err = None
    for model in models:
        for attempt in range(3):
            try:
                resp = _genai.models.generate_content(model=model, contents=prompt)
                return resp.text.strip()
            except genai_errors.ServerError as e:
                last_err = e
                time.sleep(5 * (attempt + 1))
        if last_err is None:
            break
    raise last_err


# ── 메인 ──────────────────────────────────────────────────────────────────────
def main():
    # Usage: python pipeline.py [YYYY-MM-DD] [TICKER]
    args = sys.argv[1:]
    date_arg   = next((a for a in args if re.match(r"\d{4}-\d{2}-\d{2}", a)), None)
    ticker_arg = next((a for a in args if not re.match(r"\d{4}-\d{2}-\d{2}", a)), None)

    trading_date = resolve_trading_date(date_arg)
    print(f"\n[1/6] 거래일: {trading_date}")

    if ticker_arg:
        ticker = ticker_arg.upper()
        print(f"[2/6] 지정 티커: {ticker}")
        print(f"[3/6] 일간 수익률 계산...")
        result = select_ticker([ticker], trading_date)
        if result is None:
            print(f"  -> {ticker} 선정 조건 미충족. 파이프라인 종료.")
            return
        ticker, ret = result
    else:
        print("[2/6] 포트폴리오 티커 조회...")
        tickers = fetch_tickers()
        print(f"  -> {len(tickers)}개 티커")

        print(f"[3/6] 종목 선정...")
        result = select_ticker(tickers, trading_date)
        if result is None:
            print("  -> 조건을 만족하는 종목 없음. 파이프라인 종료.")
            return
        ticker, ret = result

    print(f"[4/6] 키워드 추출...")
    keywords = get_ticker_keywords(ticker)
    print(f"  -> {keywords}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)

        print(f"[5/6] 뉴스 스크래핑 (최대 {NEWS_TARGET}개, Barrons 제외)...")
        raw_news = scrape_news(page, ticker, NEWS_TARGET)
        print(f"  -> {len(raw_news)}개 수집")

        filtered = filter_by_keywords(raw_news, ticker, keywords)
        print(f"  -> 제목 필터링 후 {len(filtered)}개")

        print(f"  -> 정규장 마감({trading_date} 16:00 ET) 이후 필터링...")
        after_close = filter_after_close(filtered, trading_date)
        print(f"  -> {len(after_close)}개 통과")

        print("[6/6] 본문 파싱...")
        final = []
        for a in after_close:
            print(f"  파싱: {a['title'][:60]}...")
            body = fetch_body(page, a["url"])
            print(f"    -> {len(body)}자")
            final.append({**a, "body": body})

        browser.close()

    print("[7/6] Gemma 요약 생성...")
    date_label = trading_date.strftime("%B %-d, %Y") if sys.platform != "win32" else trading_date.strftime("%B %#d, %Y")
    headline = f"${ticker} rose {ret:.2f}% on {date_label}. $BOBP index includes ${ticker}."
    body_summary = summarize_reason(ticker, final) if final else "(기사 없음)"
    summary = f"{headline}\n{body_summary}"
    print(f"\n  {summary}")

    output = {
        "ticker": ticker,
        "trading_date": trading_date.isoformat(),
        "return_pct": round(ret, 2),
        "keywords": keywords,
        "summary": summary,
        "articles": final,
    }
    out_path = f"{ticker.lower()}_{trading_date}_news.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n완료: {out_path} ({len(final)}개 기사)")


if __name__ == "__main__":
    main()
