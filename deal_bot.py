#!/usr/bin/env python3
"""
DealDar.de – Automatischer Deal-Bot
Holt Deals von mydealz RSS, bewertet sie mit Claude AI,
und aktualisiert die dealdar.html automatisch.
"""

import os
import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
import urllib.request
import urllib.parse
import anthropic

# ── KONFIGURATION ──────────────────────────────────────────────
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
HTML_FILE = "dealdar.html"
MAX_DEALS = 6          # Wie viele Deals auf der Website angezeigt werden
MIN_RABATT = 20        # Nur Deals mit mindestens X% Rabatt

# RSS Quellen (alle kostenlos & legal)
RSS_QUELLEN = [
    "https://www.mydealz.de/rss/hot",        # Nur heiße Deals
    "https://www.mydealz.de/rss/alle",       # Alle neuen Deals
]

# ── EMOJIS PRO KATEGORIE ───────────────────────────────────────
KATEGORIE_EMOJIS = {
    "technik": "💻", "laptop": "💻", "computer": "💻", "pc": "💻",
    "handy": "📱", "smartphone": "📱", "iphone": "📱", "samsung": "📱",
    "kopfhörer": "🎧", "audio": "🎧", "headphones": "🎧",
    "gaming": "🎮", "playstation": "🎮", "xbox": "🎮", "nintendo": "🎮",
    "tv": "📺", "fernseher": "📺",
    "küche": "🍳", "kochen": "🍳",
    "haushalt": "🏠", "staubsauger": "🤖", "roomba": "🤖",
    "sport": "💪", "fitness": "💪",
    "mode": "👗", "kleidung": "👗", "schuhe": "👟",
    "reisen": "✈️", "hotel": "✈️", "flug": "✈️",
    "buch": "📚", "bücher": "📚",
    "uhr": "⌚", "watch": "⌚", "garmin": "⌚",
    "kamera": "📷", "foto": "📷",
    "auto": "🚗",
    "lebensmittel": "🛒", "essen": "🍔",
}

def get_emoji(titel: str) -> str:
    """Wählt passendes Emoji basierend auf Produktname."""
    titel_lower = titel.lower()
    for keyword, emoji in KATEGORIE_EMOJIS.items():
        if keyword in titel_lower:
            return emoji
    return "🏷️"  # Standard-Emoji

def hole_deals_von_rss() -> list[dict]:
    """Holt Deals von mydealz RSS-Feeds."""
    alle_deals = []
    
    for url in RSS_QUELLEN:
        try:
            print(f"📡 Hole Deals von: {url}")
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "DealDar-Bot/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                inhalt = response.read().decode("utf-8")
            
            root = ET.fromstring(inhalt)
            channel = root.find("channel")
            if not channel:
                continue
                
            items = channel.findall("item")
            print(f"   ✅ {len(items)} Deals gefunden")
            
            for item in items[:20]:  # Max 20 pro Quelle
                titel = item.findtext("title", "").strip()
                link = item.findtext("link", "").strip()
                beschreibung = item.findtext("description", "").strip()
                
                if not titel or not link:
                    continue
                
                # Preis aus Titel extrahieren (z.B. "Sony WH-1000XM5 für 249€")
                preis_match = re.search(r'(\d+(?:[.,]\d+)?)\s*€', titel)
                preis = preis_match.group(0) if preis_match else "Preis unbekannt"
                
                alle_deals.append({
                    "titel": titel,
                    "link": link,
                    "beschreibung": beschreibung[:300],
                    "preis": preis,
                    "emoji": get_emoji(titel),
                })
        
        except Exception as e:
            print(f"   ⚠️  Fehler bei {url}: {e}")
            continue
    
    # Duplikate entfernen
    gesehen = set()
    unique_deals = []
    for deal in alle_deals:
        key = deal["titel"][:50]
        if key not in gesehen:
            gesehen.add(key)
            unique_deals.append(deal)
    
    print(f"\n📦 Gesamt: {len(unique_deals)} einzigartige Deals gesammelt")
    return unique_deals

