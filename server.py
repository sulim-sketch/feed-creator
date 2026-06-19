"""
Feed Creator — Local Server
Usage: python server.py  →  http://localhost:5000
"""

import sys, os, glob, subprocess, json
from concurrent.futures import ThreadPoolExecutor
from datetime import date as date_type, timedelta
from typing import Any, Optional

import requests as http_req
import yfinance as yf
import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from dotenv import load_dotenv, set_key

load_dotenv()
sys.stdout.reconfigure(encoding="utf-8")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(BASE_DIR, ".env")
XLSX_DIR = os.path.join(BASE_DIR, "xlsx")
API_BASE = "https://coresixteen-api-732000271547.asia-northeast3.run.app"

app = FastAPI()


# ── data ─────────────────────────────────────────────────────────────────────

def resolve_trading_date() -> date_type:
    start  = (date_type.today() - timedelta(days=7)).isoformat()
    end    = date_type.today().isoformat()
    prices = yf.download("SPY", start=start, end=end, auto_adjust=True, progress=False)["Close"]
    return prices.index[-1].date()


def fetch_returns(trading_date: date_type, tickers: list[str]) -> tuple[list[dict], date_type]:
    start = (trading_date - timedelta(days=20)).isoformat()
    end   = date_type.today().isoformat()
    raw   = yf.download(tickers, start=start, end=end, auto_adjust=True, progress=False)["Close"]
    df    = raw if hasattr(raw, "columns") else raw.to_frame()

    available = [d for d in df.index if d.date() <= trading_date]
    if len(available) < 2:
        return [], trading_date

    actual_date = available[-1].date()

    d1 = ((df.loc[available[-1]] - df.loc[available[-2]]) / df.loc[available[-2]] * 100).dropna()
    w1 = ((df.loc[available[-1]] - df.loc[available[-6]]) / df.loc[available[-6]] * 100).dropna() \
         if len(available) >= 6 else pd.Series(dtype=float)

    rows = []
    for ticker in tickers:
        if ticker in d1.index:
            rows.append({
                "ticker": ticker,
                "d1": round(float(d1[ticker]), 2),
                "w1": round(float(w1[ticker]), 2) if ticker in w1.index else 0.0,
            })
    return sorted(rows, key=lambda x: x["d1"], reverse=True), actual_date


_name_cache: dict[str, str] = {}

def _names_from_yfinance(tickers: list[str]) -> dict[str, str]:
    missing = [t for t in tickers if t not in _name_cache]
    if missing:
        def get_name(ticker: str) -> tuple[str, str]:
            try:
                return ticker, yf.Ticker(ticker).info.get('shortName') or ticker
            except Exception:
                return ticker, ticker
        with ThreadPoolExecutor(max_workers=10) as executor:
            for ticker, name in executor.map(get_name, missing):
                _name_cache[ticker] = name
    return {t: _name_cache.get(t, t) for t in tickers}


def _portfolio_from_api() -> tuple[list[str], dict[str, str]]:
    res = http_req.get(f"{API_BASE}/bobp/last-portfolio-returns?exclude=BIL", timeout=15)
    res.raise_for_status()
    tickers = [it["ticker"] for it in res.json()["items"]]
    return tickers, _names_from_yfinance(tickers)


def _portfolio_from_excel() -> tuple[list[str], dict[str, str]]:
    files = glob.glob(os.path.join(XLSX_DIR, "*.xlsx"))
    if not files:
        return [], {}
    df   = pd.read_excel(files[0], header=None)
    data = df.iloc[14:].dropna(subset=[1])
    tickers = [str(row[1]).strip() for _, row in data.iterrows()]
    names   = {str(row[1]).strip(): str(row[2]).strip() for _, row in data.iterrows()}
    return tickers, names


def load_portfolio() -> tuple[list[str], dict[str, str]]:
    if os.environ.get("NAME_SOURCE", "api") == "excel":
        return _portfolio_from_excel()
    return _portfolio_from_api()


def pick_highlight(rows: list[dict]) -> str | None:
    top8 = [r for r in rows if r["d1"] >= 8.0]
    if top8:
        return max(top8, key=lambda r: r["d1"])["ticker"]
    candidates = [r for r in rows if r["w1"] >= 20.0 and r["d1"] > 0]
    if candidates:
        return max(candidates, key=lambda r: r["d1"])["ticker"]
    return None


# ── routes ────────────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
def portfolio(date: Optional[str] = Query(None)):
    latest_date = resolve_trading_date()
    if date:
        try:
            trading_date = date_type.fromisoformat(date)
            if trading_date > latest_date:
                trading_date = latest_date
        except ValueError:
            trading_date = latest_date
    else:
        trading_date = latest_date
    tickers, names    = load_portfolio()
    rows, actual_date = fetch_returns(trading_date, tickers)
    highlight         = pick_highlight(rows)
    return {
        "trading_date": str(actual_date),
        "latest_date":  str(latest_date),
        "rows":         rows,
        "names":        names,
        "highlight":    highlight,
    }


@app.get("/api/env")
def get_env():
    load_dotenv(ENV_PATH, override=True)
    key    = os.environ.get("GEMINI_API_KEY", "")
    masked = (key[:6] + "••••" + key[-4:]) if len(key) > 10 else ("••••••••" if key else "")
    return {
        "GEMINI_API_KEY_MASKED": masked,
        "has_key": bool(key),
        "NAME_SOURCE": os.environ.get("NAME_SOURCE", "api"),
    }


@app.post("/api/env")
def update_env(body: dict[str, Any]):
    for k, v in body.items():
        set_key(ENV_PATH, k, str(v))
        os.environ[k] = str(v)
    return {"ok": True}


class PipelineBody(BaseModel):
    date:   Optional[str] = None
    ticker: Optional[str] = None


@app.get("/api/pipeline/result")
def pipeline_result(file: str = Query(...)):
    if os.sep in file or "/" in file or ".." in file:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(BASE_DIR, file)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.get("/api/pipeline/result/by-date")
def pipeline_result_by_date(date: str = Query(...)):
    files = glob.glob(os.path.join(BASE_DIR, f"*_{date}_news.json"))
    if not files:
        raise HTTPException(status_code=404, detail="Not found")
    with open(sorted(files)[-1], encoding="utf-8") as f:
        return json.load(f)


@app.post("/api/pipeline/run")
def run_pipeline(body: PipelineBody):
    args = [sys.executable, "-u", os.path.join(BASE_DIR, "pipeline", "pipeline.py")]
    if body.date:
        args.append(body.date)
    if body.ticker:
        args.append(body.ticker)

    def stream():
        proc = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            cwd=BASE_DIR,
        )
        for line in proc.stdout:
            yield f"data: {line.rstrip()}\n\n"
        proc.wait()
        yield f"data: [EXIT:{proc.returncode}]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


if __name__ == "__main__":
    import uvicorn
    print("Feed Creator API server running at http://localhost:5000")
    uvicorn.run(app, host="0.0.0.0", port=5000)
