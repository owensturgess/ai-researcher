# src/monitoring/handler.py
import json
import logging
import os

import boto3

logger = logging.getLogger(__name__)


def handler(event: dict, context: object) -> dict:
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")

    s3 = boto3.client("s3")
    obj = s3.get_object(Bucket=bucket, Key=f"pipeline-runs/{run_date}/run.json")
    run = json.loads(obj["Body"].read())

    sources_succeeded = run.get("sources_succeeded", 0)
    items_ingested = run.get("items_ingested", 0)
    items_above_threshold = run.get("items_above_threshold", 0)
    transcription_jobs = run.get("transcription_jobs", 0)
    estimated_cost_usd = run.get("estimated_cost_usd", 0.0)

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
        Namespace="AiResearcher/Pipeline",
        MetricData=[
            {"MetricName": "SourcesScanned", "Value": sources_succeeded, "Unit": "Count"},
            {"MetricName": "ItemsIngested", "Value": items_ingested, "Unit": "Count"},
            {"MetricName": "ItemsAboveThreshold", "Value": items_above_threshold, "Unit": "Count"},
            {"MetricName": "TranscriptionJobs", "Value": transcription_jobs, "Unit": "Count"},
            {"MetricName": "EstimatedCostUSD", "Value": estimated_cost_usd, "Unit": "None"},
        ],
    )

    threshold = float(os.environ.get("COST_ALERT_THRESHOLD_USD", "10.00"))
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

    return {"status": "ok"}
