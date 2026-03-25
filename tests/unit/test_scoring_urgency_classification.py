# tests/unit/test_scoring_urgency_classification.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.scoring.handler import handler

VALID_URGENCY_LEVELS = {"informational", "worth_discussing", "action_needed"}


@mock_aws
def test_scored_item_above_threshold_is_classified_with_valid_urgency_level(
    monkeypatch, tmp_path
):
    """
    Given a ContentItem that scores above the relevance threshold, when the
    scoring handler runs and the LLM returns urgency='action_needed', the
    ScoredItem written to S3 has urgency set to one of the three valid levels:
    informational, worth_discussing, or action_needed.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RUN_DATE", "2026-03-24")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "60")

    context_file = tmp_path / "context-prompt.txt"
    context_file.write_text(
        "Score content for relevance to agentic SDLC transformation goals."
    )
    monkeypatch.setenv("CONTEXT_PROMPT_PATH", str(context_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    item = {
        "id": "item-urgency-001",
        "title": "Critical: GPT-5 Threatens Competitive Position",
        "source_id": "src-rss-1",
        "source_name": "AI News",
        "published_date": "2026-03-24T08:00:00+00:00",
        "full_text": "OpenAI released GPT-5 with capabilities far exceeding current models.",
        "original_url": "https://example.com/gpt5-release",
        "content_format": "text",
        "transcript_status": "not_needed",
    }
    s3.put_object(
        Bucket="test-pipeline-bucket",
        Key=f"raw/2026-03-24/{item['source_id']}/{item['id']}.json",
        Body=json.dumps(item),
    )

    # Bedrock returns score=90 (above threshold=60) with urgency='action_needed'
    llm_response_body = json.dumps({
        "score": 90,
        "urgency": "action_needed",
        "relevance_tag": "Competitive Intelligence",
        "summary": "GPT-5 release poses direct competitive threat to agentic SDLC goals.",
        "reasoning": "High-relevance competitive development requiring immediate attention.",
    })
    mock_stream = MagicMock()
    mock_stream.read.return_value = json.dumps({
        "content": [{"text": llm_response_body}]
    }).encode("utf-8")

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = {"body": mock_stream}

    moto_boto3_client = boto3.client

    def client_factory(service, **kw):
        if service in ("bedrock-runtime", "bedrock"):
            return mock_bedrock
        return moto_boto3_client(service, **kw)

    with patch("src.scoring.handler.boto3.client", side_effect=client_factory):
        handler({}, None)

    # ScoredItem must be written with a valid urgency classification
    key = f"scored/2026-03-24/{item['id']}.json"
    response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
    scored = json.loads(response["Body"].read())

    assert "urgency" in scored, "ScoredItem missing urgency field"
    assert scored["urgency"] in VALID_URGENCY_LEVELS, (
        f"urgency '{scored['urgency']}' is not one of {VALID_URGENCY_LEVELS}"
    )
    assert scored["urgency"] == "action_needed", (
        f"Expected 'action_needed' from LLM response, got '{scored['urgency']}'"
    )
