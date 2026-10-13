"""Toob Eleringist Eesti börsihinnad (täna + homme) ja kirjutab data/elekter.json.

Hinnad on s/kWh ilma käibemaksuta, keskmistatud tunni kaupa (Elering annab 15-min sammuga).
"""
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Tallinn")
OUT = os.path.join(os.path.dirname(__file__), "..", "data", "elekter.json")


def fetch_day(day):
    start = datetime(day.year, day.month, day.day, tzinfo=TZ)
    end = start + timedelta(days=1) - timedelta(seconds=1)
    fmt = "%Y-%m-%dT%H:%M:%S.000Z"
    url = (
        "https://dashboard.elering.ee/api/nps/price"
        f"?start={start.astimezone(timezone.utc).strftime(fmt)}"
        f"&end={end.astimezone(timezone.utc).strftime(fmt)}"
    )
    with urllib.request.urlopen(url, timeout=30) as r:
        rows = json.load(r).get("data", {}).get("ee", [])

    sums, counts = [0.0] * 24, [0] * 24
    for row in rows:
        hour = datetime.fromtimestamp(row["timestamp"], TZ).hour
        sums[hour] += row["price"]
        counts[hour] += 1
    if not any(counts):
        return []
    # €/MWh -> s/kWh: jaga 10-ga
    return [round(sums[h] / counts[h] / 10, 2) if counts[h] else None for h in range(24)]


def main():
    today = datetime.now(TZ).date()
    tomorrow = today + timedelta(days=1)
    data = {
        "date": today.isoformat(),
        "today": fetch_day(today),
        "next_date": tomorrow.isoformat(),
        "tomorrow": fetch_day(tomorrow),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Täna {len(data['today'])} tundi, homme {len(data['tomorrow'])} tundi")


if __name__ == "__main__":
    main()
