import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open('sndk_after_close_news_body.json', encoding='utf-8') as f:
    data = json.load(f)
for a in data:
    print(f"=== {a['title']} ===")
    print(a['body'][:400])
    print("...\n")
