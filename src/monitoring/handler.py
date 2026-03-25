# src/monitoring/handler.py
import json
import logging
import os
from datetime import date, datetime, timedelta

import boto3

logger = logging.getLogger(__name__)


def _load_rolling_runs(s3, bucket, run_date_str, days=7):
    """Load up to `days` pipeline run records ending on run_date_str (inclusive)."""
    end = date.fromisoformat(run_date_str)
    runs = []
    for i in range(days):
        d = (end - timedelta(days=days - 1 - i)).isoformat()
        try:
            obj = s3.get_object(Bucket=bucket, Key=f"pipeline-runs/{d}/run.json")
            runs.append(json.loads(obj["Body"].read()))
        except Exception:
            pass
    return runs


def _delivery_latency_minutes(run):
    started = run.get("started_at", "")
    completed = run.get("completed_at", "")
    if not started or not completed:
        return 0.0
    try:
        t0 = datetime.fromisoformat(started)
        t1 = datetime.fromisoformat(completed)
        return (t1 - t0).total_seconds() / 60.0
    except Exception:
        return 0.0


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=f"pipeline-runs/{run_date}/run.json")
    run = json.loads(obj["Body"].read())

    sources_succeeded = run.get("sources_succeeded", 0)
    sources_failed = run.get("sources_failed", 0)
    items_ingested = run.get("items_ingested", 0)
    items_above_threshold = run.get("items_above_threshold", 0)
    items_in_briefing = run.get("items_in_briefing", 0)
    transcription_jobs = run.get("transcription_jobs", 0)
    estimated_cost_usd = run.get("estimated_cost_usd", 0.0)
    delivery_latency = _delivery_latency_minutes(run)

    logger.info(
        "Pipeline run complete: sources_scanned=%s items_ingested=%s "
        "items_above_threshold=%s transcription_jobs=%s estimated_cost_usd=%s",
        sources_succeeded,
        items_ingested,
        items_above_threshold,
        transcription_jobs,
        estimated_cost_usd,
    )

    cloudwatch = boto3.client("cloudwatch")
    cloudwatch.put_metric_data(
        Namespace="AgenticSDLCIntel",
        MetricData=[
            {"MetricName": "SourcesScanned", "Value": sources_succeeded, "Unit": "Count"},
            {"MetricName": "SourcesFailed", "Value": sources_failed, "Unit": "Count"},
            {"MetricName": "ItemsIngested", "Value": items_ingested, "Unit": "Count"},
            {"MetricName": "ItemsAboveThreshold", "Value": items_above_threshold, "Unit": "Count"},
            {"MetricName": "TranscriptionJobs", "Value": transcription_jobs, "Unit": "Count"},
            {"MetricName": "EstimatedCostUSD", "Value": estimated_cost_usd, "Unit": "None"},
            {"MetricName": "DeliveryLatencyMinutes", "Value": delivery_latency, "Unit": "None"},
            {"MetricName": "BriefingItemCount", "Value": items_in_briefing, "Unit": "Count"},
        ],
    )

    rolling_runs = _load_rolling_runs(s3, bucket, run_date)
    if rolling_runs:
        delivered = sum(1 for r in rolling_runs if r.get("delivery_status") == "delivered")
        reliability_pct = delivered / len(rolling_runs) * 100
        avg_cost = sum(r.get("estimated_cost_usd", 0.0) for r in rolling_runs) / len(rolling_runs)
        cloudwatch.put_metric_data(
            Namespace="AgenticSDLCIntel",
            MetricData=[
                {"MetricName": "DeliveryReliabilityPct", "Value": reliability_pct, "Unit": "Percent"},
                {"MetricName": "AverageCostPerRun", "Value": avg_cost, "Unit": "None"},
            ],
        )

    threshold = float(os.environ.get("COST_ALERT_THRESHOLD_USD", "10.00"))
    alert_sent = False
    if estimated_cost_usd > threshold:
        ses = boto3.client("ses")
        ses.send_email(
            Source=os.environ.get("SES_SENDER", ""),
            Destination={"ToAddresses": [os.environ.get("ALERT_RECIPIENT", "")]},
            Message={
                "Subject": {"Data": "AI Researcher: Cost Alert"},
                "Body": {"Text": {"Data": f"Estimated cost ${estimated_cost_usd:.2f} exceeds threshold ${threshold:.2f}"}},
            },
        )
        alert_sent = True

    return {"status": "ok", "alert_sent": alert_sent}
