from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.name == "scripts":
    ROOT = ROOT.parent

DATA_DIR = ROOT / "data"
MONITOR_FILE = DATA_DIR / "contract_monitor.json"
CONFIG_FILE = DATA_DIR / "contract_monitor_config.json"

STATIC_KEYS = (
    "company",
    "title",
    "opportunity_match",
    "monitor_type",
    "source_label",
    "source_urls",
)

with MONITOR_FILE.open("r", encoding="utf-8") as f:
    monitor = json.load(f)

existing_config = {}
if CONFIG_FILE.exists():
    with CONFIG_FILE.open("r", encoding="utf-8") as f:
        existing_config = json.load(f)

config = dict(existing_config)

for key, item in monitor.items():
    cfg = dict(config.get(key, {}))

    for static_key in STATIC_KEYS:
        if static_key in item:
            cfg[static_key] = item[static_key]

    # Capture current verified values as initial defaults for a fresh state file.
    if item.get("status") is not None:
        cfg["initial_status"] = item.get("status")
    if item.get("next_date") is not None:
        cfg["initial_next_date"] = item.get("next_date")
    if item.get("date_type") is not None:
        cfg["initial_date_type"] = item.get("date_type")
    if item.get("last_updated") is not None:
        cfg["initial_last_updated"] = item.get("last_updated")
    if item.get("last_change_summary") is not None:
        cfg["initial_last_change_summary"] = item.get("last_change_summary")

    config[key] = cfg

with CONFIG_FILE.open("w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print(f"Created/updated {CONFIG_FILE.relative_to(ROOT)} with {len(config)} monitor definitions.")
print("contract_monitor.json was not modified.")
