# tests/unit/test_delivery_reliability_metrics.py
#
# Behavior B033: After 7 consecutive days, an operator can see delivery reliability
# (% on-time) and average cost per run.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# After 7 pipeline run records exist in S3, the monitoring handler must publish
# DeliveryReliabilityPct and AverageCostPerRun metrics to CloudWatch namespace
# "AgenticSDLCIntel" so operators have a 7-day rolling view without querying S3.
import json
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler


@mock_aws
def test_after_seven_days_monitoring_handler_publishes_delivery_reliability_and_average_cost(
    monkeypatch,
):
    """
    Given 7 consecutive pipeline run records in S3 (6 with delivery_status='delivered'
    and 1 with delivery_status='failed'), when the monitoring handler runs on day 7,
    CloudWatch put_metric_data is called with 'DeliveryReliabilityPct' (~85.7%) and
    'AverageCostPerRun' metrics in the 'AgenticSDLCIntel' namespace — giving operators
    a 7-day rolling view of pipeline reliability and cost without consulting S3 directly.

    This test FAILS (RED) because the monitoring handler currently only publishes
    per-run metrics for the current day — it does not aggregate across 7 days to
    compute rolling delivery reliability or average cost per run.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "100.00")  # high so no alert fires
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Write 7 consecutive pipeline run records to S3.
    # 6 delivered on-time, 1 failed → reliability = 6/7 ≈ 85.71%
    # Costs: 2.00, 2.50, 3.00, 3.50, 4.00, 4.50, 5.00 → avg = 3.50
    base_date = date(2026, 3, 18)  # 7 days ending on RUN_DATE 2026-03-24
    for i in range(7):
        run_date = (base_date + timedelta(days=i)).isoformat()
        cost = 2.0 + i * 0.5
        delivery_status = "failed" if i == 3 else "delivered"
        pipeline_run = {
            "run_date": run_date,
            "started_at": f"{run_date}T06:00:00+00:00",
            "completed_at": f"{run_date}T07:30:00+00:00",
            "sources_attempted": 12,
            "sources_succeeded": 12,
            "sources_failed": 0,
            "items_ingested": 50,
            "items_scored": 50,
            "items_above_threshold": 8,
            "items_in_briefing": 8,
            "transcription_jobs": 3,
            "estimated_cost_usd": cost,
            "delivery_status": delivery_status,
        }
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"pipeline-runs/{run_date}/run.json",
            Body=json.dumps(pipeline_run),
        )

    mock_cloudwatch = MagicMock()
    mock_cloudwatch.put_metric_data.return_value = {}
    mock_ses = MagicMock()

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service == "cloudwatch":
            return mock_cloudwatch
        if service == "ses":
            return mock_ses
        return moto_boto3_client(service, **kw)

    with patch("src.monitoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    assert result["status"] == "ok"

    # Collect all metric names published to the AgenticSDLCIntel namespace
    published_metrics = {}
    for call_args in mock_cloudwatch.put_metric_data.call_args_list:
        kwargs = call_args.kwargs or {}
        positional = call_args.args or ()
        namespace = kwargs.get("Namespace") or (positional[0] if positional else "")
        metric_data = kwargs.get("MetricData") or (positional[1] if len(positional) > 1 else [])
        if "AgenticSDLCIntel" in str(namespace):
            for metric in metric_data:
                name = metric.get("MetricName", "")
                published_metrics[name] = metric.get("Value")

    # --- Assertion 1: delivery reliability metric must be published ---
    reliability_metric = next(
        (name for name in published_metrics if "reliability" in name.lower()),
        None,
    )
    assert reliability_metric is not None, (
        f"No delivery reliability metric found in CloudWatch 'AgenticSDLCIntel' namespace. "
        f"Published metrics: {list(published_metrics.keys())}. "
        "After 7 consecutive days the monitoring handler must publish a "
        "'DeliveryReliabilityPct' (or similar) metric so operators can track "
        "the % of on-time deliveries over the rolling 7-day window."
    )

    # Value must be close to 85.71% (6 delivered / 7 total × 100)
    reliability_value = published_metrics[reliability_metric]
    assert abs(reliability_value - (6 / 7 * 100)) < 1.0, (
        f"DeliveryReliabilityPct should be ~85.71% (6/7 runs delivered), "
        f"got {reliability_value:.2f}%."
    )

    # --- Assertion 2: average cost per run metric must be published ---
    avg_cost_metric = next(
        (
            name for name in published_metrics
            if "average" in name.lower() and "cost" in name.lower()
        ),
        None,
    )
    assert avg_cost_metric is not None, (
        f"No average cost per run metric found in CloudWatch 'AgenticSDLCIntel' namespace. "
        f"Published metrics: {list(published_metrics.keys())}. "
        "After 7 consecutive days the monitoring handler must publish an "
        "'AverageCostPerRun' (or similar) metric so operators can track "
        "the rolling 7-day average pipeline cost."
    )

    # Value must be close to $3.50 (sum of 2.00..5.00 / 7)
    avg_cost_value = published_metrics[avg_cost_metric]
    assert abs(avg_cost_value - 3.50) < 0.01, (
        f"AverageCostPerRun should be $3.50 (avg of 7 runs), got ${avg_cost_value:.2f}."
    )
