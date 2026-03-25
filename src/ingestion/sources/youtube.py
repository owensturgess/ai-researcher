# src/ingestion/sources/youtube.py
import logging
from datetime import datetime, timezone

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from src.shared.models import ContentItem

logger = logging.getLogger(__name__)


def ingest(source, since):
    channel_id = source.url.rstrip("/").split("/")[-1]
    youtube = build("youtube", "v3", developerKey=None)
    items = []
    page_token = None

    while True:
        kwargs = dict(
            part="snippet",
            channelId=channel_id,
            publishedAfter=since.isoformat() if since else None,
            type="video",
            maxResults=50,
        )
        if page_token:
            kwargs["pageToken"] = page_token

        try:
            response = youtube.search().list(**kwargs).execute()
        except HttpError as e:
            if e.resp.status == 403:
                logger.warning(
                    "YouTube quota exceeded for source %s; returning partial results", source.id
                )
                break
            raise

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

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return items
