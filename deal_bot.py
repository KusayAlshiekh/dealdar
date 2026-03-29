#!/usr/bin/env python3

import os
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

HTML_FILE = "index.html"
RSS_URL = "https://www.mydealz.de/rss/hot"

MAX_DEALS = 6
MIN_TEMP = 100
MAX_AGE_DAYS = 3

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
    "personalisiert",
    "gutscheinübersicht",
    "app only",
    "nur in der app",
    "app-exklusiv",
]

FALLBACK_EMOJIS = {
    "iphone": "📱",
    "smartphone": "📱",
    "samsung": "📱",
    "apple": "🍎",
    "kopfhörer": "🎧",
    "headphones": "🎧",
    "echo": "🔊",
    "fire tv": "📺",
    "kindle": "📚",
    "monitor": "🖥️",
    "laptop": "💻",
    "gaming": "🎮",
    "playstation": "🎮",
    "xbox": "🎮",
    "tv": "📺",
    "uhr": "⌚",
    "watch": "⌚",
    "staubsauger": "🧹",
    "kaffee": "☕",
    "küche": "🍳",
    "haushalt": "🏠",
}

def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text

def parse_temp(title: str) -> int:
    match = re.search(r"(\d+)\s*°", title)
    return int(match.group(1)) if match else 0

def parse_prices(title: str):
    matches = re.findall(r"(\d+(?:[.,]\d+)?)\s*€", title)
    if not matches:
        return "?", ""

    current_price = matches[-1] + "€"
    old_price = matches[-2] + "€" if len(matches) >= 2 else ""
    return current_price, old_price

def parse_discount(title: str) -> str:
    match = re.search(r"(\d{1,2})\s*%", title)
    return match.group(1) if match else ""

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

def get_fallback_emoji(title: str) -> str:
    title_lower = title.lower()
    for keyword, emoji in FALLBACK_EMOJIS.items():
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

def is_amazon_deal(title: str, link: str, description: str) -> bool:
    combined = f"{title} {link} {description}".lower()
    return "amazon" in combined

def is_good_deal(title: str, temp: int, current_price: str) -> bool:
    title_lower = title.lower()

    if temp < MIN_TEMP:
        return False

    if current_price == "?":
        return False

    if any(word in title_lower for word in BLOCKED_WORDS):
        return False

    return True

def fetch_deals():
    deals = []

    try:
        print(f"Lade Feed: {RSS_URL}")

        req = urllib.request.Request(
            RSS_URL,
            headers={"User-Agent": "DealDarBot/6.0"}
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            data = response.read().decode("utf-8", errors="ignore")

        root = ET.fromstring(data)
        channel = root.find("channel")
        if channel is None:
            print("Kein channel gefunden.")
            return []

        items = channel.findall("item")
        print(f"Items gefunden: {len(items)}")

        for item in items[:60]:
            title = clean_text(item.findtext("title", ""))
            link = clean_text(item.findtext("link", ""))
            description = item.findtext("description", "") or ""
            pub_date = clean_text(item.findtext("pubDate", ""))

            if not title or not link:
                continue

            if not is_recent(pub_date):
                continue

            if not is_amazon_deal(title, link, description):
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
                "store": "Amazon",
                "temp": temp,
                "current_price": current_price,
                "old_price": old_price,
                "discount": discount,
                "emoji": get_fallback_emoji(title),
                "pub_date": pub_date,
            }

            deals.append(deal)

    except Exception as e:
        print(f"Fehler beim Feed: {e}")
        return []

    unique = []
    seen = set()

    for deal in deals:
        key = deal["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(deal)

    unique.sort(key=lambda d: d["temp"], reverse=True)

    print(f"Verwertbare Amazon-Deals: {len(unique)}")
    return unique[:MAX_DEALS]

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

    old_price_html = f'<span class="deal-price-old">{deal["old_price"]}</span>' if deal["old_price"] else ""
    discount_html = f'<span class="deal-discount">-{deal["discount"]}%</span>' if deal["discount"] else ""
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

def main():
    print("DealDar Bot V6 startet...")
    deals = fetch_deals()

    if not deals:
        print("Keine passenden Amazon-Deals gefunden.")
        return

    update_html(deals)
    print("Fertig.")

if __name__ == "__main__":
    main()
