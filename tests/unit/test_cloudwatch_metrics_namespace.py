# tests/unit/test_cloudwatch_metrics_namespace.py
#
# Behavior B035: CloudWatch custom metrics are published to the
# "AgenticSDLCIntel" namespace with dashboard and alarms.
#
# Tests the public interface handler(event, context) in src/monitoring/handler.py.
# All per-run pipeline metrics must be published to "AgenticSDLCIntel" — not an
# alternative namespace — so that the CDK-defined dashboard and alarms can
# reference the same namespace and display / trigger without manual reconfiguration.
#
# This test FAILS (RED) because the handler currently publishes per-run metrics
# to "AiResearcher/Pipeline" rather than "AgenticSDLCIntel", and is missing
# required metric names: sources_failed, delivery_latency_minutes, briefing_item_count.
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.monitoring.handler import handler

REQUIRED_METRICS = {
    "SourcesScanned",
    "SourcesFailed",
    "ItemsIngested",
    "ItemsAboveThreshold",
    "TranscriptionJobs",
    "EstimatedCostUSD",
    "DeliveryLatencyMinutes",
    "BriefingItemCount",
}


@mock_aws
def test_monitoring_handler_publishes_all_per_run_metrics_to_agentic_sdlc_intel_namespace(
    monkeypatch,
):
    """
    Given a completed PipelineRun record in S3 with all standard fields,
    when the monitoring handler runs, it publishes all eight per-run metrics
    (SourcesScanned, SourcesFailed, ItemsIngested, ItemsAboveThreshold,
    TranscriptionJobs, EstimatedCostUSD, DeliveryLatencyMinutes,
    BriefingItemCount) to the CloudWatch namespace "AgenticSDLCIntel" —
    the same namespace referenced by the CDK dashboard and alarms — so that
    operators can monitor pipeline health through the AWS Console without
    namespace mismatch errors.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("COST_ALERT_THRESHOLD_USD", "100.00")
    monkeypatch.setenv("SES_SENDER", "alerts@example.com")
    monkeypatch.setenv("ALERT_RECIPIENT", "admin@example.com")

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

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

    # Collect all metrics published per namespace across all put_metric_data calls
    metrics_by_namespace: dict[str, set] = {}
    for call in mock_cloudwatch.put_metric_data.call_args_list:
        kw = call.kwargs or {}
        namespace = kw.get("Namespace", "")
        metric_data = kw.get("MetricData", [])
        names = {m.get("MetricName", "") for m in metric_data}
        metrics_by_namespace.setdefault(namespace, set()).update(names)

    # All required per-run metrics must be published to "AgenticSDLCIntel"
    published_in_target = metrics_by_namespace.get("AgenticSDLCIntel", set())

    missing = REQUIRED_METRICS - published_in_target
    assert not missing, (
        f"The following metrics were not published to 'AgenticSDLCIntel' namespace: "
        f"{sorted(missing)}. "
        f"Metrics found in 'AgenticSDLCIntel': {sorted(published_in_target)}. "
        f"All namespaces published to: {list(metrics_by_namespace.keys())}. "
        "All per-run metrics must use 'AgenticSDLCIntel' so the CDK-defined "
        "dashboard and alarms can reference them without namespace mismatch."
    )
