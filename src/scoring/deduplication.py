# src/scoring/deduplication.py
import json

import boto3


def _are_duplicates(bedrock, item_a, item_b):
    prompt = (
        f"Item A summary: {item_a.executive_summary}\n"
        f"Item A reasoning: {item_a.scoring_reasoning}\n"
        f"Item B summary: {item_b.executive_summary}\n"
        f"Item B reasoning: {item_b.scoring_reasoning}\n\n"
        "Do these items cover the same core development? "
        "Respond with JSON: {\"is_duplicate\": true} or {\"is_duplicate\": false}."
    )
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 64,
        "temperature": 0,
        "messages": [{"role": "user", "content": prompt}],
    })
    response = bedrock.invoke_model(
        modelId="anthropic.claude-3-5-sonnet-20241022-v2:0",
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    text = json.loads(response["body"].read())["content"][0]["text"]
    return json.loads(text).get("is_duplicate", False)


def deduplicate_by_semantics(scored_items):
    bedrock = boto3.client("bedrock-runtime")
    items = sorted(scored_items, key=lambda x: x.relevance_score, reverse=True)

    for i in range(len(items)):
        if items[i].is_duplicate:
            continue
        for j in range(i + 1, len(items)):
            if items[j].is_duplicate:
                continue
            if _are_duplicates(bedrock, items[i], items[j]):
                items[j].is_duplicate = True
                items[j].duplicate_of = items[i].content_item_id

    return items
