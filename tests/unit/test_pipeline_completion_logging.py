# tests/unit/test_pipeline_completion_logging.py
#
# Behavior B031: When the daily pipeline completes, logs show: sources scanned,
# items ingested, items scored above threshold, transcription jobs run, and
# total estimated cost.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# After a completed pipeline run record exists in S3, the monitoring handler must
# emit a log entry containing all five required pipeline completion metrics.
import json
import logging
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler


@mock_aws
def test_pipeline_completion_logs_sources_items_scored_transcriptions_and_cost(
    monkeypatch, caplog
):
    """
    Given a completed PipelineRun record in S3 with known metrics (11 sources
    scanned, 47 items ingested, 8 items above threshold, 3 transcription jobs,
    $2.47 estimated cost), when the monitoring handler runs, the log output
    contains all five values — confirming operators can verify pipeline health
    from logs alone without consulting the S3 run record directly.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "10.00")
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Write a completed PipelineRun record to S3 with known metric values
    pipeline_run = {
        "run_date": "2026-03-24",
        "started_at": "2026-03-24T06:00:00+00:00",
        "completed_at": "2026-03-24T07:30:00+00:00",
        "sources_attempted": 12,
        "sources_succeeded": 11,
        "sources_failed": 1,
        "items_ingested": 47,
        "items_scored": 47,
        "items_above_threshold": 8,
        "items_in_briefing": 8,
        "transcription_jobs": 3,
        "estimated_cost_usd": 2.47,
        "delivery_status": "delivered",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
        Body=json.dumps(pipeline_run),
    )

    # Mock CloudWatch at the AWS service boundary — cost is below threshold
    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}

    # Mock SES at the AWS service boundary — no alert expected (cost < threshold)
    mock_ses = MagicMock()

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        with caplog.at_level(logging.INFO):
            result = handler({}, None)

    assert result["status"] == "ok"

    # Collect all log text for inspection
    all_log_messages = " ".join(r.message for r in caplog.records)

    # 1. Sources scanned (sources_succeeded=11)
    assert "11" in all_log_messages, (
        f"Logs must include sources scanned count (11). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 2. Items ingested (items_ingested=47)
    assert "47" in all_log_messages, (
        f"Logs must include items ingested count (47). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 3. Items scored above threshold (items_above_threshold=8)
    assert "8" in all_log_messages, (
        f"Logs must include items above threshold count (8). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 4. Transcription jobs run (transcription_jobs=3)
    assert "3" in all_log_messages, (
        f"Logs must include transcription jobs count (3). "
        f"Got log messages: {all_log_messages!r}"
    )

    # 5. Total estimated cost ($2.47)
    assert "2.47" in all_log_messages, (
        f"Logs must include estimated cost (2.47). "
        f"Got log messages: {all_log_messages!r}"
    )
