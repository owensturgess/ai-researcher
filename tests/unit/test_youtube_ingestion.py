# tests/unit/test_youtube_ingestion.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.ingestion.sources.youtube import ingest
from src.shared.models import Source


def test_youtube_ingestion_returns_video_content_items_for_recent_videos():
    """
    Given a YouTube source and a since datetime, when ingest() is called,
    it returns ContentItem objects with content_format=video for videos
    published after `since`, each with source_id, title, published_date,
    and original_url populated from the YouTube API response.
    """
    source = Source(
        id="yt-source-1",
        name="AI Channel",
        type="youtube",
        url="https://www.youtube.com/channel/UC_test_channel_id",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    video_id = "dQw4w9WgXcQ"
    video_title = "Latest AI Developments Explained"
    published_at = "2026-03-24T10:00:00Z"

    mock_search_response = {
        "items": [
            {
                "id": {"videoId": video_id},
                "snippet": {
                    "title": video_title,
                    "publishedAt": published_at,
                    "channelTitle": "AI Channel",
                },
            }
        ]
    }

    mock_list_request = MagicMock()
    mock_list_request.execute.return_value = mock_search_response

    mock_search = MagicMock()
    mock_search.list.return_value = mock_list_request

    mock_youtube_client = MagicMock()
    mock_youtube_client.search.return_value = mock_search

    with patch(
        "src.ingestion.sources.youtube.build",
        return_value=mock_youtube_client,
    ):
        results = ingest(source, since)

    assert len(results) == 1
    item = results[0]
    assert item.source_id == "yt-source-1"
    assert item.title == video_title
    assert item.content_format == "video"
    assert video_id in item.original_url
    assert item.published_date == datetime(2026, 3, 24, 10, 0, 0, tzinfo=timezone.utc)
