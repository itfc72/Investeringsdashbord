from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.name == "scripts":
    ROOT = ROOT.parent

monitor_path = ROOT / "data" / "contract_monitor.json"

with monitor_path.open("r", encoding="utf-8") as f:
    monitor = json.load(f)

if "netheridge_thp" not in monitor:
    monitor["netheridge_thp"] = {
        "company": "Cambi",
        "title": "Netheridge STW THP – Severn Trent",
        "opportunity_match": "Netheridge STW THP",
        "monitor_type": "netheridge_tender",
        "source_label": "Find a Tender 2025/S 000-022304 / Sell2Wales – ocds-h6vhtk-051607",
        "source_urls": [
            "https://www.find-tender.service.gov.uk/Notice/022304-2025",
            "https://www.sell2wales.gov.wales/search/show/search_view.aspx?ID=MAY514386&catID="
        ],
        "status": "Preliminary market engagement / avventer tender",
        "next_date": "Ikke offentlig",
        "date_type": "Neste procurement-steg",
        "last_checked": "16.09.2026",
        "last_updated": "16.09.2026",
        "content_hash": None,
        "last_change_summary": (
            "Severn Trent gjennomførte preliminary market engagement for et THP-system ved "
            "Netheridge STW. Scope omfatter supply, delivery, installation/support, commissioning, "
            "operator training og maintenance. Levering var planlagt tidlig 2027, installasjon "
            "innen midten av 2027 og commissioning innen utgangen av 2027. "
            "Neste relevante trigger er UK4 tender notice, UK6 award eller leverandørvalg."
        )
    }

with monitor_path.open("w", encoding="utf-8") as f:
    json.dump(monitor, f, ensure_ascii=False, indent=2)

print("Netheridge monitor added safely to data/contract_monitor.json")
