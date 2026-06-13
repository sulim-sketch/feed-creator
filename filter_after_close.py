import sys, re, json, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

sys.stdout.reconfigure(encoding='utf-8')

ET = ZoneInfo('America/New_York')
TRADING_DATE = "2026-06-11"
MARKET_CLOSE_ET = datetime(2026, 6, 11, 16, 0, 0, tzinfo=ET)

with open("sndk_filtered_news.json", encoding="utf-8") as f:
    articles = json.load(f)

def fetch_published_at(url: str) -> datetime | None:
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            html = r.read().decode("utf-8", errors="replace")
        m = re.search(r'<time\b[^>]*datetime="([^"]+)"', html)
        if not m:
            m = re.search(r'"datePublished"\s*:\s*"([^"]+)"', html)
        if m:
            return datetime.fromisoformat(m.group(1).replace("Z", "+00:00")).astimezone(ET)
    except Exception as e:
        print(f"  [오류] {url}: {e}")
    return None

results = []
for a in articles:
    published_et = fetch_published_at(a["url"])
    if published_et is None:
        print(f"날짜 없음 | {a['title']}")
        continue

    after = published_et > MARKET_CLOSE_ET
    status = "✓ 마감 후" if after else "✗ 마감 전"
    print(f"{status} | {published_et.strftime('%Y-%m-%d %H:%M ET')} | {a['title']}")

    if after:
        results.append({**a, "published_et": published_et.isoformat()})

print(f"\n정규장({TRADING_DATE} 16:00 ET) 이후 기사: {len(results)}/{len(articles)}개")

out_path = "sndk_after_close_news.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"저장: {out_path}")
