# tests/unit/test_scoring_reliability.py
import json
from unittest.mock import MagicMock, patch

import boto3
from moto import mock_aws

from src.scoring.handler import handler

# The scoring handler must call Bedrock with temperature=0 so that the same
# content item receives consistent scores across consecutive daily runs.
# Without temperature=0, LLM outputs are non-deterministic and scores can vary
# wildly between runs — violating the ±10 point reliability requirement.


@mock_aws
def test_same_content_item_scores_consistently_across_two_consecutive_days(
    monkeypatch, tmp_path
):
    """
    Given the same content item is ingested and scored on two consecutive days,
    when the scoring handler runs each day, the two resulting relevance scores
    differ by no more than ±10 points — confirmed by the handler passing
    temperature=0 to Bedrock so the LLM produces deterministic output.
    """
    monkeypatch.setenv("PIPELINE_BUCKET", "test-pipeline-bucket")
    monkeypatch.setenv("RELEVANCE_THRESHOLD", "0")  # score all items

    context_file = tmp_path / "context-prompt.txt"
    context_file.write_text(
        "Score content for relevance to agentic SDLC transformation goals."
    )
    monkeypatch.setenv("CONTEXT_PROMPT_PATH", str(context_file))

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="test-pipeline-bucket")

    # The same item ingested on two consecutive days
    item = {
        "id": "item-reliability-001",
        "title": "Claude 4 Released with Agentic Capabilities",
        "source_id": "src-rss-1",
        "source_name": "AI News",
        "published_date": "2026-03-24T08:00:00+00:00",
        "full_text": "Anthropic released Claude 4 with major agentic improvements.",
        "original_url": "https://example.com/claude-4",
        "content_format": "text",
        "transcript_status": "not_needed",
    }

    for run_date in ("2026-03-24", "2026-03-25"):
        s3.put_object(
            Bucket="test-pipeline-bucket",
            Key=f"raw/{run_date}/{item['source_id']}/{item['id']}.json",
            Body=json.dumps(item),
        )

    # Bedrock mock: when temperature=0 is present both calls return 75 (consistent).
    # When temperature is absent or non-zero the mock alternates between 30 and 75
    # on successive calls, simulating the non-determinism that arises without
    # temperature pinning. This makes the test fail (RED) until the handler passes
    # temperature=0 so the same score is produced across consecutive daily runs.
    call_counter = {"n": 0}
    non_deterministic_scores = [30, 75]  # differ by 45 — exceeds ±10 threshold

    def bedrock_invoke_side_effect(modelId, body, **kwargs):
        request = json.loads(body)
        uses_zero_temp = request.get("temperature", None) == 0
        if uses_zero_temp:
            score = 75  # deterministic when temperature=0
        else:
            # Alternate scores to simulate non-determinism without temperature pinning
            score = non_deterministic_scores[call_counter["n"] % len(non_deterministic_scores)]
            call_counter["n"] += 1
        response_body = json.dumps({
            "score": score,
            "urgency": "worth_discussing",
            "relevance_tag": "AI Tools",
            "summary": "Agentic AI release.",
            "reasoning": "Directly relevant to agentic SDLC goals.",
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

    scores = []
    for run_date in ("2026-03-24", "2026-03-25"):
        monkeypatch.setenv("RUN_DATE", run_date)
        with patch("src.scoring.handler.boto3.client", side_effect=client_factory):
            handler({}, None)

        key = f"scored/{run_date}/{item['id']}.json"
        response = s3.get_object(Bucket="test-pipeline-bucket", Key=key)
        scored = json.loads(response["Body"].read())
        scores.append(scored["relevance_score"])

    # Both daily scores must be within ±10 points of each other
    score_day1, score_day2 = scores
    assert abs(score_day1 - score_day2) <= 10, (
        f"Scores differ by {abs(score_day1 - score_day2)} points "
        f"(day1={score_day1}, day2={score_day2}) — exceeds ±10 reliability threshold. "
        "Ensure the scoring handler passes temperature=0 to Bedrock."
    )
