import os
import json
import time
import yfinance as yf
from google import genai
from google.genai import errors as genai_errors
from dotenv import load_dotenv

load_dotenv()
_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def get_ticker_keywords(ticker: str) -> list[str]:
    info = yf.Ticker(ticker).info
    short = info.get("shortName", "")
    long_ = info.get("longName", "")

    prompt = (
        f"Stock ticker: '{ticker}'\n"
        f"Yahoo Finance shortName: {short!r}\n"
        f"Yahoo Finance longName:  {long_!r}\n\n"
        f"List the search keywords an investor would naturally use to look up news about this company. "
        f"Rules:\n"
        f"- Include the brand name people actually use (e.g. 'Robinhood', not 'Robinhood Markets')\n"
        f"- If the company has a well-known alternative name, include both "
        f"(e.g. Alphabet → ['Google', 'Alphabet'])\n"
        f"- Short forms are fine if commonly used (e.g. 'Berkshire' alongside 'Berkshire Hathaway')\n"
        f"- Remove legal suffixes (Inc, Corp, Ltd, Corporation, Holdings, Group, Markets, etc.)\n"
        f"- Remove truncated or incomplete parenthetical expressions\n"
        f"- Do NOT invent keywords — only include names people genuinely search for\n"
        f"- Most tickers will have just one keyword\n"
        f"- Return a JSON array of strings only, no explanation. Example: [\"Google\", \"Alphabet\"]"
    )

    models = ["gemma-4-26b-a4b-it", "gemma-4-31b-it"]
    last_err = None
    response = None
    for model in models:
        for attempt in range(3):
            try:
                response = _client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                last_err = None
                break
            except genai_errors.ServerError as e:
                last_err = e
                time.sleep(5 * (attempt + 1))
        if last_err is None:
            break
    if last_err:
        raise last_err

    text = response.text.strip()
    # 마크다운 코드블록 제거
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())
