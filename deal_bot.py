#!/usr/bin/env python3

import os
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

HTML_FILE = "index.html"
MAX_DEALS = 6
MIN_TEMP = 100
MAX_AGE_DAYS = 3

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
    "notebooksbilliger": "NBB",
    "galaxus": "Galaxus",
    "cyberport": "Cyberport",
}

BLOCKED_WORDS = [
    "abo",
    "vertrag",
    "casino",
    "gewinnspiel",
    "abgelaufen",
    "expired",
    "tarif",
    "newsletter",
    "kostenlos testen",
    "gratis testen",
]

FALLBACK_IMAGES = {
    "technik": "💻",
    "laptop": "💻",
    "computer": "💻",
    "pc": "💻",
    "handy": "📱",
    "smartphone": "📱",
    "iphone": "📱",
    "samsung": "📱",
    "kopfhörer": "🎧",
    "audio": "🎧",
    "headphones": "🎧",
    "gaming": "🎮",
    "playstation": "🎮",
    "xbox": "🎮",
    "nintendo": "🎮",
    "tv": "📺",
    "fernseher": "📺",
    "küche": "🍳",
    "haushalt": "🏠",
    "staubsauger": "🤖",
    "sport": "💪",
    "fitness": "💪",
    "mode": "👗",
    "kleidung": "👗",
    "schuhe": "👟",
    "reisen": "✈️",
    "hotel": "✈️",
    "flug": "✈️",
    "buch": "📚",
    "bücher": "📚",
    "uhr": "⌚",
    "watch": "⌚",
    "kamera": "📷",
    "auto": "🚗",
    "lebensmittel": "🛒",
    "essen": "🍔",
}

# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def parse_temp(title: str) -> int:
    match = re.search(r"(\d+)\s*°", title)
    if match:
        return int(match.group(1))
    return 0

def parse_prices(title: str):
    """
    Nimmt Euro-Werte aus dem Titel.
    Heuristik:
    - letzter €-Wert = aktueller Preis
    - vorletzter €-Wert = alter Preis (optional)
    """
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*€", title)
    if not matches:
        return "?", ""

    current_price = matches[-1] + "€"
    old_price = matches[-2] + "€" if len(matches) >= 2 else ""
    return current_price, old_price

def parse_discount(title: str) -> str:
    match = re.search(r"(\d{1,2})\s*%", title)
    if match:
        return match.group(1)
    return ""

def extract_image(description: str) -> str:
    if not description:
        return ""

    description = html.unescape(description)

    match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', description, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r'<img[^>]+data-src=["\']([^"\']+)["\']', description, re.IGNORECASE)
    if match:
        return match.group(1)

    match = re.search(r'https?://[^"\'>\s]+\.(?:jpg|jpeg|png|webp)', description, re.IGNORECASE)
    if match:
        return match.group(0)

    return ""

def get_store(title: str, link: str) -> str:
    text = f"{title} {link}".lower()
    for keyword, store in STORE_KEYWORDS.items():
        if keyword in text:
            return store
    return "Online"

def get_fallback_emoji(title: str) -> str:
    title_lower = title.lower()
    for keyword, emoji in FALLBACK_IMAGES.items():
        if keyword in title_lower:
            return emoji
    return "🏷️"

def is_recent(pub_date_str: str) -> bool:
    if not pub_date_str:
        return False

    try:
        dt = parsedate_to_datetime(pub_date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=MAX_AGE_DAYS)
        return dt >= cutoff
    except Exception:
        return False

def is_good_deal(title: str, temp: int, current_price: str) -> bool:
    title_lower = title.lower()

    if temp < MIN_TEMP:
        return False

    if current_price == "?":
        return False

    if any(word in title_lower for word in BLOCKED_WORDS):
        return False

    return True

# ------------------------------------------------------------
# Feed laden
# ------------------------------------------------------------

