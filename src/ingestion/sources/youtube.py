# src/ingestion/sources/youtube.py
from datetime import datetime, timezone

from googleapiclient.discovery import build

from src.shared.models import ContentItem


def ingest(source, since):
    channel_id = source.url.rstrip("/").split("/")[-1]
    youtube = build("youtube", "v3", developerKey=None)
    request = youtube.search().list(
        part="snippet",
        channelId=channel_id,
        publishedAfter=since.isoformat() if since else None,
        type="video",
        maxResults=50,
    )
    response = request.execute()
    items = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        snippet = item["snippet"]
        published_at = snippet["publishedAt"]
        published_date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        items.append(ContentItem(
            id=video_id,
            title=snippet["title"],
            source_id=source.id,
            source_name=source.name,
            published_date=published_date,
            full_text="",
            original_url=f"https://www.youtube.com/watch?v={video_id}",
            content_format="video",
        ))
    return items
