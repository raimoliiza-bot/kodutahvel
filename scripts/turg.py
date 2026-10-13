"""Toob turuandmed (Yahoo Finance + CNN Fear & Greed), arvutab häirekella ja kirjutab data/turg.json."""
import json
import os
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

OUT = os.path.join(os.path.dirname(__file__), "..", "data", "turg.json")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"}

# Häirekella tasemed (muuda siin)
BUY_LEVELS = [(-0.30, "osta ülejäänud puhver"), (-0.20, "osta 2. kolmandik"), (-0.10, "osta 1. kolmandik")]
VIX_PANIC = 40
VIX_WARN = 25
FG_CONFIRM = 15
FG_GREED = 85

RATINGS = {"extreme fear": "Äärmine hirm", "fear": "Hirm", "neutral": "Neutraalne",
           "greed": "Ahnus", "extreme greed": "Äärmine ahnus"}


def get(url):
    headers = dict(UA)
    if "cnn.io" in url:  # CNN laseb läbi ainult "brauseri" päistega
        headers.update({"Referer": "https://edition.cnn.com/", "Origin": "https://edition.cnn.com",
                        "Accept": "application/json, text/plain, */*", "Accept-Language": "en-US,en;q=0.9"})
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def closes(symbol):
    d = get(f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.request.quote(symbol)}?range=1y&interval=1d")
    res = d["chart"]["result"][0]
    c = [x for x in res["indicators"]["quote"][0]["close"] if x is not None]
    last = res["meta"].get("regularMarketPrice") or c[-1]
    return c, last


def num(v, dec=0):
    s = f"{v:,.{dec}f}".replace(",", " ").replace(".", ",")
    return s


def row(name, symbol, dec, suffix=""):
    c, last = closes(symbol)
    # c[-1] on tänane (jooksev või viimane) päev, c[-2] eelmise päeva sulgemine
    prev = c[-2] if len(c) > 1 else last
    return {"name": name, "value": num(last, dec) + suffix, "change": round((last / prev - 1) * 100, 2)}, c, last


def main():
    out = {"updated": datetime.now(ZoneInfo("Europe/Tallinn")).strftime("%d.%m %H:%M"), "rows": []}

    sp_row, sp_c, sp_last = row("S&P 500", "^GSPC", 0)
    gold_row, _, _ = row("Kuld", "GC=F", 0, " $")
    vix_row, _, vix = row("VIX", "^VIX", 1)
    tnx_row, _, _ = row("US10Y", "^TNX", 2, "%")
    out["rows"] = [sp_row, gold_row, vix_row, tnx_row]

    fg = None
    try:
        f = get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata")["fear_and_greed"]
        fg = round(f["score"])
        out["fg"] = {"score": fg, "rating": RATINGS.get(f["rating"], f["rating"])}
    except Exception as e:  # CNN blokeerib vahel robotid
        print("Fear & Greed ei õnnestunud:", e)

    peak = max(sp_c + [sp_last])
    dd = sp_last / peak - 1
    ma200 = sum(sp_c[-200:]) / min(200, len(sp_c))
    out["drawdown"] = round(dd * 100, 1)

    level, text = "ok", f"vaikne · S&P tipust {num(dd * 100, 1)}%"
    for lim, action in BUY_LEVELS:
        if dd <= lim:
            level, text = "buy", f"S&P {num(dd * 100, 1)}% tipust → {action}"
            break
    if vix > VIX_PANIC:
        level, text = "buy", f"VIX {num(vix, 1)} > {VIX_PANIC} → osta ülejäänud puhver"
    if level == "buy" and fg is not None and fg < FG_CONFIRM:
        text += " (F&G kinnitab)"
    if level == "ok":
        if vix > VIX_WARN and sp_last < ma200:
            level, text = "warn", "VIX > 25 ja S&P alla 200p keskmise"
        elif fg is not None and fg > FG_GREED:
            level, text = "warn", f"ahnus {fg} → uusi riskiostu ei tee"
    out["alarm"] = {"level": level, "text": text}

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False)
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