def fetch_deals():
    all_deals = []

    for url in RSS_QUELLEN:
        print(f"Lade Feed: {url}")

        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DealDarBot/5.0"}
            )

            with urllib.request.urlopen(req, timeout=15) as response:
                data = response.read().decode("utf-8", errors="ignore")

            root = ET.fromstring(data)
            channel = root.find("channel")
            if channel is None:
                print("Kein channel gefunden.")
                continue

            items = channel.findall("item")
            print(f"Items gefunden: {len(items)}")

            for item in items[:40]:
                title = clean_text(item.findtext("title", ""))
                link = clean_text(item.findtext("link", ""))
                description = item.findtext("description", "") or ""
                pub_date = clean_text(item.findtext("pubDate", ""))

                if not title or not link:
                    continue

                if not is_recent(pub_date):
                    continue

                temp = parse_temp(title)
                current_price, old_price = parse_prices(title)
                discount = parse_discount(title)

                if not is_good_deal(title, temp, current_price):
                    continue

                deal = {
                    "title": title,
                    "link": link,
                    "image": extract_image(description),
                    "store": get_store(title, link),
                    "temp": temp,
                    "current_price": current_price,
                    "old_price": old_price,
                    "discount": discount,
                    "emoji": get_fallback_emoji(title),
                    "pub_date": pub_date,
                }

                all_deals.append(deal)

        except Exception as e:
            print(f"Fehler bei Feed {url}: {e}")

    # Duplikate entfernen
    unique = []
    seen = set()

    for deal in all_deals:
        key = deal["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(deal)

    # Nach Temperatur sortieren
    unique.sort(key=lambda d: d["temp"], reverse=True)

    print(f"Verwertbare Deals: {len(unique)}")
    return unique[:MAX_DEALS]

# ------------------------------------------------------------
# HTML bauen
# ------------------------------------------------------------

def build_image_html(deal: dict) -> str:
    if deal["image"]:
        return (
            f'<div class="deal-img">'
            f'<img src="{deal["image"]}" alt="{html.escape(deal["title"])}" loading="lazy" referrerpolicy="no-referrer">'
            f'</div>'
        )

    return f'<div class="deal-img deal-img-fallback">{deal["emoji"]}</div>'

def build_card(deal: dict) -> str:
    badge_html = f'<div class="badge-hot">🔥 {deal["temp"]}°</div>'

    old_price_html = ""
    if deal["old_price"]:
        old_price_html = f'<span class="deal-price-old">{deal["old_price"]}</span>'

    discount_html = ""
    if deal["discount"]:
        discount_html = f'<span class="deal-discount">-{deal["discount"]}%</span>'

    image_html = build_image_html(deal)

    return f"""
<a href="{deal["link"]}" target="_blank" rel="noopener nofollow" class="deal-card-link">
  <div class="deal-card">
    {badge_html}
    {image_html}
    <div class="deal-body">
      <div class="deal-store">{deal["store"]}</div>
      <div class="deal-title">{html.escape(deal["title"])}</div>
      <div class="deal-prices">
        <span class="deal-price-new">{deal["current_price"]}</span>
        {old_price_html}
        {discount_html}
      </div>
      <div class="deal-cta">Zum Deal →</div>
    </div>
  </div>
</a>
"""

# ------------------------------------------------------------
# HTML aktualisieren
# ------------------------------------------------------------

def update_html(deals):
    if not os.path.exists(HTML_FILE):
        print(f"{HTML_FILE} fehlt.")
        return

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html_text = f.read()

    cards_html = "\n".join(build_card(deal) for deal in deals)

    pattern = r'(<div class="deal-grid">)(.*?)(</div>)'
    new_html = re.sub(
        pattern,
        f'\\1\n{cards_html}\n\\3',
        html_text,
        count=1,
        flags=re.DOTALL
    )

    if new_html == html_text:
        print("Deal-Grid nicht gefunden. Prüfe index.html.")
        return

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(new_html)

    print("Website aktualisiert.")

# ------------------------------------------------------------
# Main
# ------------------------------------------------------------

def main():
    print("DealDar Bot V5 startet...")
    deals = fetch_deals()

    if not deals:
        print("Keine passenden frischen Deals gefunden.")
        return

    update_html(deals)
    print("Fertig.")

if __name__ == "__main__":
    main()
