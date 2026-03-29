"""米国株データ取得モジュール"""
import yfinance as yf
import pandas as pd
import requests
from io import StringIO
from typing import Optional


def _pct(current: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return round((current - prev) / prev * 100, 2)


# yfinanceティッカー → stooqティッカーのマッピング
_STOOQ_MAP = {
    # 主要指数
    "^GSPC": "^spx",
    "^IXIC": "^ndq",
    "^DJI":  "^dji",
    "^VIX":  "^vix",
    # セクターETF
    "XLK": "xlk.us", "XLF": "xlf.us", "XLE": "xle.us", "XLV": "xlv.us",
    "XLY": "xly.us", "XLI": "xli.us", "XLP": "xlp.us", "XLU": "xlu.us",
    # 先物・マクロ
    "ES=F":      "es.f",
    "NQ=F":      "nq.f",
    "NIY=F":     "niy.f",
    "^TNX":      "10us.b",
    "DX-Y.NYB":  "^usd",
    # コモディティ
    "CL=F": "cl.f",
    "GC=F": "gc.f",
}


def _to_stooq_ticker(yf_ticker: str) -> str:
    """yfinanceティッカーをstooqティッカーに変換。マッピングにない場合は ticker.us 形式を試みる"""
    if yf_ticker in _STOOQ_MAP:
        return _STOOQ_MAP[yf_ticker]
    # 英数字のみの普通の株式ティッカー → ticker.us
    if yf_ticker.isalpha():
        return f"{yf_ticker.lower()}.us"
    return yf_ticker


def _fetch_stooq(stooq_ticker: str) -> Optional[dict]:
    """stooqから価格データを取得"""
    try:
        url = f"https://stooq.com/q/d/l/?s={stooq_ticker}&i=d"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        df = df.dropna(subset=["Close"]).sort_values("Date")
        if len(df) < 2:
            return None
        latest = float(df.iloc[-1]["Close"])
        prev   = float(df.iloc[-2]["Close"])
        return {
            "price":  round(latest, 2),
            "change": round(latest - prev, 2),
            "pct":    _pct(latest, prev),
        }
    except Exception:
        return None


def _fetch_ticker(yf_ticker: str) -> Optional[dict]:
    """stooqを優先し、失敗時はyfinanceにフォールバック"""
    stooq_ticker = _to_stooq_ticker(yf_ticker)
    data = _fetch_stooq(stooq_ticker)
    if data:
        return data
    # フォールバック: yfinance
    try:
        t = yf.Ticker(yf_ticker)
        hist = t.history(period="5d")
        if hist.empty or len(hist) < 2:
            return None
        latest = hist.iloc[-1]
        prev = hist.iloc[-2]
        price = round(float(latest["Close"]), 2)
        change = round(float(latest["Close"] - prev["Close"]), 2)
        pct = _pct(latest["Close"], prev["Close"])
        return {"price": price, "change": change, "pct": pct}
    except Exception:
        return None


def fetch_indices(indices: list[dict]) -> list[dict]:
    results = []
    for item in indices:
        data = _fetch_ticker(item["ticker"])
        if data:
            results.append({"name": item["name"], "ticker": item["ticker"], **data})
        else:
            results.append({"name": item["name"], "ticker": item["ticker"],
                            "price": None, "change": None, "pct": None})
    return results


def fetch_sectors(sector_etfs: list[dict]) -> list[dict]:
    results = []
    for item in sector_etfs:
        data = _fetch_ticker(item["ticker"])
        if data:
            results.append({"name": item["name"], "ticker": item["ticker"], **data})
        else:
            results.append({"name": item["name"], "ticker": item["ticker"],
                            "price": None, "change": None, "pct": None})
    results.sort(key=lambda x: x["pct"] if x["pct"] is not None else -999, reverse=True)
    return results


def fetch_notable_stocks(top20: list[dict], threshold: float = 3.0) -> dict:
    """
    時価総額上位20銘柄のパフォーマンス＋S&P500スクリーニング(±threshold%)を統合。
    テーブル表示用ではなく、AI考察へのインプット用データ。
    """
    top20_data = []
    for item in top20:
        data = _fetch_ticker(item["ticker"])
        if data:
            top20_data.append({"name": item["name"], "ticker": item["ticker"], **data})

    screened = _screen_sp500(threshold)
    top20_tickers = {d["ticker"] for d in top20_data}
    extra = [s for s in screened if s["ticker"] not in top20_tickers]

    return {
        "top20": top20_data,
        "screened": screened,
        "extra_screened": extra,
    }


def _screen_sp500(threshold: float) -> list[dict]:
    """S&P500構成銘柄から騰落率±threshold%以上を抽出"""
    try:
        sp500 = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
        tickers = sp500["Symbol"].str.replace(".", "-").tolist()
    except Exception:
        return []

    results = []
    batch = " ".join(tickers[:100])
    try:
        data = yf.download(batch, period="5d", progress=False, auto_adjust=True)
        closes = data["Close"]
        for ticker in closes.columns:
            col = closes[ticker].dropna()
            if len(col) < 2:
                continue
            pct = _pct(col.iloc[-1], col.iloc[-2])
            if abs(pct) >= threshold:
                results.append({"ticker": ticker, "pct": pct,
                                "price": round(float(col.iloc[-1]), 2)})
    except Exception:
        return []

    results.sort(key=lambda x: x["pct"], reverse=True)
    return results


def fetch_commodities(commodities: list[dict]) -> list[dict]:
    results = []
    for item in commodities:
        data = _fetch_ticker(item["ticker"])
        if data:
            results.append({"name": item["name"], "ticker": item["ticker"], **data})
        else:
            results.append({"name": item["name"], "ticker": item["ticker"],
                            "price": None, "change": None, "pct": None})
    return results


def fetch_futures(futures: list[dict]) -> list[dict]:
    results = []
    for item in futures:
        data = _fetch_ticker(item["ticker"])
        if data:
            results.append({"name": item["name"], "ticker": item["ticker"], **data})
        else:
            results.append({"name": item["name"], "ticker": item["ticker"],
                            "price": None, "change": None, "pct": None})
    return results
