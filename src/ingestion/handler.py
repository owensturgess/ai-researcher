# src/ingestion/handler.py
import json
import logging
import os

import boto3
import yaml

from src.ingestion.sources import rss, web, x_api

logger = logging.getLogger(__name__)

_INGESTERS = {"rss": rss.ingest, "web": web.ingest, "x": x_api.ingest}


def load_sources():
    config_path = os.environ.get("SOURCES_CONFIG", "config/sources.yaml")
    with open(config_path) as f:
        config = yaml.safe_load(f)
    sources = [s for s in config.get("sources", []) if s.get("active", True)]
    return sorted(sources, key=lambda s: s.get("priority", 1))


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    s3 = boto3.client("s3")

    sources = load_sources()
    sources_attempted = len(sources)
    sources_succeeded = 0
    all_items = []

    for source in sources:
        source_type = source.get("type")
        ingest_fn = _INGESTERS.get(source_type)
        if ingest_fn is None:
            continue
        try:
            items = ingest_fn(source, since=None)
            for i, item in enumerate(items):
                item_key = f"raw/{run_date}/{source['id']}/{i}.json"
                s3.put_object(
                    Bucket=bucket,
                    Key=item_key,
                    Body=json.dumps(item),
                    ContentType="application/json",
                )
            all_items.extend(items)
            sources_succeeded += 1
        except Exception:
            logger.warning("ingestion failed for source %s", source.get("id", "unknown"), exc_info=True)

    run_record = {
        "sources_attempted": sources_attempted,
        "sources_succeeded": sources_succeeded,
        "source_ids_attempted": [s.get("id") for s in sources],
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
