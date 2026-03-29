"""朝の投資ブリーフィング生成エントリポイント"""
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
import pytz
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from fetchers import us_stocks, jp_stocks, crypto, events
from ai import commentator
from generators.markdown import build_report


def load_config() -> dict:
    config_path = Path(__file__).parent.parent / "config" / "watchlist.yml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    print("📊 朝の投資ブリーフィング生成開始...")
    cfg = load_config()

    # ── データ取得 ──────────────────────────────────
    print("  [1/5] 米国株データ取得中...")
    us_indices = us_stocks.fetch_indices(cfg["us_stocks"]["indices"])
    us_sectors = us_stocks.fetch_sectors(cfg["us_stocks"]["sector_etfs"])
    us_notable = us_stocks.fetch_notable_stocks(
        cfg["us_stocks"]["top20_market_cap"],
        cfg["us_stocks"]["screening_threshold"],
    )
    futures_data = us_stocks.fetch_futures(cfg["futures"])
    commodities_data = us_stocks.fetch_commodities(cfg["commodities"])

    print("  [2/5] 日本株データ取得中...")
    jp_indices = jp_stocks.fetch_indices(cfg["jp_stocks"]["indices"])
    jp_fx = jp_stocks.fetch_fx(cfg["jp_stocks"]["fx"])
    jp_notable = jp_stocks.fetch_notable_stocks(
        cfg["jp_stocks"]["top20_market_cap"],
        cfg["jp_stocks"]["screening_threshold"],
    )

    print("  [3/5] 暗号資産データ取得中...")
    crypto_prices = crypto.fetch_prices(cfg["crypto"]["watchlist"])
    fear_greed = crypto.fetch_fear_greed()

    print("  [4/5] 経済指標カレンダー取得中...")
    today_events = events.fetch_today_events()

    # VIXを指数リストから抽出
    vix = next((i for i in us_indices if i["ticker"] == "^VIX"), {})

    # BTC/ETH を個別に取り出す
    btc = next((c for c in crypto_prices if c["id"] == "bitcoin"), {})
    eth = next((c for c in crypto_prices if c["id"] == "ethereum"), {})

    # ── AI考察生成 ──────────────────────────────────
    print("  [5/5] AI考察生成中...")
    summary = commentator.generate_summary(us_indices, jp_indices, crypto_prices, jp_fx)
    us_commentary = commentator.generate_us_commentary(us_notable, vix, us_indices)
    jp_commentary = commentator.generate_jp_commentary(jp_notable, jp_fx, jp_indices)
    crypto_commentary = commentator.generate_crypto_commentary(btc, eth, fear_greed, commodities_data)
    outlook = commentator.generate_outlook(futures_data, us_indices, jp_indices,
                                           today_events, fear_greed)

    # ── Markdown生成 ────────────────────────────────
    report_data = {
        "us": {
            "indices": us_indices,
            "sectors": us_sectors,
        },
        "jp": {
            "indices": jp_indices,
            "fx": jp_fx,
        },
        "crypto": {
            "prices": crypto_prices,
            "fear_greed": fear_greed,
            "commodities": commodities_data,
        },
        "futures": futures_data,
        "events": today_events,
        "summary": summary,
        "us_commentary": us_commentary,
        "jp_commentary": jp_commentary,
        "crypto_commentary": crypto_commentary,
        "outlook": outlook,
    }

    markdown = build_report(report_data)

    # ── ファイル出力 ─────────────────────────────────
    jst = pytz.timezone("Asia/Tokyo")
    today_str = datetime.now(jst).strftime("%Y-%m-%d")
    output_dir = Path(__file__).parent.parent / "reports"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / f"{today_str}.md"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(markdown)

    print(f"\n✅ レポート生成完了: {output_path}")
    print("─" * 50)
    print(markdown[:500] + "...\n")  # プレビュー


if __name__ == "__main__":
    # ANTHROPIC_API_KEY の存在確認
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ エラー: ANTHROPIC_API_KEY が設定されていません")
        sys.exit(1)
    main()
