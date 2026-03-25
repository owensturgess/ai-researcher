# src/ingestion/handler.py
import json
import logging
import os

import boto3

from src.ingestion.config import load_sources as _load_sources
from src.ingestion.sources import rss, web, x_api

logger = logging.getLogger(__name__)

_INGESTERS = {"rss": rss.ingest, "web": web.ingest, "x": x_api.ingest}

_FAILURE_PREFIX = "source-failures/"


def _failure_key(source_id):
    return f"{_FAILURE_PREFIX}{source_id}.json"


def track_source_failure(source_id, date, succeeded):
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")
    key = _failure_key(source_id)

    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
    except Exception:
        data = {"consecutive_failures": 0}

    if succeeded:
        data["consecutive_failures"] = 0
    else:
        data["consecutive_failures"] = data.get("consecutive_failures", 0) + 1

    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(data), ContentType="application/json")


def get_failing_sources(threshold=3):
    bucket = os.environ["PIPELINE_BUCKET"]
    s3 = boto3.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    result = []
    for page in paginator.paginate(Bucket=bucket, Prefix=_FAILURE_PREFIX):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            source_id = key[len(_FAILURE_PREFIX):].removesuffix(".json")
            data = json.loads(s3.get_object(Bucket=bucket, Key=key)["Body"].read())
            count = data.get("consecutive_failures", 0)
            if count >= threshold:
                result.append((source_id, count))
    return result


def load_sources():
    config_path = os.environ.get("SOURCES_CONFIG", "config/sources.yaml")
    return sorted(_load_sources(config_path), key=lambda s: s.priority)


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    s3 = boto3.client("s3")

    sources = load_sources()
    sources_attempted = len(sources)
    sources_succeeded = 0
    all_items = []

    for source in sources:
        ingest_fn = _INGESTERS.get(source.type)
        if ingest_fn is None:
            continue
        try:
            items = ingest_fn(source, since=None)
            for i, item in enumerate(items):
                item_key = f"raw/{run_date}/{source.id}/{i}.json"
                s3.put_object(
                    Bucket=bucket,
                    Key=item_key,
                    Body=json.dumps(item),
                    ContentType="application/json",
                )
            all_items.extend(items)
            sources_succeeded += 1
        except Exception:
            logger.warning("ingestion failed for source %s", source.id, exc_info=True)

    run_record = {
        "sources_attempted": sources_attempted,
        "sources_succeeded": sources_succeeded,
        "source_ids_attempted": [s.id for s in sources],
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
