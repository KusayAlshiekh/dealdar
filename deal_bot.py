#!/usr/bin/env python3

import os
import re
import html
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.request

HTML_FILE = "index.html"
MAX_DEALS = 6

RSS_QUELLEN = [
    "https://www.mydealz.de/rss/hottest",
    "https://www.mydealz.de/rss/hot",
]

STORE_KEYWORDS = {
    "amazon": "Amazon",
    "mediamarkt": "MediaMarkt",
    "saturn": "Saturn",
    "ebay": "eBay",
    "otto": "OTTO",
    "lidl": "Lidl",
    "aldi": "Aldi",
}

MARKEN = [
    "apple","samsung","sony","bose","jbl","lg","lenovo",
    "asus","acer","hp","xiaomi","anker","dyson","nike","adidas"
]

# ───────────── PARSER ─────────────

def parse_temp(titel):
    match = re.search(r'(\d+)\s*°', titel)
    return int(match.group(1)) if match else 0

def parse_preis(titel):
    matches = re.findall(r'(\d+(?:[.,]\d+)?)\s*€', titel)
    if not matches:
        return "?"
    return matches[-1] + "€"

def parse_rabatt(titel):
    match = re.search(r'(\d{1,2})\s*%', titel)
    return match.group(1) if match else ""

def get_store(titel, link):
    text = (titel + link).lower()
    for k, v in STORE_KEYWORDS.items():
        if k in text:
            return v
    return "Online"

def clean_title(t):
    return re.sub(r'\s+', ' ', html.unescape(t)).strip()

def extract_image(desc):
    if not desc:
        return ""
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', desc)
    return m.group(1) if m else ""

# ───────────── FILTER ─────────────

def is_good(deal):
    t = deal["titel"].lower()

    if deal["temp"] < 100:
        return False

    if deal["preis"] == "?":
        return False

    if any(x in t for x in ["abo","vertrag","casino","gewinnspiel"]):
        return False

    if not any(m in t for m in MARKEN) and deal["temp"] < 200:
        return False

    return True

# ───────────── FETCH ─────────────

def fetch_deals():
    deals = []

    for url in RSS_QUELLEN:
        print("Lade:", url)

        try:
            req = urllib.request.Request(url, headers={"User-Agent": "DealDarBot"})
            data = urllib.request.urlopen(req).read().decode()

            root = ET.fromstring(data)
            items = root.find("channel").findall("item")

            for item in items[:30]:
                title = clean_title(item.findtext("title",""))
                link = item.findtext("link","")
                desc = item.findtext("description","")

                deal = {
                    "titel": title,
                    "link": link,
                    "preis": parse_preis(title),
                    "rabatt": parse_rabatt(title),
                    "temp": parse_temp(title),
                    "store": get_store(title, link),
                    "bild": extract_image(desc)
                }

                if is_good(deal):
                    deals.append(deal)

        except Exception as e:
            print("Fehler:", e)

    # Duplikate entfernen
    unique = []
    seen = set()

    for d in deals:
        key = d["titel"]
        if key not in seen:
            seen.add(key)
            unique.append(d)

    # nach Temperatur sortieren
    unique.sort(key=lambda x: x["temp"], reverse=True)

    return unique[:MAX_DEALS]

# ───────────── HTML ─────────────

def build_card(d):
    img = f'<img src="{d["bild"]}">' if d["bild"] else "🏷️"

    rabatt = f'<span class="deal-discount">-{d["rabatt"]}%</span>' if d["rabatt"] else ""

    return f"""
<a href="{d["link"]}" target="_blank" class="deal-card-link">
<div class="deal-card">
<div class="badge-hot">🔥 {d["temp"]}°</div>

<div class="deal-img">{img}</div>

<div class="deal-body">
<div class="deal-store">{d["store"]}</div>
<div class="deal-title">{d["titel"]}</div>

<div class="deal-prices">
<span class="deal-price-new">{d["preis"]}</span>
{rabatt}
</div>

<div class="deal-cta">Zum Deal →</div>
</div>
</div>
</a>
"""

def update_html(deals):
    if not os.path.exists(HTML_FILE):
        print("index.html fehlt")
        return

    html_text = open(HTML_FILE).read()

    cards = "\n".join([build_card(d) for d in deals])

    new_html = re.sub(
        r'(<div class="deal-grid">)(.*?)(</div>)',
        f'\\1\n{cards}\n\\3',
        html_text,
        flags=re.DOTALL
    )

    open(HTML_FILE, "w").write(new_html)

    print("Website aktualisiert")

# ───────────── MAIN ─────────────

def main():
    print("DealDar Bot V4 läuft...")
    deals = fetch_deals()

    if not deals:
        print("Keine Deals gefunden")
        return

    update_html(deals)

if __name__ == "__main__":
    main()
