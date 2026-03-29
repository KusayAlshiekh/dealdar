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
    "otto": "OTTO",
    "lidl": "Lidl",
    "aldi": "Aldi",
    "notebooksbilliger": "NBB",
    "galaxus": "Galaxus",
}

MARKEN = [
    "apple", "samsung", "sony", "bose", "jbl", "lg", "lenovo", "asus",
    "acer", "hp", "xiaomi", "anker", "dyson", "nintendo", "xbox",
    "playstation", "philips", "garmin", "amazon", "nike", "adidas"
]

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

def parse_preis(titel: str) -> str:
    match = re.search(r'(\d+(?:[.,]\d+)?)\s*€', titel)
    if match:
        return match.group(0)
    return "Preis unbekannt"

def parse_rabatt(titel: str) -> str:
    match = re.search(r'(\d{1,2})\s*%', titel)
    if match:
        return match.group(1)
    return ""

def get_badge(titel: str, rabatt: str) -> str:
    titel_lower = titel.lower()
    if rabatt:
        try:
            if int(rabatt) >= 30:
                return "hot"
        except ValueError:
            pass
    if "gutschein" in titel_lower or "gratis" in titel_lower:
        return "hot"
    return ""

def clean_title(titel: str) -> str:
    titel = html.unescape(titel)
    titel = re.sub(r'\s+', ' ', titel).strip()
    titel = titel.replace("  ", " ")
    return titel

def extract_image_url(description: str) -> str:
    if not description:
        return ""

    description = html.unescape(description)

    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description, re.IGNORECASE)
    if img_match:
        return img_match.group(1)

    data_src_match = re.search(r'<img[^>]+data-src=["\']([^"\']+)["\']', description, re.IGNORECASE)
    if data_src_match:
        return data_src_match.group(1)

    url_match = re.search(r'https?://[^"\'>\s]+\.(jpg|jpeg|png|webp)', description, re.IGNORECASE)
    if url_match:
        return url_match.group(0)

    return ""

def is_good_deal(titel: str, preis: str, rabatt: str, store: str) -> bool:
    titel_lower = titel.lower()

    schlechte_woerter = [
        "gratis testen", "kostenlos testen", "gewinnspiel", "newsletter",
        "abo", "tarif", "vertrag", "casino", "wett", "gutscheinheft"
    ]
    if any(w in titel_lower for w in schlechte_woerter):
        return False

    if preis == "Preis unbekannt":
        return False

    if store == "Online" and not any(marke in titel_lower for marke in MARKEN):
        return False

    if rabatt:
        try:
            if int(rabatt) >= 15:
                return True
        except ValueError:
            pass

    if any(marke in titel_lower for marke in MARKEN):
        return True

    return False

def hole_deals_von_rss():
    alle_deals = []

    for url in RSS_QUELLEN:
        try:
            print(f"Hole Deals von: {url}")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DealDar-Bot/2.0"}
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                inhalt = response.read().decode("utf-8", errors="ignore")

            root = ET.fromstring(inhalt)
            channel = root.find("channel")
            if channel is None:
                continue

            items = channel.findall("item")

            for item in items[:25]:
                titel_raw = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                beschreibung = item.findtext("description", "").strip()

                if not titel_raw or not link:
                    continue

                titel = clean_title(titel_raw)
                preis = parse_preis(titel)
                rabatt = parse_rabatt(titel)
                store = get_store(titel, link)
                bild = extract_image_url(beschreibung)

                if not is_good_deal(titel, preis, rabatt, store):
                    continue

                alle_deals.append({
                    "titel": titel,
                    "link": link,
                    "preis_neu": preis,
                    "preis_alt": "",
                    "rabatt": rabatt,
                    "badge": get_badge(titel, rabatt),
                    "store": store,
                    "emoji": get_emoji(titel),
                    "bild": bild,
                })

        except Exception as e:
            print(f"Fehler bei {url}: {e}")

    unique = []
    gesehen = set()

    for deal in alle_deals:
        key = deal["titel"].lower()
        if key not in gesehen:
            gesehen.add(key)
            unique.append(deal)

    return unique[:MAX_DEALS]

def build_image_html(deal: dict) -> str:
    bild = deal.get("bild", "").strip()
    emoji = deal.get("emoji", "🏷️")

    if bild:
        return f'<div class="deal-img"><img src="{bild}" alt="{deal["titel"]}" loading="lazy" referrerpolicy="no-referrer"></div>'

    return f'<div class="deal-img deal-img-fallback">{emoji}</div>'

def erstelle_deal_karten(deals):
    html_output = ""

    for deal in deals:
        badge_html = ""
        if deal["badge"] == "hot":
            badge_html = '<div class="badge-hot">🔥 Hot</div>'

        preis_alt_html = ""
        if deal["preis_alt"]:
            preis_alt_html = f'<span class="deal-price-old">{deal["preis_alt"]}</span>'

        rabatt_html = ""
        if deal["rabatt"]:
            rabatt_html = f'<span class="deal-discount">-{deal["rabatt"]}%</span>'

        bild_html = build_image_html(deal)

        html_output += f"""
    <a href="{deal["link"]}" target="_blank" rel="noopener nofollow" class="deal-card-link">
      <div class="deal-card">
        {badge_html}
        {bild_html}
        <div class="deal-body">
          <div class="deal-store">{deal["store"]}</div>
          <div class="deal-title">{deal["titel"]}</div>
          <div class="deal-prices">
            <span class="deal-price-new">{deal["preis_neu"]}</span>
            {preis_alt_html}
            {rabatt_html}
          </div>
          <div class="deal-cta">Zum Deal →</div>
        </div>
      </div>
    </a>"""

    return html_output

def inject_style_if_missing(html_text: str) -> str:
    extra_css = """
<style id="dealdar-bot-styles">
.deal-img {
  width: 100%;
  height: 180px;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  border-radius: 14px 14px 0 0;
  background: #111;
}
.deal-img img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.deal-img-fallback {
  font-size: 3rem;
}
.deal-title {
  line-height: 1.4;
}
</style>
"""
    if 'id="dealdar-bot-styles"' in html_text:
        return html_text

    if "</head>" in html_text:
        return html_text.replace("</head>", extra_css + "\n</head>")

    return html_text

def aktualisiere_website(deals):
    if not os.path.exists(HTML_FILE):
        print(f"{HTML_FILE} nicht gefunden!")
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html_text = f.read()

    html_text = inject_style_if_missing(html_text)

    neue_karten = erstelle_deal_karten(deals)
    jetzt = datetime.now().strftime("%d.%m.%Y %H:%M")

    pattern = r'(<div class="deal-grid">)(.*?)(</div>\s*</section>)'
    replacement = f'\\1\n{neue_karten}\n  \\3\n  <!-- Zuletzt aktualisiert: {jetzt} -->'

    neues_html = re.sub(pattern, replacement, html_text, flags=re.DOTALL)

    if neues_html == html_text:
        print("Deal-Grid nicht gefunden. Prüfe index.html")
        return

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(neues_html)

    print(f"Website aktualisiert: {jetzt}")

def main():
    print("DealDar Bot V2 startet...")
    deals = hole_deals_von_rss()

    if not deals:
        print("Keine brauchbaren Deals gefunden.")
        return

    aktualisiere_website(deals)
    print("Fertig.")

if __name__ == "__main__":
    main()
