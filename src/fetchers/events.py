"""経済指標・イベントカレンダー取得モジュール（Forex Factory XML）"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz

FF_CALENDAR_URL = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
HIGH_IMPACT = {"High", "Medium"}


def fetch_today_events() -> list[dict]:
    jst = pytz.timezone("Asia/Tokyo")
    today_jst = datetime.now(jst).strftime("%m-%d-%Y")

    try:
        resp = requests.get(
            FF_CALENDAR_URL,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
    except Exception:
        return [{"time": "--:--", "country": "", "impact": "",
                 "title": "イベントデータを取得できませんでした", "forecast": "", "previous": ""}]

    events = []
    for item in root.findall(".//event"):
        date = item.findtext("date", "").strip()
        if date != today_jst:
            continue

        impact = item.findtext("impact", "").strip()
        if impact not in HIGH_IMPACT:
            continue

        raw_time = item.findtext("time", "").strip()
        time_str = _convert_time(raw_time, jst)

        events.append({
            "time": time_str,
            "country": item.findtext("country", "").strip(),
            "impact": impact,
            "title": item.findtext("title", "").strip(),
            "forecast": item.findtext("forecast", "").strip(),
            "previous": item.findtext("previous", "").strip(),
        })

    events.sort(key=lambda x: x["time"])
    return events if events else [{"time": "--:--", "country": "", "impact": "",
                                   "title": "本日の主要イベントはありません", "forecast": "", "previous": ""}]


def _convert_time(raw: str, tz) -> str:
    """'2:30pm' 形式 → JST 'HH:MM' に変換"""
    if not raw or raw.lower() in ("all day", "tentative", ""):
        return "終日"
    try:
        # Forex Factory時刻はニューヨーク時間（ET）
        et = pytz.timezone("America/New_York")
        now = datetime.now(tz)
        dt = datetime.strptime(raw, "%I:%M%p").replace(
            year=now.year, month=now.month, day=now.day, tzinfo=et
        )
        return dt.astimezone(tz).strftime("%H:%M")
    except Exception:
        return raw
