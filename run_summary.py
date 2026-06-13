import sys, os, json, time
sys.stdout.reconfigure(encoding="utf-8")
from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from datetime import date

load_dotenv()
_genai = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

def summarize_reason(ticker, articles):
    combined = "\n\n---\n\n".join(
        f"[{a['title']}]\n{a['body']}" for a in articles if a.get("body")
    )
    prompt = (
        f"The following are news articles published after market close about {ticker} stock, "
        f"which had the highest daily return in the portfolio today.\n\n"
        f"{combined}\n\n"
        f"In 1-2 sentences, explain why {ticker} stock rose today. "
        f"Be concise and direct -- synthesize only the single most important reason in your own words. "
        f"Do not copy phrases from the articles. Write naturally, like a person giving a quick explanation to a colleague. "
        f"Then leave exactly one blank line, and write one concise hook sentence that draws the reader's curiosity. "
        f"Keep it short and sharp. Sometimes pose it as a direct question, other times as a brief observation -- "
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

for fname in ["sndk_2026-06-11_news.json", "lrcx_2026-06-11_news.json"]:
    with open(fname, encoding="utf-8") as f:
        data = json.load(f)
    if not data["articles"]:
        print(f"[{fname}] 기사 없음, 스킵")
        continue
    ticker = data["ticker"]
    ret = data["return_pct"]
    print(f"\n=== {ticker} ({ret:+.2f}%) ===")
    summary_body = summarize_reason(ticker, data["articles"])
    d = date.fromisoformat(data["trading_date"])
    date_label = d.strftime("%B %#d, %Y")
    headline = f"${ticker} rose {ret:.2f}% on {date_label}. $BOBP index includes ${ticker}."
    full_summary = f"{headline}\n{summary_body}"
    print(full_summary)
    data["summary"] = full_summary
    with open(fname, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"-> {fname} 저장 완료")
