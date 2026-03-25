# tests/unit/test_x_api_rate_limit_mid_ingestion.py
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import tweepy

from src.ingestion.sources.x_api import ingest
from src.shared.models import Source


def test_x_api_rate_limit_mid_ingestion_returns_partial_results_and_logs_event(caplog):
    """
    Given an X source being ingested across multiple pages, when the X API
    raises TooManyRequests on the second page (rate limit hit mid-ingestion),
    ingest() returns the ContentItems already retrieved from the first page
    and emits a warning log containing "rate limit".
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

    # First page: one tweet retrieved successfully, meta indicates more pages exist
    mock_tweet = MagicMock()
    mock_tweet.id = "tweet-page1-001"
    mock_tweet.text = "First page tweet about AI developments"
    mock_tweet.created_at = datetime(2026, 3, 24, 9, 0, 0, tzinfo=timezone.utc)

    first_page_meta = MagicMock()
    first_page_meta.next_token = "page2_token"

    first_page_response = MagicMock()
    first_page_response.data = [mock_tweet]
    first_page_response.meta = first_page_meta

    # Construct a tweepy TooManyRequests exception for the second page
    mock_rate_limit_response = MagicMock()
    mock_rate_limit_response.status_code = 429
    mock_rate_limit_response.headers = {}
    mock_rate_limit_response.json.return_value = {}
    mock_rate_limit_response.text = "Too Many Requests"

    call_count = 0

    def search_side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return first_page_response
        raise tweepy.errors.TooManyRequests(mock_rate_limit_response)

    mock_client = MagicMock()
    mock_client.search_recent_tweets.side_effect = search_side_effect

    with patch("src.ingestion.sources.x_api.tweepy.Client", return_value=mock_client):
        with caplog.at_level(logging.WARNING):
            results = ingest(source, since)

    # Items from the first page must be returned despite the rate limit
    assert len(results) == 1
    assert results[0].source_id == "x-source-1"

    # A rate-limit-specific warning must be logged
    rate_limit_logs = [r for r in caplog.records if "rate limit" in r.message.lower()]
    assert len(rate_limit_logs) >= 1
