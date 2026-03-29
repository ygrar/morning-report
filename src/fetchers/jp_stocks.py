"""日本株・為替データ取得モジュール"""
import yfinance as yf
import pandas as pd
import requests
import pytz
from typing import Optional

JST = pytz.timezone("Asia/Tokyo")


def _pct(current: float, prev: float) -> float:
    if prev == 0:
        return 0.0
    return round((current - prev) / prev * 100, 2)


def _fetch_ticker(ticker: str) -> Optional[dict]:
    try:
        t = yf.Ticker(ticker)
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


def _fetch_fx_ny_close(ticker: str) -> Optional[dict]:
    """
    1時間足で取得し、NYクローズ相当（6:00 JST = 5pm ET/EDT）の値を返す。
    レポート生成タイミング（朝6時JST）に合わせた為替終値。
    6:00 JSTのローソク足 = 5:00-6:00 JSTの足のClose値を使用。
    前日比は同時刻の前営業日値との比較。
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period="10d", interval="1h")
        if hist.empty:
            return None
        hist.index = hist.index.tz_convert(JST)
        # 5:00 JST のローソク足Close = 6:00 JST時点の値（NYクローズ相当）
        closes = hist[hist.index.hour == 5]["Close"].dropna()
        if len(closes) < 2:
            return None
        latest = float(closes.iloc[-1])
        prev = float(closes.iloc[-2])
        price = round(latest, 2)
        change = round(latest - prev, 2)
        pct = _pct(latest, prev)
        return {"price": price, "change": change, "pct": pct}
    except Exception:
        return None


def _fetch_topix_stooq() -> Optional[dict]:
    """stooq から TOPIX 実値を取得"""
    try:
        url = "https://stooq.com/q/d/l/?s=^tpx&i=d"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(resp.text))
        df = df.dropna(subset=["Close"]).sort_values("Date")
        if len(df) < 2:
            return None
        latest = float(df.iloc[-1]["Close"])
        prev = float(df.iloc[-2]["Close"])
        return {
            "price": round(latest, 2),
            "change": round(latest - prev, 2),
            "pct": _pct(latest, prev),
        }
    except Exception:
        return None


def fetch_indices(indices: list[dict]) -> list[dict]:
    results = []
    for item in indices:
        if item["ticker"] == "^TOPX":
            data = _fetch_topix_stooq()
        else:
            data = _fetch_ticker(item["ticker"])
        if data:
            results.append({"name": item["name"], "ticker": item["ticker"], **data})
        else:
            results.append({"name": item["name"], "ticker": item["ticker"],
                            "price": None, "change": None, "pct": None})
    return results


def fetch_fx(fx: list[dict]) -> list[dict]:
    results = []
    for item in fx:
        data = _fetch_fx_ny_close(item["ticker"])
        if data:
            results.append({"name": item["name"], "ticker": item["ticker"], **data})
        else:
            results.append({"name": item["name"], "ticker": item["ticker"],
                            "price": None, "change": None, "pct": None})
    return results


def fetch_notable_stocks(top20: list[dict], threshold: float = 3.0) -> dict:
    """
    時価総額上位20銘柄のパフォーマンス＋日経225スクリーニング(±threshold%)を統合して返す。
    テーブル表示用ではなく、AI考察へのインプット用データ。
    """
    # ── 上位20銘柄のパフォーマンス取得 ──
    top20_data = []
    for item in top20:
        data = _fetch_ticker(item["ticker"])
        if data:
            top20_data.append({
                "name": item["name"],
                "ticker": item["ticker"],
                **data,
            })

    # ── 日経225スクリーニング（±3%超） ──
    screened = _screen_nikkei225(threshold)

    # スクリーニング結果から上位20に含まれないものだけを追加
    top20_tickers = {d["ticker"] for d in top20_data}
    extra = [s for s in screened if s["ticker"] not in top20_tickers]

    return {
        "top20": top20_data,
        "screened": screened,          # 日経225 ±3%超（上位20含む）
        "extra_screened": extra,       # 上位20外のスクリーニング銘柄
    }


def _screen_nikkei225(threshold: float) -> list[dict]:
    """日経225構成銘柄から騰落率±threshold%以上を抽出"""
    try:
        nikkei = pd.read_html(
            "https://indexes.nikkei.co.jp/nkave/index/component?idx=nk225"
        )[0]
        code_col = nikkei.columns[0]
        tickers = [
            f"{str(c).zfill(4)}.T"
            for c in nikkei[code_col].dropna().astype(int).tolist()
        ]
    except Exception:
        return []

    results = []
    batch = " ".join(tickers[:80])
    try:
        data = yf.download(batch, period="5d", progress=False, auto_adjust=True)
        closes = data["Close"]
        for ticker in closes.columns:
            col = closes[ticker].dropna()
            if len(col) < 2:
                continue
            pct = _pct(col.iloc[-1], col.iloc[-2])
            if abs(pct) >= threshold:
                results.append({
                    "ticker": ticker,
                    "pct": pct,
                    "price": round(float(col.iloc[-1]), 2),
                })
    except Exception:
        return []

    results.sort(key=lambda x: x["pct"], reverse=True)
    return results
