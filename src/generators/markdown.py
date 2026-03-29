"""Markdownレポート生成モジュール"""
from datetime import datetime
import pytz


def _arrow(pct: float | None) -> str:
    if pct is None:
        return "―"
    return "▲" if pct >= 0 else "▼"


def _fmt_pct(pct: float | None) -> str:
    if pct is None:
        return "―"
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct}%"


def _fmt_price(price: float | None, decimals: int = 2) -> str:
    if price is None:
        return "―"
    return f"{price:,.{decimals}f}"


def _index_table(items: list[dict], currency: str = "$") -> str:
    rows = ["| 指数 | 終値 | 前日比 | 騰落率 |",
            "|------|-----:|-------:|-------:|"]
    for i in items:
        arrow = _arrow(i.get("pct"))
        price = _fmt_price(i.get("price"))
        change = _fmt_price(i.get("change"))
        pct = _fmt_pct(i.get("pct"))
        rows.append(f"| {i['name']} | {currency}{price} | {arrow}{change} | {pct} |")
    return "\n".join(rows)


def _stock_table(items: list[dict], currency: str = "$") -> str:
    rows = ["| 銘柄 | 終値 | 前日比 | 騰落率 |",
            "|------|-----:|-------:|-------:|"]
    for i in items:
        arrow = _arrow(i.get("pct"))
        price = _fmt_price(i.get("price"))
        change = _fmt_price(i.get("change"))
        pct = _fmt_pct(i.get("pct"))
        rows.append(f"| {i['name']}（{i['ticker']}） | {currency}{price} | {arrow}{change} | {pct} |")
    return "\n".join(rows)


def _screening_section(screening: dict) -> str:
    lines = []
    tops = screening.get("top", [])
    bots = screening.get("bottom", [])

    if not tops and not bots:
        return "前日比±3%超の銘柄はありませんでした。\n"

    if tops:
        lines.append("**急騰 TOP3**")
        for s in tops:
            lines.append(f"- {s['ticker']}　**+{s['pct']}%**　（${_fmt_price(s.get('price'))}）")
    if bots:
        lines.append("\n**急落 TOP3**")
        for s in bots:
            lines.append(f"- {s['ticker']}　**{s['pct']}%**　（${_fmt_price(s.get('price'))}）")
    return "\n".join(lines) + "\n"


def _sector_section(sectors: list[dict]) -> str:
    top3 = [s for s in sectors if s.get("pct") is not None][:3]
    bot3 = [s for s in reversed(sectors) if s.get("pct") is not None][:3]

    lines = ["**上昇セクター TOP3**"]
    for s in top3:
        lines.append(f"- {s['name']}（{s['ticker']}）　{_fmt_pct(s.get('pct'))}")
    lines.append("\n**下落セクター TOP3**")
    for s in bot3:
        lines.append(f"- {s['name']}（{s['ticker']}）　{_fmt_pct(s.get('pct'))}")
    return "\n".join(lines) + "\n"


def _futures_table(futures: list[dict]) -> str:
    rows = ["| 指標 | 現在値 | 前日比 | 騰落率 |",
            "|------|-----:|-------:|-------:|"]
    for f in futures:
        arrow = _arrow(f.get("pct"))
        price = _fmt_price(f.get("price"))
        change = _fmt_price(f.get("change"))
        pct = _fmt_pct(f.get("pct"))
        rows.append(f"| {f['name']} | {price} | {arrow}{change} | {pct} |")
    return "\n".join(rows)


