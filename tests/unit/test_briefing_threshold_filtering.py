# tests/unit/test_briefing_threshold_filtering.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.briefing.handler import handler


@mock_aws
def test_only_items_above_relevance_threshold_appear_in_final_briefing(
    monkeypatch, tmp_path
):
    """
    Given the relevance threshold is set to 60 (default) and scored items in S3
    where one item has score 75 (above threshold) and one has score 40 (below
    threshold), when the briefing handler runs, only the item scoring above 60
    appears in the briefing — items_included == 1.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "60")
    monkeypatch.setenv("SES_SENDER", "briefing@example.com")
    monkeypatch.setenv("RECIPIENTS", "user@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Item above threshold (score 75) — should appear in briefing
    item_above = {
        "id": "item-above",
        "title": "Claude 4 Released with Agentic Capabilities",
        "source_id": "src-rss-1",
        "source_name": "AI News",
        "published_date": "2026-03-24T08:00:00+00:00",
        "full_text": "Anthropic released Claude 4.",
        "original_url": "https://example.com/claude-4",
        "content_format": "text",
        "transcript_status": "not_needed",
        "relevance_score": 75,
        "urgency": "worth_discussing",
        "relevance_tag": "AI Tools",
        "executive_summary": "Major agentic AI release.",
        "scoring_reasoning": "Highly relevant to agentic SDLC goals.",
        "is_duplicate": False,
        "duplicate_of": None,
    }

    # Item below threshold (score 40) — must NOT appear in briefing
    item_below = {
        "id": "item-below",
        "title": "Local Weather Forecast for March",
        "source_id": "src-rss-2",
        "source_name": "Weather Feed",
        "published_date": "2026-03-24T07:00:00+00:00",
        "full_text": "Expect sunny skies.",
        "original_url": "https://example.com/weather",
        "content_format": "text",
        "transcript_status": "not_needed",
        "relevance_score": 40,
        "urgency": "informational",
        "relevance_tag": "Other",
        "executive_summary": "Local weather update.",
        "scoring_reasoning": "Not relevant to agentic SDLC goals.",
        "is_duplicate": False,
        "duplicate_of": None,
    }

    for item in [item_above, item_below]:
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"scored/2026-03-24/{item['id']}.json",
            Body=json.dumps(item),
        )

    # Mock SES at the AWS service boundary — we only care about item filtering
    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "msg-001"}

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.briefing.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    # Only the item above the 60-point threshold must appear in the briefing
    assert result["items_included"] == 1
