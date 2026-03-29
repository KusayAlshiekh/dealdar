#!/usr/bin/env python3

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.request

HTML_FILE = "index.html"
MAX_DEALS = 6

RSS_QUELLEN = [
    "https://www.mydealz.de/rss/hot",
    "https://www.mydealz.de/rss/alle",
]

KATEGORIE_EMOJIS = {
    "technik": "💻", "laptop": "💻", "computer": "💻", "pc": "💻",
    "handy": "📱", "smartphone": "📱", "iphone": "📱", "samsung": "📱",
    "kopfhörer": "🎧", "audio": "🎧", "headphones": "🎧",
    "gaming": "🎮", "playstation": "🎮", "xbox": "🎮", "nintendo": "🎮",
    "tv": "📺", "fernseher": "📺",
    "küche": "🍳",
    "haushalt": "🏠", "staubsauger": "🤖",
    "sport": "💪", "fitness": "💪",
    "mode": "👗", "kleidung": "👗", "schuhe": "👟",
    "reisen": "✈️", "hotel": "✈️", "flug": "✈️",
    "buch": "📚", "bücher": "📚",
    "uhr": "⌚", "watch": "⌚",
    "kamera": "📷",
    "auto": "🚗",
    "lebensmittel": "🛒", "essen": "🍔",
}

STORE_KEYWORDS = {
    "amazon": "Amazon",
    "mediamarkt": "MediaMarkt",
    "saturn": "Saturn",
    "ebay": "eBay",
    "lidl": "Lidl",
    "aldi": "Aldi",
    "otto": "OTTO",
}

def get_emoji(titel: str) -> str:
    titel_lower = titel.lower()
    for keyword, emoji in KATEGORIE_EMOJIS.items():
        if keyword in titel_lower:
            return emoji
    return "🏷️"

def get_store(titel: str, link: str) -> str:
    text = f"{titel} {link}".lower()
    for keyword, store in STORE_KEYWORDS.items():
        if keyword in text:
            return store
    return "Online"

def get_badge(titel: str) -> str:
    titel_lower = titel.lower()
    if "%" in titel_lower or "gutschein" in titel_lower:
        return "hot"
    return ""

def parse_preis(titel: str) -> str:
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*€', titel)
    if match:
        return match.group(0)
    return "Preis unbekannt"

def hole_deals_von_rss():
    alle_deals = []

    for url in RSS_QUELLEN:
        try:
            print(f"Hole Deals von: {url}")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DealDar-Bot/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                inhalt = response.read().decode("utf-8")

            root = ET.fromstring(inhalt)
            channel = root.find("channel")
            if channel is None:
                continue

            items = channel.findall("item")

            for item in items[:20]:
                titel = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()

                if not titel or not link:
                    continue

                alle_deals.append({
                    "titel": titel,
                    "titel_ar": titel,
                    "link": link,
                    "preis_neu": parse_preis(titel),
                    "preis_alt": "",
                    "rabatt": "",
                    "badge": get_badge(titel),
                    "store": get_store(titel, link),
                    "emoji": get_emoji(titel),
                })

        except Exception as e:
            print(f"Fehler bei {url}: {e}")

    # Duplikate entfernen
    unique = []
    gesehen = set()

    for deal in alle_deals:
        key = deal["titel"].lower()
        if key not in gesehen:
            gesehen.add(key)
            unique.append(deal)

    return unique[:MAX_DEALS]

def erstelle_deal_karten(deals):
    html = ""

    for deal in deals:
        badge_html = ""
        if deal["badge"] == "hot":
            badge_html = '<div class="badge-hot" data-de="🔥 Hot" data-ar="🔥 ساخن">🔥 Hot</div>'

        preis_alt_html = ""
        if deal["preis_alt"]:
            preis_alt_html = f'<span class="deal-price-old">{deal["preis_alt"]}</span>'

        rabatt_html = ""
        if deal["rabatt"]:
            rabatt_html = f'<span class="deal-discount">-{deal["rabatt"]}%</span>'

        html += f"""
    <div class="deal-card">
      {badge_html}
      <div class="deal-img">{deal["emoji"]}</div>
      <div class="deal-body">
        <div class="deal-store">{deal["store"]}</div>
        <div class="deal-title" data-de="{deal["titel"]}" data-ar="{deal["titel_ar"]}">{deal["titel"]}</div>
        <div class="deal-prices">
          <span class="deal-price-new">{deal["preis_neu"]}</span>
          {preis_alt_html}
          {rabatt_html}
        </div>
        <a href="{deal["link"]}" target="_blank" rel="noopener" class="deal-cta" data-de="Zum Deal →" data-ar="اذهب للعرض →">Zum Deal →</a>
      </div>
    </div>"""

    return html

def aktualisiere_website(deals):
    if not os.path.exists(HTML_FILE):
        print(f"{HTML_FILE} nicht gefunden!")
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()

    neue_karten = erstelle_deal_karten(deals)
    jetzt = datetime.now().strftime("%d.%m.%Y %H:%M")

    pattern = r'(<div class="deal-grid">)(.*?)(</div>\s*</section>)'
    replacement = f'\\1\n{neue_karten}\n  \\3\n  <!-- Zuletzt aktualisiert: {jetzt} -->'

    neues_html = re.sub(pattern, replacement, html, flags=re.DOTALL)

    if neues_html == html:
        print("Deal-Grid nicht gefunden. Prüfe index.html")
        return

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(neues_html)

    print(f"Website aktualisiert: {jetzt}")

def main():
    print("DealDar Bot startet...")
    deals = hole_deals_von_rss()

    if not deals:
        print("Keine Deals gefunden.")
        return

    aktualisiere_website(deals)
    print("Fertig.")

if __name__ == "__main__":
    main()
