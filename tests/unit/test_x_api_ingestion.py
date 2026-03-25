# tests/unit/test_x_api_ingestion.py
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.ingestion.sources.x_api import ingest
from src.shared.models import Source


def test_x_api_ingestion_returns_content_items_for_recent_tweets():
    """
    Given an X source and a since datetime, when ingest() is called,
    it returns ContentItem objects for tweets published after `since`,
    each with source_id, title, published_date, original_url, and full_text
    populated from the tweet data.
    """
    source = Source(
        id="x-source-1",
        name="Test X Account",
        type="x",
        url="https://twitter.com/testaccount",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    tweet_id = "1234567890"
    tweet_text = "Exciting AI development announced today! #AI"
    tweet_created_at = datetime(2026, 3, 24, 9, 0, 0, tzinfo=timezone.utc)

    mock_tweet = MagicMock()
    mock_tweet.id = tweet_id
    mock_tweet.text = tweet_text
    mock_tweet.created_at = tweet_created_at

    mock_response = MagicMock()
    mock_response.data = [mock_tweet]

    mock_client_instance = MagicMock()
    mock_client_instance.search_recent_tweets.return_value = mock_response

    with patch("src.ingestion.sources.x_api.tweepy.Client", return_value=mock_client_instance):
        results = ingest(source, since)

    assert len(results) == 1
    item = results[0]
    assert item.source_id == "x-source-1"
    assert tweet_text in item.title or tweet_text in item.full_text
    assert item.published_date == tweet_created_at
    assert tweet_id in item.original_url
