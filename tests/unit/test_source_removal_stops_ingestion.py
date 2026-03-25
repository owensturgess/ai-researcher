# tests/unit/test_source_removal_stops_ingestion.py
#
# Behavior B024: Given a source is removed from the configuration file,
# content from that source is no longer ingested on the next run.
#
# This test verifies that the pipeline run record written to S3 contains an
# explicit list of source IDs that were attempted (source_ids_attempted), and
# that the removed source's ID is absent from that list while the remaining
# source's ID is present.  The handler currently writes only counts
# (sources_attempted, sources_succeeded) — not an ID list — so this test fails
# until source_ids_attempted is added to the run record.
import json
import textwrap
from unittest.mock import patch, MagicMock

import boto3
from moto import mock_aws

from src.ingestion.handler import handler


@mock_aws
def test_removed_source_id_is_absent_from_run_record_source_id_list(
    monkeypatch, tmp_path
):
    """
    Given a config file that contains only src-remaining-001 (src-removed-002
    was previously active but has been removed from the YAML), when the
    ingestion handler runs, the pipeline run record written to S3 includes a
    source_ids_attempted list that contains src-remaining-001 and does NOT
    contain src-removed-002 — giving operators an explicit record of which
    sources participated in each run.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv(
        "TRANSCRIPTION_QUEUE_URL",
        "https://sqs.us-east-1.amazonaws.com/123456789012/test-transcription-queue",
    )
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Config after removal: only src-remaining-001 is present
    sources_yaml = textwrap.dedent("""\
        sources:
          - id: src-remaining-001
            name: Remaining AI Feed
            type: rss
            url: https://remaining.example.com/feed.xml
            category: ai
            active: true
            priority: 1
    """)
    config_file = tmp_path / "sources.yaml"
    config_file.write_text(sources_yaml)
    monkeypatch.setenv("SOURCES_CONFIG", str(config_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")
    sqs = boto3.client("sqs", region_name="us-east-1")
    sqs.create_queue(QueueName="test-transcription-queue")

    fake_feed = MagicMock()
    fake_feed.bozo = False
    fake_feed.entries = []

    with patch("feedparser.parse", return_value=fake_feed):
        handler({}, None)

    # Read the pipeline run record written to S3
    response = s3.get_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
    )
    run_data = json.loads(response["Body"].read())

    # The run record must include an explicit list of source IDs attempted
    assert "source_ids_attempted" in run_data, (
        "pipeline run record missing 'source_ids_attempted' field — "
        "operators cannot verify which sources ran vs. which were removed"
    )

    source_ids = run_data["source_ids_attempted"]
    assert "src-remaining-001" in source_ids, (
        f"src-remaining-001 should be in source_ids_attempted but got: {source_ids}"
    )
    assert "src-removed-002" not in source_ids, (
        f"src-removed-002 must not appear in source_ids_attempted after removal, got: {source_ids}"
    )
