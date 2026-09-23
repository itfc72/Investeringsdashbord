from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_FILE = DATA_DIR / "contract_news_config.json"
MONITOR_FILE = DATA_DIR / "contract_monitor.json"
UPDATES_FILE = DATA_DIR / "daily_updates.json"

OSLO = ZoneInfo("Europe/Oslo")
TODAY = datetime.now(OSLO).strftime("%d.%m.%Y")
TODAY_ISO = datetime.now(OSLO).date().isoformat()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; InvestmentDashboardNewsMonitor/1.0; "
        "+https://github.com/itfc72/Investeringsdashbord)"
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


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def signal_id(title: str, url: str) -> str:
    raw = f"{clean_text(title).lower()}|{url.strip().lower()}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def fetch_links(source_url: str):
    r = requests.get(source_url, timeout=30, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    source_host = urlparse(source_url).netloc.lower().removeprefix("www.")

    rows = []
    for a in soup.find_all("a", href=True):
        title = clean_text(" ".join(a.stripped_strings))
        if len(title) < 12 or len(title) > 240:
            continue

        href = (a.get("href") or "").strip()
        if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue

        url = urljoin(source_url, href)
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            continue

        host = parsed.netloc.lower().removeprefix("www.")
        if host != source_host and not host.endswith("." + source_host):
            continue

        rows.append({"title": title, "url": url})

    return rows


def contains_any(text: str, keywords) -> bool:
    low = text.lower()
    return any(str(keyword).lower() in low for keyword in keywords or [])


def is_relevant(title: str, cfg: dict) -> bool:
    low = title.lower()

    if contains_any(low, cfg.get("exclude_keywords", [])):
        return False

    return (
        contains_any(low, cfg.get("high_keywords", []))
        or contains_any(low, cfg.get("signal_keywords", []))
    )


def classify_signal(title: str, cfg: dict):
    if contains_any(title, cfg.get("high_keywords", [])):
        return "Høy", "Konkret kommersielt signal"
    return "Middels", "Mulig kontraktssignal"


def collect_candidates(cfg: dict):
    by_id = {}
    used_urls = []
    errors = []

    for source_url in cfg.get("source_urls", []):
        try:
            links = fetch_links(source_url)
            used_urls.append(source_url)
            for row in links:
                if not is_relevant(row["title"], cfg):
                    continue
                sid = signal_id(row["title"], row["url"])
                if sid not in by_id:
                    by_id[sid] = {
                        "id": sid,
                        "title": row["title"],
                        "url": row["url"],
                    }
        except Exception as exc:
            errors.append(f"{source_url}: {exc}")

    return list(by_id.values()), used_urls, errors


def add_daily_update(updates, company, title, summary, importance):
    key = (TODAY_ISO, company, title, summary)
    existing = {
        (x.get("Dato"), x.get("Selskap"), x.get("Tittel"), x.get("Oppdatering"))
        for x in updates
    }
    if key not in existing:
        updates.append({
            "Dato": TODAY_ISO,
            "Selskap": company,
            "Kategori": "Mulig kontraktssignal",
            "Tittel": title,
            "Oppdatering": summary,
            "Viktighet": importance,
        })


def merge_config_and_state(cfg: dict, state: dict):
    item = dict(state or {})
    for key in (
        "company",
        "title",
        "monitor_type",
        "source_label",
        "source_urls",
        "high_keywords",
        "signal_keywords",
        "exclude_keywords",
    ):
        if key in cfg:
            item[key] = cfg[key]

    item.setdefault("status", "Aktiv nyhetsovervåkning")
    item.setdefault("seen_signal_ids", [])
    item.setdefault("signals", [])
    return item


def process_news_monitor(key: str, cfg: dict, state: dict, updates: list):
    item = merge_config_and_state(cfg, state)
    item["last_checked"] = TODAY

    candidates, used_urls, errors = collect_candidates(cfg)
    item["source_urls_used"] = used_urls

    if not used_urls:
        item["check_error"] = " | ".join(errors)[:1500]
        print(f"{key}: no sources could be fetched.")
        return item

    item.pop("check_error", None)

    candidate_ids = [x["id"] for x in candidates]
    seen = list(item.get("seen_signal_ids") or [])

    # Første vellykkede kjøring etablerer baseline uten å varsle om gamle saker.
    if not seen:
        item["seen_signal_ids"] = candidate_ids[-400:]
        item["last_baseline"] = TODAY
        print(f"{key}: news baseline established with {len(candidate_ids)} relevant links.")
        return item

    seen_set = set(seen)
    new_candidates = [x for x in candidates if x["id"] not in seen_set]
    processed_candidates = new_candidates[:8]

    for candidate in processed_candidates:
        importance, signal_type = classify_signal(candidate["title"], cfg)
        row = {
            "Oppdaget": TODAY,
            "Signal": candidate["title"],
            "Type": signal_type,
            "Viktighet": importance,
            "Kilde": cfg.get("source_label", ""),
            "Lenke": candidate["url"],
        }

        existing_signal_ids = {x.get("id") for x in item.get("signals", [])}
        if candidate["id"] not in existing_signal_ids:
            row["id"] = candidate["id"]
            item.setdefault("signals", []).insert(0, row)

        summary = (
            f"Automatisk oppdaget {signal_type.lower()} i {cfg.get('source_label', 'kilden')}: "
            f"{candidate['title']}. Saken bør vurderes manuelt før den regnes som en potensiell kontrakt."
        )
        add_daily_update(
            updates,
            cfg.get("company", ""),
            candidate["title"],
            summary,
            importance,
        )

    item["signals"] = item.get("signals", [])[:30]
    item["seen_signal_ids"] = (
        seen + [candidate["id"] for candidate in processed_candidates]
    )[-400:]

    if processed_candidates:
        item["last_updated"] = TODAY
        item["last_change_summary"] = (
            f"{len(processed_candidates)} nytt/nye relevant(e) nyhetssignal(er) oppdaget."
        )

    print(f"{key}: completed; {len(processed_candidates)} new signal(s).")
    return item


def main():
    config = load_json(CONFIG_FILE, {})
    monitor = load_json(MONITOR_FILE, {})
    updates = load_json(UPDATES_FILE, [])

    if not config:
        print("contract_news_config.json is empty or missing.")
        return 0

    for key, cfg in config.items():
        monitor[key] = process_news_monitor(key, cfg, monitor.get(key, {}), updates)

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
    print("Contract news signal monitor completed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
