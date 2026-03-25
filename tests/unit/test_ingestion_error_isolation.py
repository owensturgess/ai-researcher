# tests/unit/test_ingestion_error_isolation.py
import textwrap
from urllib.error import HTTPError
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_failing_source_is_skipped_and_other_sources_process_normally(
    monkeypatch, tmp_path
):
    """
    Given two RSS sources where one raises an HTTP 429 (rate limit) during
    ingestion, when the handler runs, the failing source is skipped and the
    other source's items are ingested normally — sources_attempted == 2 and
    sources_succeeded == 1 in the returned counts.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-rss-failing
            name: Failing Feed
            type: rss
            url: https://failing.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-rss-ok
            name: Healthy Feed
            type: rss
            url: https://healthy.example.com/feed.xml
            category: ai
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    # Healthy feed returns one recent entry
    fake_healthy_feed = MagicMock()
    fake_healthy_feed.bozo = False
    fake_healthy_feed.entries = [
        MagicMock(
            title="AI Update from Healthy Source",
            link="https://healthy.example.com/article-1",
            published_parsed=(2026, 3, 24, 10, 0, 0, 0, 0, 0),
            summary="A healthy AI update.",
        )
    ]

    # feedparser.parse raises HTTPError for the failing source URL
    def parse_side_effect(url, *args, **kwargs):
        if "failing" in url:
            raise HTTPError(url, 429, "Too Many Requests", {}, None)
        return fake_healthy_feed

    with patch("feedparser.parse", side_effect=parse_side_effect):
        result = handler({}, None)

    # Both sources were attempted; only the healthy one succeeded
    assert result["sources_attempted"] == 2
    assert result["sources_succeeded"] == 1

    # Items from the healthy source were written to S3 despite the other failure
    objects = s3.list_objects_v2(
        Bucket="test-pipeline-bucket", Prefix="raw/2026-03-24/src-rss-ok/"
    )
    assert objects.get("KeyCount", 0) >= 1
