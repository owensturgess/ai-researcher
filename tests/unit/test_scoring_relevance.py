# tests/unit/test_scoring_relevance.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.scoring.handler import handler


@mock_aws
def test_each_content_item_receives_relevance_score_between_0_and_100(
    monkeypatch, tmp_path
):
    """
    Given a batch of ingested ContentItems in S3 and a configured company context
    prompt, when the scoring handler runs, each item is scored by the LLM and a
    ScoredItem is written to S3 at scored/{date}/{item_id}.json with a
    relevance_score between 0 and 100 inclusive.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")

    # Write context-prompt.txt at the filesystem boundary
    context_prompt = (
        "Score content for relevance to agentic SDLC transformation goals."
    )
    context_file = tmp_path / "context-prompt.txt"
    context_file.write_text(context_prompt)
    monkeypatch.setenv("CONTEXT_PROMPT_PATH", str(context_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # Write two ContentItems to S3 at the raw path
    items = [
        {
            "id": "item-001",
            "title": "Claude 4 Released with Agentic Capabilities",
            "source_id": "src-rss-1",
            "source_name": "AI News",
            "published_date": "2026-03-24T08:00:00+00:00",
            "full_text": "Anthropic released Claude 4 with major agentic improvements.",
            "original_url": "https://example.com/claude-4",
            "content_format": "text",
            "transcript_status": "not_needed",
        },
        {
            "id": "item-002",
            "title": "Local Weather Forecast for March",
            "source_id": "src-rss-2",
            "source_name": "Weather Feed",
            "published_date": "2026-03-24T07:00:00+00:00",
            "full_text": "Expect sunny skies with a high of 72 degrees.",
            "original_url": "https://example.com/weather",
            "content_format": "text",
            "transcript_status": "not_needed",
        },
    ]
    for item in items:
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"raw/2026-03-24/{item['source_id']}/{item['id']}.json",
            Body=json.dumps(item),
        )

    # Mock Bedrock at the AWS service boundary — returns structured JSON scores
    def bedrock_invoke_side_effect(modelId, body, **kwargs):
        request = json.loads(body)
        # Return a different score per item based on content to simulate LLM scoring
        title = ""
        for msg in request.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str):
                title = content
                break
        score = 85 if "Claude" in title or "claude" in title.lower() else 12
        response_body = json.dumps({
            "score": score,
            "urgency": "worth_discussing",
            "relevance_tag": "AI Tools",
            "summary": "Summary of the item.",
            "reasoning": "Scored based on relevance to agentic SDLC.",
        })
        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps({
            "content": [{"text": response_body}]
        }).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = bedrock_invoke_side_effect

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service in ("bedrock-runtime", "bedrock"):
            return mock_bedrock
        return moto_boto3_client(service, **kw)

    with patch("src.scoring.handler.boto3.client", side_effect=client_factory):
        result = handler({}, None)

    # Handler must report all items scored
    assert result["items_scored"] == 2

    # Each item must have a ScoredItem written to S3 with relevance_score in [0, 100]
    for item in items:
        key = f"scored/2026-03-24/{item['id']}.json"
        response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
        scored = json.loads(response["Body"].read())

        assert "relevance_score" in scored, f"relevance_score missing for {item['id']}"
        score = scored["relevance_score"]
        assert isinstance(score, (int, float)), (
            f"relevance_score must be numeric, got {type(score)} for {item['id']}"
        )
        assert 0 <= score <= 100, (
            f"relevance_score {score} out of [0,100] range for {item['id']}"
        )
