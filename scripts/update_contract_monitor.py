from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
MONITOR_FILE = DATA_DIR / "contract_monitor.json"
UPDATES_FILE = DATA_DIR / "daily_updates.json"

OSLO = ZoneInfo("Europe/Oslo")
TODAY = datetime.now(OSLO).strftime("%d.%m.%Y")
TODAY_ISO = datetime.now(OSLO).date().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; InvestmentDashboardMonitor/1.1; "
        "+https://github.com/itfc72/Investeringsdashboard)"
    )
}


def load_json(path: Path, default):
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def fetch_text(url: str) -> str:
    r = requests.get(url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = " ".join(soup.stripped_strings)
    return re.sub(r"\s+", " ", text).strip()


def fetch_all_sources(urls):
    parts = []
    used_urls = []
    errors = []
    for url in urls:
        try:
            text = fetch_text(url)
            if text and len(text) > 200:
                parts.append(f"SOURCE {url}: {text}")
                used_urls.append(url)
        except Exception as e:
            errors.append(f"{url}: {e}")
    return "\n".join(parts), used_urls, errors


def normalized_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def extract_deadline(text: str) -> tuple[str | None, str | None]:
    patterns = [
        r"(?:closing|close|deadline|submission|bid due|response deadline|respond by)[^0-9A-Za-z]{0,40}"
        r"((?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}))",
        r"(?:closing|close|deadline|submission|bid due|response deadline|respond by)[^0-9A-Za-z]{0,40}"
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
        r"(?:closing|close|deadline|submission|bid due|response deadline|respond by)[^0-9]{0,40}"
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for p in patterns:
        m = re.search(p, text, flags=re.I)
        if m:
            raw = m.group(1)
            for fmt in ("%d %B %Y", "%B %d, %Y", "%B %d %Y", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(raw.replace(",", ""), fmt.replace(",", ""))
                    return dt.strftime("%d.%m.%Y"), "Tilbudsfrist"
                except ValueError:
                    pass
    if re.search(r"(2\s+October\s+2026|October\s+2,?\s+2026|2026-10-02)", text, re.I):
        return "02.10.2026", "Tilbudsfrist"
    return None, None


def extract_tender_status(text: str) -> str | None:
    """Conservative tender parser: only explicit status wording counts."""
    low = re.sub(r"\s+", " ", text).lower()

    explicit_award = [
        r"bid status\s*[:\-]\s*awarded\b",
        r"opportunity status\s*[:\-]\s*awarded\b",
        r"contract status\s*[:\-]\s*awarded\b",
        r"awarded vendor\s*[:\-]",
        r"awarded to\s+[a-z0-9]",
    ]
    if any(re.search(p, low, flags=re.I) for p in explicit_award):
        return "Tildelt / award publisert"

    explicit_cancel = [
        r"bid status\s*[:\-]\s*cancelled\b",
        r"bid status\s*[:\-]\s*canceled\b",
        r"opportunity status\s*[:\-]\s*cancelled\b",
        r"opportunity status\s*[:\-]\s*canceled\b",
    ]
    if any(re.search(p, low, flags=re.I) for p in explicit_cancel):
        return "Kansellert"

    explicit_closed = [
        r"bid status\s*[:\-]\s*closed\b",
        r"opportunity status\s*[:\-]\s*closed\b",
        r"submission status\s*[:\-]\s*closed\b",
    ]
    if any(re.search(p, low, flags=re.I) for p in explicit_closed):
        return "Tilbud lukket / avventer tildeling"

    explicit_open = [
        r"bid status\s*[:\-]\s*open\b",
        r"opportunity status\s*[:\-]\s*open\b",
        r"respond by\s+",
        r"submission deadline\s+",
    ]
    if any(re.search(p, low, flags=re.I) for p in explicit_open):
        return "Aktivt anbud"

    return None


def extract_rosedale_status(text: str) -> str | None:
    """
    Rosedale-specific parser.
    Generic wording that manufacturing is expected after a later NTP does NOT count.
    Only explicit evidence that NTP/production has actually started changes status.
    """
    low = re.sub(r"\s+", " ", text).lower()

    explicit_started = [
        r"notice to proceed has been issued",
        r"notice to proceed was issued",
        r"cambi has received (?:the )?notice to proceed",
        r"received (?:the )?notice to proceed",
        r"manufacturing has commenced",
        r"manufacturing has started",
        r"production has commenced",
        r"production has started",
        r"equipment manufacturing has begun",
    ]
    if any(re.search(p, low, flags=re.I) for p in explicit_started):
        return "NTP mottatt / produksjon igangsatt"

    explicit_cancel = [
        r"rosedale.{0,120}(?:cancelled|canceled)",
        r"(?:cancelled|canceled).{0,120}rosedale",
    ]
    if any(re.search(p, low, flags=re.I) for p in explicit_cancel):
        return "Kansellert / stoppet"

    return None


def add_daily_update(updates, company, title, summary, importance="Høy"):
    key = (TODAY_ISO, company, title, summary)
    existing = {
        (x.get("Dato"), x.get("Selskap"), x.get("Tittel"), x.get("Oppdatering"))
        for x in updates
    }
    if key not in existing:
        updates.append({
            "Dato": TODAY_ISO,
            "Selskap": company,
            "Kategori": "Kontrakt / anbud",
            "Tittel": title,
            "Oppdatering": summary,
            "Viktighet": importance,
        })


def process_item(key, item, updates):
    text, used_urls, errors = fetch_all_sources(item.get("source_urls", []))
    item["last_checked"] = TODAY

    if not text:
        item["check_error"] = " | ".join(errors)[:1500]
        print(f"{key}: no sources could be fetched.")
        return item

    new_hash = normalized_hash(text)
    old_hash = item.get("content_hash")
    changed_fields = []

    monitor_type = item.get("monitor_type", "tender")

    if monitor_type == "tender":
        deadline, date_type = extract_deadline(text)
        status = extract_tender_status(text)

        if deadline and deadline != item.get("next_date"):
            changed_fields.append(f"frist {item.get('next_date', '–')} → {deadline}")
            item["next_date"] = deadline
            item["date_type"] = date_type or item.get("date_type")

        if status and status != item.get("status"):
            changed_fields.append(f"status {item.get('status', '–')} → {status}")
            item["status"] = status

    elif monitor_type == "rosedale_ntp":
        status = extract_rosedale_status(text)
        if status and status != item.get("status"):
            changed_fields.append(f"status {item.get('status', '–')} → {status}")
            item["status"] = status

    # First successful run establishes a baseline and must not alert.
    if old_hash is None:
        item["content_hash"] = new_hash
        item["source_urls_used"] = used_urls
        item.pop("check_error", None)
        print(f"{key}: baseline established.")
        return item

    page_changed = old_hash != new_hash

    if changed_fields:
        summary = f"{item['title']} er oppdatert: " + "; ".join(changed_fields) + "."
        item["last_updated"] = TODAY
        item["last_change_summary"] = summary
        item.pop("review_note", None)
        item.pop("last_source_change", None)
        add_daily_update(updates, item.get("company", ""), item["title"], summary)
    elif page_changed:
        # A raw webpage/hash change is not enough to count as a real investment update.
        # Record it for later review, but do not change last_updated and do not create
        # a homepage alert unless status/date/NTP changed explicitly.
        item["last_source_change"] = TODAY
        item["review_note"] = (
            f"Kildene for {item['title']} er endret siden forrige kontroll, "
            "men ingen sikker status-/datoendring ble funnet automatisk."
        )

    item["content_hash"] = new_hash
    item["source_urls_used"] = used_urls
    item.pop("check_error", None)
    print(f"{key}: completed.")
    return item


def main():
    monitor = load_json(MONITOR_FILE, {})
    updates = load_json(UPDATES_FILE, [])

    for key, item in list(monitor.items()):
        monitor[key] = process_item(key, item, updates)

    # Keep only recent daily updates.
    today_date = datetime.now(OSLO).date()
    recent = []
    for x in updates:
        try:
            d = datetime.fromisoformat(x.get("Dato", "")).date()
        except Exception:
            d = None
        if d is None or (today_date - d).days <= 45:
            recent.append(x)

    save_json(MONITOR_FILE, monitor)
    save_json(UPDATES_FILE, recent)
    print("Contract monitor completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