def build_report(data: dict) -> str:
    jst = pytz.timezone("Asia/Tokyo")
    today = datetime.now(jst).strftime("%Y/%m/%d")
    report_date = datetime.now(jst).strftime("%Y-%m-%d")

    sections = []

    # ヘッダー
    sections.append(f"# 朝の投資ブリーフィング　{today}\n")
    sections.append("---\n")

    # 相場サマリー
    sections.append("## 📋 相場サマリー\n")
    sections.append(f"{data.get('summary', '（取得失敗）')}\n")
    sections.append("---\n")

    # 米国株
    sections.append("## 🇺🇸 米国株式市場\n")
    sections.append("### 主要指数\n")
    sections.append(_index_table(data["us"]["indices"]) + "\n")

    sections.append("\n### セクター動向\n")
    sections.append(_sector_section(data["us"]["sectors"]))

    sections.append("\n### AI考察\n")
    sections.append(f"> {data.get('us_commentary', '（取得失敗）')}\n")
    sections.append("---\n")

    # 日本株
    sections.append("## 🇯🇵 日本株式市場\n")
    sections.append("### 主要指数\n")
    sections.append(_index_table(data["jp"]["indices"], currency="¥") + "\n")

    sections.append("\n### 為替\n")
    sections.append(_index_table(data["jp"]["fx"], currency="") + "\n")

    sections.append("\n### AI考察\n")
    sections.append(f"> {data.get('jp_commentary', '（取得失敗）')}\n")
    sections.append("---\n")

    # 暗号資産・コモディティ
    sections.append("## 🪙 暗号資産\n")
    crypto_rows = ["| 銘柄 | 価格 | 24h変動 |",
                   "|------|-----:|-------:|"]
    for c in data["crypto"]["prices"]:
        pct = _fmt_pct(c.get("pct_24h"))
        price = _fmt_price(c.get("price"))
        crypto_rows.append(f"| {c['name']} | ${price} | {pct} |")
    sections.append("\n".join(crypto_rows) + "\n")

    fg = data["crypto"]["fear_greed"]
    fg_val = fg.get("value", "―")
    fg_label = fg.get("label", "")
    sections.append(f"\n**Fear & Greed Index**: {fg_val} / 100　（{fg_label}）\n")

    commodities = data["crypto"].get("commodities", [])
    if commodities:
        sections.append("\n## コモディティ\n")
        comm_rows = ["| 銘柄 | 価格 | 前日比 | 騰落率 |",
                     "|------|-----:|-------:|-------:|"]
        for c in commodities:
            arrow = _arrow(c.get("pct"))
            price = _fmt_price(c.get("price"))
            change = _fmt_price(c.get("change"))
            pct = _fmt_pct(c.get("pct"))
            comm_rows.append(f"| {c['name']} | ${price} | {arrow}{change} | {pct} |")
        sections.append("\n" + "\n".join(comm_rows) + "\n")

    sections.append("\n### AI考察\n")
    sections.append(f"> {data.get('crypto_commentary', '（取得失敗）')}\n")
    sections.append("---\n")

    # 相場見通し
    sections.append("## 🔭 相場見通し\n")
    sections.append("### 先物・マクロ指標\n")
    sections.append(_futures_table(data["futures"]) + "\n")
    sections.append("\n### AI総括\n")
    sections.append(f"> {data.get('outlook', '（取得失敗）')}\n")
    sections.append("---\n")

    # 本日のイベント
    sections.append("## 📅 本日の注目イベント\n")
    events = data.get("events", [])
    if events:
        rows = ["| 時刻(JST) | 国 | 指標 | 予想 | 前回 |",
                "|----------|----|------|-----:|-----:|"]
        for e in events:
            forecast = e.get("forecast") or "―"
            previous = e.get("previous") or "―"
            country = e.get("country") or "―"
            rows.append(f"| {e['time']} | {country} | {e['title']} | {forecast} | {previous} |")
        sections.append("\n".join(rows) + "\n")
    else:
        sections.append("本日の主要イベントはありません\n")

    sections.append("\n---\n")
    sections.append(f"*生成日時: {datetime.now(jst).strftime('%Y/%m/%d %H:%M')} JST　／　データ: Yahoo Finance / CoinGecko / Forex Factory*\n\n")
    sections.append(
        "【免責事項】本レポートは情報提供のみを目的としており、投資助言・勧誘ではありません。"
        "投資判断およびそれに伴う損益はすべて読者ご自身の責任において行ってください。\n"
    )

    return "\n".join(sections)
