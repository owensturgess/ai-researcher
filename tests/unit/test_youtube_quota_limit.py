# tests/unit/test_youtube_quota_limit.py
import json
import logging
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from googleapiclient.errors import HttpError

from src.ingestion.sources.youtube import ingest
from src.shared.models import Source


def test_youtube_quota_exceeded_stops_queries_and_returns_partial_results(caplog):
    """
    Given a YouTube source where the first API page succeeds but a subsequent
    query raises an HttpError with status 403 (quotaExceeded), when ingest()
    is called, it returns the ContentItems already retrieved and does not raise
    an exception — the caller (pipeline) can continue with other source types.
    """
    source = Source(
        id="yt-source-quota",
        name="AI Channel",
        type="youtube",
        url="https://www.youtube.com/channel/UC_quota_test_channel",
        category="ai",
        active=True,
        priority=1,
    )
    since = datetime(2026, 3, 23, 0, 0, 0, tzinfo=timezone.utc)

    # First page returns one video successfully
    first_page_response = {
        "items": [
            {
                "id": {"videoId": "video-before-quota"},
                "snippet": {
                    "title": "Video Retrieved Before Quota Hit",
                    "publishedAt": "2026-03-24T08:00:00Z",
                    "channelTitle": "AI Channel",
                },
            }
        ],
        "nextPageToken": "page2token",
    }

    # Second page raises quota exceeded error (403 quotaExceeded)
    quota_error_content = json.dumps({
        "error": {
            "code": 403,
            "errors": [{"reason": "quotaExceeded", "domain": "youtube.quota"}],
            "message": "The request cannot be completed because you have exceeded your quota.",
        }
    }).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.status = 403
    quota_error = HttpError(resp=mock_resp, content=quota_error_content)

    call_count = 0

    def execute_side_effect():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return first_page_response
        raise quota_error

    mock_list_request = MagicMock()
    mock_list_request.execute.side_effect = execute_side_effect

    mock_search = MagicMock()
    mock_search.list.return_value = mock_list_request

    mock_youtube_client = MagicMock()
    mock_youtube_client.search.return_value = mock_search

    with patch("src.ingestion.sources.youtube.build", return_value=mock_youtube_client):
        with caplog.at_level(logging.WARNING):
            results = ingest(source, since)

    # Must return items collected before quota was hit — not raise or return nothing
    assert isinstance(results, list)
    assert len(results) >= 1
    assert results[0].source_id == "yt-source-quota"
    assert results[0].content_format == "video"

    # Must log a quota-related warning so the operator knows queries stopped early
    quota_logs = [
        r for r in caplog.records
        if "quota" in r.message.lower()
    ]
    assert len(quota_logs) >= 1
