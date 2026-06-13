"""
Yahoo Finance 뉴스 스크래퍼
Usage: python scrape_news.py <TICKER> [기사수]
  기사수 생략 시 기본 20개
"""

import sys, json
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding="utf-8")

EXCLUDE_PUBLISHER = "barrons.com"
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def scrape_news(ticker: str, target: int = 20) -> list[dict]:
    articles, seen = [], set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        page = browser.new_page(user_agent=UA)
        page.goto(f"https://finance.yahoo.com/quote/{ticker}/news/", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)
        try:
            page.click('button:has-text("Accept all")', timeout=3000)
            page.wait_for_timeout(1000)
        except Exception:
            pass

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
                    browser.close()
                    return articles
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(2000)

        browser.close()
    return articles


def main():
    args = sys.argv[1:]
    if not args:
        print("Usage: python scrape_news.py <TICKER> [기사수]")
        sys.exit(1)

    ticker = args[0].upper()
    target = int(args[1]) if len(args) > 1 else 20

    print(f"[{ticker}] 뉴스 스크래핑 (최대 {target}개, Barrons 제외)...")
    articles = scrape_news(ticker, target)
    print(f"  -> {len(articles)}개 수집")
    for i, a in enumerate(articles, 1):
        print(f"  {i:2}. [{a['publisher']}] {a['title']}")

    out_path = f"{ticker.lower()}_news_raw.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(articles, f, ensure_ascii=False, indent=2)
    print(f"\n저장: {out_path}")


if __name__ == "__main__":
    main()
