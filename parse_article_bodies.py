import sys, json
from playwright.sync_api import sync_playwright

sys.stdout.reconfigure(encoding='utf-8')

with open("sndk_after_close_news.json", encoding="utf-8") as f:
    articles = json.load(f)

def fetch_body(page, url: str) -> list[str]:
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)

    # 동의 버튼 클릭 (Yahoo Finance GDPR 팝업)
    try:
        page.click('button:has-text("Accept all")', timeout=3000)
        page.wait_for_timeout(1000)
    except Exception:
        pass

    # data-testid="article-body" 내 <p> 태그
    body_el = page.query_selector('[data-testid="article-body"]')
    if body_el:
        paras = body_el.query_selector_all("p")
        return "\n\n".join(p.inner_text().strip() for p in paras if p.inner_text().strip())

    # 대체: <article> 내 <p>
    article_el = page.query_selector("article")
    if article_el:
        paras = article_el.query_selector_all("p")
        return "\n\n".join(p.inner_text().strip() for p in paras if p.inner_text().strip())

    return ""

results = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_page(user_agent=(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/125.0.0.0 Safari/537.36"
    ))
    for a in articles:
        print(f"파싱 중: {a['title'][:60]}...")
        body = fetch_body(page, a["url"])
        print(f"  -> {len(body)}자")
        results.append({**a, "body": body})
    browser.close()

out_path = "sndk_after_close_news_body.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n저장: {out_path}")
