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

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
MONITOR_FILE = DATA_DIR / "contract_monitor.json"
UPDATES_FILE = DATA_DIR / "daily_updates.json"

OSLO = ZoneInfo("Europe/Oslo")
TODAY = datetime.now(OSLO).strftime("%d.%m.%Y")
TODAY_ISO = datetime.now(OSLO).date().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; InvestmentDashboardMonitor/1.0; "
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

def normalized_hash(text: str) -> str:
    # Ignore trivial whitespace changes.
    normalized = re.sub(r"\s+", " ", text).strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def extract_deadline(text: str) -> tuple[str | None, str | None]:
    # Supports common English date formats and ISO-like dates.
    patterns = [
        r"(?:closing|close|deadline|submission|bid due|response deadline)[^0-9A-Za-z]{0,40}"
        r"((?:\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4}))",
        r"(?:closing|close|deadline|submission|bid due|response deadline)[^0-9A-Za-z]{0,40}"
        r"((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4})",
        r"(?:closing|close|deadline|submission|bid due|response deadline)[^0-9]{0,40}"
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
    # Keep known Clarkson date if the page still contains Oct 2 2026.
    if re.search(r"(2\s+October\s+2026|October\s+2,?\s+2026|2026-10-02)", text, re.I):
        return "02.10.2026", "Tilbudsfrist"
    return None, None

def extract_status(text: str) -> str | None:
    low = text.lower()
    # Conservative wording: never infer an award winner from a vague page.
    if any(x in low for x in ["award notice", "contract awarded", "awarded to"]):
        return "Tildelt / award publisert"
    if any(x in low for x in ["cancelled", "canceled", "tender cancelled", "opportunity cancelled"]):
        return "Kansellert"
    if any(x in low for x in ["closed", "submission closed", "bidding closed"]):
        return "Tilbud lukket / avventer tildeling"
    if any(x in low for x in ["open", "active", "accepting bids", "submission deadline"]):
        return "Aktivt anbud"
    return None

def add_daily_update(updates, company, title, summary, importance="Høy"):
    # Avoid duplicate same-day messages with same title+summary.
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

def main():
    monitor = load_json(MONITOR_FILE, {})
    updates = load_json(UPDATES_FILE, [])
    item = monitor.get("clarkson_wrrf")
    if not item:
        print("Clarkson monitor not configured.")
        return 0

    text = None
    used_url = None
    errors = []
    for url in item.get("source_urls", []):
        try:
            candidate = fetch_text(url)
            if candidate and len(candidate) > 200:
                text = candidate
                used_url = url
                break
        except Exception as e:
            errors.append(f"{url}: {e}")

    item["last_checked"] = TODAY

    if not text:
        item["check_error"] = " | ".join(errors)[:1000]
        monitor["clarkson_wrrf"] = item
        save_json(MONITOR_FILE, monitor)
        print("Could not fetch Clarkson sources; last_checked updated.")
        return 0

    new_hash = normalized_hash(text)
    old_hash = item.get("content_hash")
    deadline, date_type = extract_deadline(text)
    status = extract_status(text)

    changed_fields = []

    if deadline and deadline != item.get("next_date"):
        changed_fields.append(f"frist {item.get('next_date', '–')} → {deadline}")
        item["next_date"] = deadline
        item["date_type"] = date_type or item.get("date_type")

    if status and status != item.get("status"):
        changed_fields.append(f"status {item.get('status', '–')} → {status}")
        item["status"] = status

    # First successful run establishes baseline without generating a false alert.
    if old_hash is None:
        item["content_hash"] = new_hash
        item["source_url_used"] = used_url
        item.pop("check_error", None)
        monitor["clarkson_wrrf"] = item
        save_json(MONITOR_FILE, monitor)
        print("Clarkson baseline established.")
        return 0

    page_changed = old_hash != new_hash

    if changed_fields:
        summary = "Clarkson WRRF er oppdatert: " + "; ".join(changed_fields) + "."
        item["last_updated"] = TODAY
        item["last_change_summary"] = summary
        add_daily_update(updates, "Cambi", item["title"], summary)
    elif page_changed:
        # Flag page change without inventing semantic details.
        summary = (
            "Kilden for Clarkson WRRF er endret siden forrige kontroll. "
            "Ingen sikker endring i frist eller status kunne leses automatisk; bør gjennomgås."
        )
        item["last_updated"] = TODAY
        item["last_change_summary"] = summary
        add_daily_update(updates, "Cambi", item["title"], summary, importance="Middels")

    item["content_hash"] = new_hash
    item["source_url_used"] = used_url
    item.pop("check_error", None)
    monitor["clarkson_wrrf"] = item

    # Keep only recent daily updates to avoid an ever-growing file.
    def parse_iso(x):
        try:
            return datetime.fromisoformat(x.get("Dato", "")).date()
        except Exception:
            return None

    today_date = datetime.now(OSLO).date()
    recent = []
    for x in updates:
        d = parse_iso(x)
        if d is None or (today_date - d).days <= 45:
            recent.append(x)

    save_json(MONITOR_FILE, monitor)
    save_json(UPDATES_FILE, recent)
    print("Clarkson monitor completed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
