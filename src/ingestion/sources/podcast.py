# src/ingestion/sources/podcast.py
from datetime import datetime, timezone

import feedparser

from src.shared.models import ContentItem


def ingest(source, since):
    feed = feedparser.parse(source.url)
    if feed.bozo:
        return []
    items = []
    for entry in feed.entries:
        published_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc)
        if since and published_date < since:
            continue
        enclosures = getattr(entry, "enclosures", [])
        if not enclosures:
            continue
        enclosure_url = enclosures[0].href
        items.append(ContentItem(
            id=enclosure_url,
            title=entry.title,
            source_id=source.id,
            source_name=source.name,
            published_date=published_date,
            full_text="",
            original_url=enclosure_url,
            content_format="audio",
        ))
    return items
