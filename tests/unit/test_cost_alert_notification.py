# tests/unit/test_cost_alert_notification.py
#
# Behavior B032: When daily costs exceed a configurable threshold, a cost alert
# notification is sent to configured recipients.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# When estimated_cost_usd in the PipelineRun record exceeds COST_ALERT_THRESHOLD_USD,
# the handler must send a cost alert email via SES and return alert_sent=True.
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler


@mock_aws
def test_cost_alert_sent_to_recipients_when_daily_cost_exceeds_threshold(
    monkeypatch,
):
    """
    Given a completed PipelineRun record with estimated_cost_usd=18.75 and a
    cost alert threshold of $10.00, when the monitoring handler runs, it sends
    a cost alert email via SES to the configured alert recipient and returns
    alert_sent=True — notifying operators that the daily budget was exceeded.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "10.00")
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Pipeline run with cost ($18.75) exceeding the threshold ($10.00)
    pipeline_run = {
        "run_date": "2026-03-24",
        "started_at": "2026-03-24T06:00:00+00:00",
        "completed_at": "2026-03-24T07:30:00+00:00",
        "sources_attempted": 12,
        "sources_succeeded": 12,
        "sources_failed": 0,
        "items_ingested": 120,
        "items_scored": 120,
        "items_above_threshold": 10,
        "items_in_briefing": 10,
        "transcription_jobs": 15,
        "estimated_cost_usd": 18.75,
        "delivery_status": "delivered",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key="pipeline-runs/2026-03-24/run.json",
        Body=json.dumps(pipeline_run),
    )

    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}

    mock_ses = MagicMock()
    mock_ses.send_email.return_value = {"MessageId": "alert-msg-001"}

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    # Handler must report that an alert was sent
    assert result.get("alert_sent") is True, (
        f"Expected alert_sent=True when cost $18.75 exceeds threshold $10.00, "
        f"got: {result.get('alert_sent')!r}"
    )

    # SES send_email must have been called at least once (the cost alert)
    assert mock_ses.send_email.called, (
        "SES send_email was never called — cost alert was not sent despite "
        "estimated_cost_usd ($18.75) exceeding COST_ALERT_THRESHOLD_USD ($10.00)."
    )

    # The alert must be addressed to the configured recipient
    call_kwargs = mock_ses.send_email.call_args
    # Support both positional and keyword argument styles
    call_args_flat = str(call_kwargs)
    assert "admin@example.com" in call_args_flat, (
        f"Cost alert email must be sent to ALERT_RECIPIENT 'admin@example.com'. "
        f"SES call args: {call_kwargs}"
    )
