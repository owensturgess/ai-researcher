# tests/unit/test_pipeline_run_metadata.py
import json
import textwrap
from unittest.mock import patch, MagicMock

import boto3
import pytest
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_ingestion_handler_writes_pipeline_run_record_with_source_and_item_counts(
    monkeypatch, tmp_path
):
    """
    After the ingestion handler runs with two active sources (RSS and web),
    a PipelineRun record is written to S3 at pipeline-runs/{date}/run.json
    containing sources_attempted == 2, sources_succeeded == 2,
    items_ingested, transcription_jobs, and delivery_status.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Write a real sources.yaml at the filesystem boundary (not mocking load_sources)
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-rss-1
            name: AI News RSS
            type: rss
            url: https://example.com/feed.xml
            category: ai
            active: true
            priority: 1
          - id: src-web-1
            name: Tech Blog
            type: web
            url: https://example.com/blog
            category: ai
            active: true
            priority: 2
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    # Set up AWS services at the AWS boundary
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    # Mock feedparser.parse at the external library / network boundary (RSS)
    fake_rss_feed = MagicMock()
    fake_rss_feed.bozo = False
    fake_rss_feed.entries = [
        MagicMock(
            title="AI Breakthrough",
            link="https://example.com/article-1",
            published_parsed=(2026, 3, 24, 10, 0, 0, 0, 0, 0),
            summary="An AI breakthrough was announced.",
        ),
        MagicMock(
            title="LLM Update",
            link="https://example.com/article-2",
            published_parsed=(2026, 3, 24, 11, 0, 0, 0, 0, 0),
            summary="A new LLM update was released.",
        ),
    ]

    # Mock urllib.request.urlopen at the network boundary (web page fetching)
    fake_web_html = b"""<html><body>
      <article>
        <h1>Tech Post</h1>
        <time datetime="2026-03-24">March 24, 2026</time>
        <p>AI developments continue.</p>
      </article>
    </body></html>"""
    fake_http_response = MagicMock()
    fake_http_response.read.return_value = fake_web_html
    fake_http_response.__enter__ = lambda s: s
    fake_http_response.__exit__ = MagicMock(return_value=False)

    with (
        patch("feedparser.parse", return_value=fake_rss_feed),
        patch("urllib.request.urlopen", return_value=fake_http_response),
    ):
        handler({}, None)

    # PipelineRun record must be written to S3 with correct metadata fields
    run_key = "pipeline-runs/2026-03-24/run.json"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=run_key)
    run_data = json.loads(response["Body"].read())

    assert run_data["sources_attempted"] == 2
    assert run_data["sources_succeeded"] == 2
    assert "items_ingested" in run_data
    assert "transcription_jobs" in run_data
    assert "delivery_status" in run_data
