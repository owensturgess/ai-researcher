# src/scoring/handler.py
import json
import os

import boto3


def _score_item(bedrock, context_prompt, item):
    user_text = (
        f"Title: {item.get('title', '')}\n"
        f"Content: {item.get('full_text', '')}\n\n"
        "Respond with JSON containing a 'score' field (integer 0-100)."
    )

    request_body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 256,
        "temperature": 0,
        "system": context_prompt,
        "messages": [{"role": "user", "content": user_text}],
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
    urgency = parsed.get("urgency", "informational")
    return parsed["score"], urgency


def handler(event, context):
    bucket = os.environ["PIPELINE_BUCKET"]
    run_date = os.environ.get("RUN_DATE", "")
    context_prompt_path = os.environ.get("CONTEXT_PROMPT_PATH", "config/context-prompt.txt")

    with open(context_prompt_path) as f:
        context_prompt = f.read().strip()

    s3 = boto3.client("s3")
    bedrock = boto3.client("bedrock-runtime")

    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=f"raw/{run_date}/")

    threshold = int(os.environ.get("RELEVANCE_THRESHOLD", "60"))
    items_scored = 0
    items_above_threshold = 0
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
            item = json.loads(body)

            score, urgency = _score_item(bedrock, context_prompt, item)

            item_id = item["id"]
            scored = dict(item)
            scored["relevance_score"] = score
            scored["urgency"] = urgency
            items_scored += 1

            s3.put_object(
                Bucket=bucket,
                Key=f"scored/{run_date}/{item_id}.json",
                Body=json.dumps(scored),
                ContentType="application/json",
            )
            if score >= threshold:
                items_above_threshold += 1

    return {"items_scored": items_scored, "items_above_threshold": items_above_threshold}
