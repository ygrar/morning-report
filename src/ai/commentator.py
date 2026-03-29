"""Claude APIを使った相場考察・サマリー生成モジュール"""
import os
import anthropic

MODEL = "claude-haiku-4-5-20251001"
_FORMAT_RULE = "出力はプレーンな日本語文章のみ。Markdownの見出し（#）・箇条書き（-/*）・太字（**）は一切使わないこと。"


def _get_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _call(prompt: str, max_tokens: int = 300) -> str:
    try:
        msg = _get_client().messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text.strip()
    except Exception as e:
        return f"（AI考察取得失敗: {e}）"


def generate_summary(us_indices: list, jp_indices: list, crypto: list, fx: list) -> str:
    """冒頭の相場サマリー（結論ファースト・3〜5行）"""
    def fmt_idx(items):
        return ", ".join(
            f"{i['name']} {'+' if (i['pct'] or 0) >= 0 else ''}{i['pct']}%"
            for i in items if i.get("pct") is not None
        )

    prompt = f"""あなたは個人投資家向けの金融アナリストです。以下の前日市場データを基に、
相場の空気感が結論からわかるサマリーを3〜5行の日本語で書いてください。
「リスクオン/リスクオフ」「センチメント」などのキーワードも適宜使用してください。
{_FORMAT_RULE}

【米国株指数】{fmt_idx(us_indices)}
【日本株指数】{fmt_idx(jp_indices)}
【為替】{fmt_idx(fx)}
【暗号資産】{', '.join(f"{c['name']} {'+' if (c['pct_24h'] or 0) >= 0 else ''}{c['pct_24h']}%" for c in crypto if c.get('pct_24h') is not None)}

流れるような文章で書いてください。"""
    return _call(prompt, max_tokens=400)


def generate_us_commentary(notable: dict, vix: dict, indices: list) -> str:
    """
    米国株考察（150〜200字）。
    時価総額上位20銘柄のパフォーマンス＋S&P500スクリーニング結果を渡し、
    AIが注目すべき銘柄を厳選して言及する。
    """
    vix_val = vix.get("price", "不明")
    idx_str = ", ".join(
        f"{i['name']} {_fmt_change(i)}" for i in indices if i.get("pct") is not None
    )

    # 上位20銘柄（騰落率の絶対値が大きい順）
    top20 = sorted(
        [s for s in notable.get("top20", []) if s.get("pct") is not None],
        key=lambda x: abs(x["pct"]), reverse=True
    )[:10]
    top20_str = ", ".join(
        f"{s['name']}({s['ticker']}) {'+' if s['pct'] >= 0 else ''}{s['pct']}%"
        for s in top20
    )

    # S&P500スクリーニング
    screened = notable.get("screened", [])
    screened_up = [s for s in screened if s["pct"] > 0][:3]
    screened_dn = [s for s in screened if s["pct"] < 0][:3]
    screened_str = ""
    if screened_up:
        screened_str += "急騰: " + ", ".join(f"{s['ticker']} +{s['pct']}%" for s in screened_up)
    if screened_dn:
        screened_str += " / 急落: " + ", ".join(f"{s['ticker']} {s['pct']}%" for s in screened_dn)
    if not screened_str:
        screened_str = "±3%超の銘柄なし"

    prompt = f"""米国株市場の前日の動きについて、個人投資家向けに考察を190〜210字の日本語で書いてください。
{_FORMAT_RULE}

【指数】{idx_str}
【VIX】{vix_val}
【時価総額上位20銘柄（騰落率上位）】{top20_str if top20_str else 'データなし'}
【S&P500 ±3%超スクリーニング】{screened_str}

以下を3〜4文でまとめてください：
・VIX水準を踏まえたセンチメントの評価
・動きが目立った銘柄2社への具体的な言及（騰落の背景も1文で）
・セクターローテーションの兆しがあれば触れる"""
    return _call(prompt, max_tokens=500)


