# src/ingestion/config.py
import yaml

from src.shared.models import Source


def load_sources(config_path):
    with open(config_path) as f:
        config = yaml.safe_load(f)
    raw = config.get("sources", [])
    seen = set()
    for s in raw:
        if s["id"] in seen:
            raise ValueError(f"duplicate source id: {s['id']}")
        seen.add(s["id"])
    return [
        Source(
            id=s["id"],
            name=s["name"],
            type=s["type"],
            url=s["url"],
            category=s.get("category", ""),
            active=s.get("active", True),
            priority=s.get("priority", 1),
        )
        for s in raw
        if s.get("active", True)
    ]
