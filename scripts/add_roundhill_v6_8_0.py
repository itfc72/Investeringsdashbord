from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if ROOT.name == "scripts":
    ROOT = ROOT.parent

CONFIG_FILE = ROOT / "data" / "contract_monitor_config.json"

with CONFIG_FILE.open("r", encoding="utf-8") as f:
    config = json.load(f)

if "roundhill_thp" not in config:
    config["roundhill_thp"] = {
        "company": "Cambi",
        "title": "Roundhill STW THP – Severn Trent",
        "opportunity_match": "Roundhill STW THP",
        "monitor_type": "roundhill_pipeline",
        "source_label": "Severn Trent PR24 / Environment Agency",
        "source_urls": [
            "https://www.stwater.co.uk/content/dam/stw/about_us/pr24-response/totex/sve4-34-bioresources-botex-plus-cost-assessment.pdf",
            "https://www.severntrent.com/sustainability/bioresources/treatment/",
            "https://www.gov.uk/government/publications/dy7-6px-severn-trent-water-limited-environmental-issued-eprkb3701fka001"
        ],
        "initial_status": "Planlagt AMP8 THP-anlegg / overvåkes",
        "initial_next_date": "Ikke offentlig",
        "initial_date_type": "Neste procurement-steg",
        "initial_last_updated": "16.09.2026",
        "initial_last_change_summary": (
            "Severn Trent opplyser i PR24-materialet at AMP8-planen inkluderer to nye THP-anlegg "
            "ved Netheridge og Roundhill, samt utvidelser ved Wanlip og Derby. "
            "Roundhill har et gjeldende miljøtillatelsesgrunnlag for sludge treatment, men ingen "
            "offentlig UK4 tender eller UK6 award for det nye THP-anlegget er identifisert."
        )
    }

with CONFIG_FILE.open("w", encoding="utf-8") as f:
    json.dump(config, f, ensure_ascii=False, indent=2)

print("Roundhill monitor added safely to data/contract_monitor_config.json")
