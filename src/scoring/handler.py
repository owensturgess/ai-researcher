# src/scoring/handler.py
import json
import os

import boto3


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    context_prompt_path = os.environ.get("CONTEXT_PROMPT_PATH", "config/context-prompt.txt")

    with open(context_prompt_path) as f:
        context_prompt = f.read().strip()

    s3 = boto3.client("s3")
    bedrock = boto3.client("bedrock-runtime")

    # List all raw items for this run date
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=f"raw/{run_date}/")

    items_scored = 0
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            item = json.loads(body)

            score = _score_item(bedrock, context_prompt, item)

            item_id = item["id"]
            scored = dict(item)
            scored["relevance_score"] = score

            s3.put_object(
                Bucket=bucket,
                Key=f"scored/{run_date}/{item_id}.json",
                Body=json.dumps(scored),
                ContentType="application/json",
            )
            items_scored += 1

    return {"items_scored": items_scored}


def _score_item(bedrock, context_prompt, item):
    prompt_text = (
        f"{context_prompt}\n\n"
        f"Title: {item.get('title', '')}\n"
        f"Content: {item.get('full_text', '')}\n\n"
        "Respond with JSON containing a 'score' field (integer 0-100)."
    )

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt_text}],
    })

    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=request_body,
        contentType="application/json",
        accept="application/json",
    )

    response_body = json.loads(response["body"].read())
    text = response_body["content"][0]["text"]
    parsed = json.loads(text)
    return parsed["score"]
