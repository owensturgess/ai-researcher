# tests/unit/test_podcast_ingestion.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from src.ingestion.sources.podcast import ingest
from src.shared.models import Source


def test_podcast_ingestion_returns_audio_content_items_for_recent_episodes():
    """
    Given a podcast source and a since datetime, when ingest() is called,
    it returns ContentItem objects with content_format=audio for episodes
    published after `since`, each with source_id, title, published_date,
    and original_url set to the enclosure (audio file) URL.
    """
    source = Source(
        id="podcast-source-1",
        name="AI Podcast",
        type="podcast",
        url="https://example.com/podcast/feed.xml",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    episode_title = "Episode 42: The Future of Agentic AI"
    episode_enclosure_url = "https://example.com/podcast/ep42.mp3"

    mock_entry = MagicMock()
    mock_entry.title = episode_title
    mock_entry.published_parsed = (2026, 3, 24, 9, 0, 0, 0, 0, 0)
    mock_entry.enclosures = [
        MagicMock(href=episode_enclosure_url, type="audio/mpeg")
    ]

    mock_feed = MagicMock()
    mock_feed.bozo = False
    mock_feed.entries = [mock_entry]

    with patch("feedparser.parse", return_value=mock_feed):
        results = ingest(source, since)

    assert len(results) == 1
    item = results[0]
    assert item.source_id == "podcast-source-1"
    assert item.title == episode_title
    assert item.content_format == "audio"
    assert item.original_url == episode_enclosure_url
    assert item.published_date >= since
