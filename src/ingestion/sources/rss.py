# src/ingestion/sources/rss.py
import feedparser


def ingest(source, since):
    feed = feedparser.parse(source.url)
    if feed.bozo:
        return []
    return [
        {
            "title": getattr(entry, "title", ""),
            "url": getattr(entry, "link", ""),
            "summary": getattr(entry, "summary", ""),
            "source_id": source.id,
        }
        for entry in feed.entries
    ]
