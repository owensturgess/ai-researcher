# src/briefing/handler.py
import json
import os

import boto3


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    threshold = int(os.environ.get("RELEVANCE_THRESHOLD", "60"))

    s3 = boto3.client("s3")

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=f"scored/{run_date}/")

    included_items = []
    for page in pages:
        for obj in page.get("Contents", []):
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            item = json.loads(body)
            if item.get("relevance_score", 0) >= threshold:
                included_items.append(item)

    return {"items_included": len(included_items)}
