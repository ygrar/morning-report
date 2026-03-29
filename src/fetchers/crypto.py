"""暗号資産データ取得モジュール（CoinGecko無料API）"""
import requests


COINGECKO_BASE = "https://api.coingecko.com/api/v3"
FEAR_GREED_URL = "https://api.alternative.me/fng/"


def fetch_prices(watchlist: list[dict]) -> list[dict]:
    ids = ",".join(item["id"] for item in watchlist)
    try:
        resp = requests.get(
            f"{COINGECKO_BASE}/simple/price",
            params={
                "ids": ids,
                "vs_currencies": "usd",
                "include_24hr_change": "true",
                "include_market_cap": "true",
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception:
        return [{"name": item["symbol"], "id": item["id"],
                 "price": None, "pct_24h": None, "market_cap": None}
                for item in watchlist]

    results = []
    for item in watchlist:
        d = data.get(item["id"], {})
        results.append({
            "name": item["symbol"],
            "id": item["id"],
            "price": d.get("usd"),
            "pct_24h": round(d.get("usd_24h_change", 0), 2) if d.get("usd_24h_change") is not None else None,
            "market_cap": d.get("usd_market_cap"),
        })
    return results


def fetch_fear_greed() -> dict:
    try:
        resp = requests.get(FEAR_GREED_URL, params={"limit": 1}, timeout=10)
        resp.raise_for_status()
        d = resp.json()["data"][0]
        return {
            "value": int(d["value"]),
            "label": d["value_classification"],
        }
    except Exception:
        return {"value": None, "label": "取得失敗"}