def bewerte_deals_mit_ai(deals: list[dict]) -> list[dict]:
    """Claude AI bewertet und filtert die besten Deals."""
    if not deals:
        return []
    
    print(f"\n🤖 AI bewertet {len(deals)} Deals...")
    
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    
    # Deals als kompakte Liste für AI vorbereiten
    deals_text = ""
    for i, deal in enumerate(deals):
        deals_text += f"{i}. {deal['titel']} | Preis: {deal['preis']}\n"
    
    prompt = f"""Du bist ein Deal-Experte für DealDar.de, eine zweisprachige (Deutsch/Arabisch) Deal-Website.

Hier sind {len(deals)} Deals von mydealz:

{deals_text}

Wähle die TOP {MAX_DEALS} besten Deals aus. Kriterien:
- Echter Rabatt (kein Fake-Sale)
- Bekannte Marken (Sony, Samsung, Apple, Lenovo, etc.)
- Breites Interesse (Technik, Gaming, Haushalt, etc.)
- Verschiedene Kategorien (nicht 5x Kopfhörer)

Antworte NUR mit einem JSON-Array. Keine Erklärung, kein Text davor oder danach.
Format:
[
  {{
    "index": 0,
    "store": "Amazon",
    "preis_neu": "249€",
    "preis_alt": "379€",
    "rabatt": "34",
    "badge": "hot",
    "titel_de": "Sony WH-1000XM5 Kopfhörer",
    "titel_ar": "سماعات سوني WH-1000XM5"
  }}
]

badge kann sein: "hot" (sehr gut), "neu" (neu eingetroffen), oder "" (normal).
Schätze preis_alt wenn nicht angegeben (realistisch).
Übersetze titel_ar ins Arabische.
Erkenne den store aus dem Link oder Titel (Amazon, MediaMarkt, Saturn, etc.).
"""

    try:
        message = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )
        
        antwort = message.content[0].text.strip()
        
        # JSON aus Antwort extrahieren
        json_match = re.search(r'\[.*\]', antwort, re.DOTALL)
        if not json_match:
            print("⚠️  AI hat kein gültiges JSON zurückgegeben")
            return deals[:MAX_DEALS]
        
        bewertete = json.loads(json_match.group())
        print(f"✅ AI hat {len(bewertete)} Top-Deals ausgewählt")
        
        # Original-Deal-Daten mit AI-Bewertung zusammenführen
        ergebnis = []
        for b in bewertete:
            idx = b.get("index", 0)
            original = deals[idx] if idx < len(deals) else deals[0]
            ergebnis.append({
                "titel_de": b.get("titel_de", original["titel"]),
                "titel_ar": b.get("titel_ar", original["titel"]),
                "preis_neu": b.get("preis_neu", original["preis"]),
                "preis_alt": b.get("preis_alt", ""),
                "rabatt": b.get("rabatt", ""),
                "badge": b.get("badge", ""),
                "store": b.get("store", "Online"),
                "link": original["link"],
                "emoji": original["emoji"],
            })
        
        return ergebnis
    
    except Exception as e:
        print(f"⚠️  AI-Fehler: {e}")
        return deals[:MAX_DEALS]

def erstelle_deal_karten(deals: list[dict]) -> str:
    """Generiert HTML für die Deal-Karten."""
    html = ""
    
    for deal in deals:
        badge_html = ""
        if deal.get("badge") == "hot":
            badge_html = '<div class="badge-hot" data-de="🔥 Hot" data-ar="🔥 ساخن">🔥 Hot</div>'
        elif deal.get("badge") == "neu":
            badge_html = '<div class="badge-neu" data-de="⭐ Neu" data-ar="⭐ جديد">⭐ Neu</div>'
        
        rabatt_html = ""
        if deal.get("rabatt"):
            rabatt_html = f'<span class="deal-discount">-{deal["rabatt"]}%</span>'
        
        preis_alt_html = ""
        if deal.get("preis_alt"):
            preis_alt_html = f'<span class="deal-price-old">{deal["preis_alt"]}</span>'
        
        # Link mit Affiliate-Tag (später eintragen)
        link = deal.get("link", "#")
        
        html += f"""
    <div class="deal-card">
      {badge_html}
      <div class="deal-img">{deal.get("emoji", "🏷️")}</div>
      <div class="deal-body">
        <div class="deal-store">{deal.get("store", "Online")}</div>
        <div class="deal-title" data-de="{deal['titel_de']}" data-ar="{deal['titel_ar']}">{deal['titel_de']}</div>
        <div class="deal-prices">
          <span class="deal-price-new">{deal.get("preis_neu", "")}</span>
          {preis_alt_html}
          {rabatt_html}
        </div>
        <a href="{link}" target="_blank" rel="noopener" class="deal-cta" data-de="Zum Deal →" data-ar="اذهب للعرض →">Zum Deal →</a>
      </div>
    </div>"""
    
    return html

def aktualisiere_website(deals: list[dict]):
    """Ersetzt die Deal-Karten in der dealdar.html."""
    if not os.path.exists(HTML_FILE):
        print(f"❌ {HTML_FILE} nicht gefunden!")
        return
    
    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    
    # Neuen HTML-Block für Deals erstellen
    neue_karten = erstelle_deal_karten(deals)
    
    # Timestamp hinzufügen
    jetzt = datetime.now().strftime("%d.%m.%Y %H:%M")
    
    # Deal-Grid in HTML ersetzen
    pattern = r'(<div class="deal-grid">)(.*?)(</div>\s*</section>)'
    neuer_block = f'<div class="deal-grid">\n{neue_karten}\n  </div>\n  <!-- Zuletzt aktualisiert: {jetzt} -->\n  </section>'
    
    neues_html = re.sub(pattern, neuer_block, html, flags=re.DOTALL)
    
    if neues_html == html:
        print("⚠️  Konnte Deal-Grid nicht finden – HTML-Struktur prüfen")
        return
    
    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(neues_html)
    
    print(f"\n✅ dealdar.html erfolgreich aktualisiert! ({jetzt})")
    print(f"   {len(deals)} Deals eingetragen")

def main():
    print("=" * 50)
    print("🌙 DealDar Deal-Bot gestartet")
    print("=" * 50)
    
    if not ANTHROPIC_API_KEY:
        print("❌ ANTHROPIC_API_KEY nicht gesetzt!")
        print("   Setze ihn mit: export ANTHROPIC_API_KEY='dein-key'")
        return
    
    # 1. Deals holen
    deals = hole_deals_von_rss()
    if not deals:
        print("❌ Keine Deals gefunden!")
        return
    
    # 2. AI bewertet Deals
    top_deals = bewerte_deals_mit_ai(deals)
    if not top_deals:
        print("❌ AI konnte keine Deals auswählen!")
        return
    
    # 3. Website aktualisieren
    aktualisiere_website(top_deals)
    
    print("\n🎉 Fertig! Die Website ist aktuell.")
    print("=" * 50)

if __name__ == "__main__":
    main()
