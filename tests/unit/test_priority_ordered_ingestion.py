# tests/unit/test_priority_ordered_ingestion.py
import textwrap
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_sources_ingested_in_priority_order_regardless_of_yaml_declaration_order(
    monkeypatch, tmp_path
):
    """
    Given three RSS sources declared in YAML with priorities 3, 1, 2 (non-sorted),
    when the handler runs, it invokes each source ingestion in ascending priority
    order (priority 1 first, then 2, then 3) — ensuring highest-value sources
    are processed first when rate limits may constrain total volume.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Sources declared in non-priority order: 3, 1, 2
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-priority-3
            name: Low Priority Feed
            type: rss
            url: https://low-priority.example.com/feed.xml
            category: ai
            active: true
            priority: 3
          - id: src-priority-1
            name: High Priority Feed
            type: rss
            url: https://high-priority.example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-priority-2
            name: Medium Priority Feed
            type: rss
            url: https://medium-priority.example.com/feed.xml
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

    # Track the URL order that feedparser.parse is called with
    call_order = []

    def parse_side_effect(url, *args, **kwargs):
        call_order.append(url)
        feed = MagicMock()
        feed.bozo = False
        feed.entries = []
        return feed

    with patch("feedparser.parse", side_effect=parse_side_effect):
        handler({}, None)

    # All three sources must be attempted
    assert len(call_order) == 3

    # Priority=1 (high-priority) must be ingested first
    assert "high-priority" in call_order[0], (
        f"Expected priority=1 source first, got: {call_order}"
    )
    # Priority=2 (medium-priority) must be ingested second
    assert "medium-priority" in call_order[1], (
        f"Expected priority=2 source second, got: {call_order}"
    )
    # Priority=3 (low-priority) must be ingested last
    assert "low-priority" in call_order[2], (
        f"Expected priority=3 source last, got: {call_order}"
    )
