# src/ingestion/handler.py
import json
import os

import boto3
import yaml

from src.ingestion.sources import rss, web


def load_sources():
    config_path = os.environ.get("SOURCES_CONFIG", "config/sources.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    return [s for s in config.get("sources", []) if s.get("active", True)]


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    s3 = boto3.client("s3")

    sources = load_sources()
    sources_attempted = len(sources)
    sources_succeeded = 0
    all_items = []

    ingesters = {"rss": rss.ingest, "web": web.ingest}

    for source in sources:
        source_type = source.get("type")
        ingest_fn = ingesters.get(source_type)
        if ingest_fn is None:
            continue
        try:
            items = ingest_fn(source, since=None)
            all_items.extend(items)
            sources_succeeded += 1
        except Exception:
            pass

    run_record = {
        "sources_attempted": sources_attempted,
        "sources_succeeded": sources_succeeded,
        "items_ingested": len(all_items),
        "transcription_jobs": 0,
        "delivery_status": "pending",
    }

    s3.put_object(
        Bucket=bucket,
        Key=f"pipeline-runs/{run_date}/run.json",
        Body=json.dumps(run_record),
        ContentType="application/json",
    )

    return run_record