def generate_jp_commentary(notable: dict, fx: list, indices: list) -> str:
    """
    日本株考察（150〜200字）。
    時価総額上位20銘柄のパフォーマンス＋日経225スクリーニング結果を渡し、
    AIが注目すべき銘柄を厳選して言及する。
    """
    fx_str = ", ".join(f"{f['name']} {f['price']}" for f in fx if f.get("price"))
    idx_str = ", ".join(
        f"{i['name']} {_fmt_change(i)}" for i in indices if i.get("pct") is not None
    )

    # 上位20銘柄の動き（騰落率の大きい順にソート）
    top20 = sorted(
        [s for s in notable.get("top20", []) if s.get("pct") is not None],
        key=lambda x: abs(x["pct"]), reverse=True
    )[:10]
    top20_str = ", ".join(f"{s['name']}({s['ticker']}) {'+' if s['pct'] >= 0 else ''}{s['pct']}%" for s in top20)

    # 日経225スクリーニング結果
    screened = notable.get("screened", [])
    screened_up = [s for s in screened if s["pct"] > 0][:3]
    screened_dn = [s for s in screened if s["pct"] < 0][:3]
    screened_str = ""
    if screened_up:
        screened_str += "急騰: " + ", ".join(f"{s['ticker']} +{s['pct']}%" for s in screened_up)
    if screened_dn:
        screened_str += " / 急落: " + ", ".join(f"{s['ticker']} {s['pct']}%" for s in screened_dn)
    if not screened_str:
        screened_str = "±3%超の銘柄なし"

    prompt = f"""日本株市場の前日の動きについて、個人投資家向けに考察を190〜210字の日本語で書いてください。
{_FORMAT_RULE}

【指数】{idx_str}
【為替】{fx_str}
【時価総額上位20銘柄（騰落率上位）】{top20_str if top20_str else 'データなし'}
【日経225 ±3%超スクリーニング】{screened_str}

以下を3〜4文でまとめてください：
・為替水準と株価への影響
・動きが目立った銘柄2社への具体的な言及（騰落の背景も1文で）
・市場全体のセンチメント判断"""
    return _call(prompt, max_tokens=500)


def _fmt_change(item: dict) -> str:
    pct = item.get("pct")
    if pct is None:
        return "―"
    return f"{'+' if pct >= 0 else ''}{pct}%"


def generate_crypto_commentary(btc: dict, eth: dict, fear_greed: dict, commodities: list = None) -> str:
    """暗号資産・コモディティの一言考察（70〜90字程度）"""
    comm_str = ""
    if commodities:
        comm_str = "\n".join(
            f"{c['name']}: {c.get('price', '不明')} ({'+' if (c.get('pct') or 0) >= 0 else ''}{c.get('pct', '不明')}%)"
            for c in commodities if c.get("price")
        )

    prompt = f"""暗号資産・コモディティ市場について、80〜100字の日本語で一言コメントしてください。
{_FORMAT_RULE}

BTC: {btc.get('price', '不明')}ドル ({'+' if (btc.get('pct_24h') or 0) >= 0 else ''}{btc.get('pct_24h', '不明')}%)
ETH: {eth.get('price', '不明')}ドル ({'+' if (eth.get('pct_24h') or 0) >= 0 else ''}{eth.get('pct_24h', '不明')}%)
Fear & Greed: {fear_greed.get('value', '不明')} ({fear_greed.get('label', '')})
{comm_str}

暗号資産のセンチメントとコモディティの動きを踏まえ、端的に伝えてください。"""
    return _call(prompt, max_tokens=200)


def generate_outlook(futures: list, us_indices: list, jp_indices: list,
                     events: list, fear_greed: dict) -> str:
    """相場見通し（先物・マクロ指標を踏まえた200字程度の総括）"""
    fut_str = "\n".join(
        f"  {f['name']}: {f['price']} ({'+' if (f['pct'] or 0) >= 0 else ''}{f['pct']}%)"
        for f in futures if f.get("price")
    )
    events_str = "\n".join(f"  {e['time']} {e['title']}" for e in events[:5])
    fg = f"{fear_greed.get('value', '不明')} ({fear_greed.get('label', '')})"

    prompt = f"""個人投資家向けに、本日の相場見通しを220〜240字の日本語で書いてください。
{_FORMAT_RULE}

【先物・マクロ指標】
{fut_str if fut_str else '  データなし'}

【本日の主要イベント（予定）】
{events_str if events_str else '  特になし'}

【暗号資産センチメント】Fear & Greed: {fg}

以下を3〜4文でまとめてください：
・先物の方向感と金利・ドル動向からの読み取り
・本日のイベントリスク（なければ「主要指標なし」と明記）
・注目セクターまたは注意すべき点
断定的な表現は避け、参考情報として書いてください。"""
    return _call(prompt, max_tokens=500)
