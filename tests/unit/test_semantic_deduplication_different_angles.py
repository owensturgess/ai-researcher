# tests/unit/test_semantic_deduplication_different_angles.py
#
# Behavior B029: Given two items have similar topics but genuinely different
# angles or insights, both items are retained as distinct entries.
#
# The current _are_duplicates prompt sends only executive_summary to the LLM.
# Without scoring_reasoning, the LLM lacks context to distinguish "same core
# development reported twice" from "same topic covered from a genuinely
# different angle." This test will FAIL (RED) until scoring_reasoning is
# included in the deduplication prompt, enabling proper angle differentiation.

import json
from unittest.mock import MagicMock, patch

from src.scoring.deduplication import deduplicate_by_semantics
from src.shared.models import ScoredItem


def test_items_with_different_angle_reasoning_are_both_retained_when_reasoning_informs_dedup():
    """
    Given two ScoredItems with similar executive_summaries (same GPT-5 release)
    but scoring_reasoning that explicitly documents different angles — one scored
    from a developer-tools perspective, one from a business-strategy perspective —
    when deduplicate_by_semantics() is called, both items are retained as distinct
    entries (is_duplicate=False, duplicate_of=None for both).

    The Bedrock mock returns is_duplicate=false ONLY when the prompt contains
    the scoring_reasoning text, simulating a real LLM that correctly identifies
    different angles once given full context. With the current implementation
    (prompt contains only executive_summary), the mock returns is_duplicate=true
    and the test FAILS — confirming that scoring_reasoning must be included in
    the deduplication prompt to detect genuinely different angles.
    """
    item_developer = ScoredItem(
        content_item_id="item-gpt5-developer-tools",
        relevance_score=85,
        urgency="worth_discussing",
        relevance_tag="AI Tools",
        executive_summary=(
            "OpenAI releases GPT-5 with advanced coding and agentic capabilities, "
            "signalling a major shift in AI-assisted development workflows."
        ),
        scoring_reasoning=(
            "Scored from a developer-tools angle: GPT-5 directly competes with our "
            "agentic SDLC toolchain choices and may alter which LLM we recommend "
            "for code generation tasks."
        ),
        is_duplicate=False,
        duplicate_of=None,
    )

    item_business = ScoredItem(
        content_item_id="item-gpt5-business-strategy",
        relevance_score=70,
        urgency="worth_discussing",
        relevance_tag="Market Intelligence",
        executive_summary=(
            "GPT-5 launched by OpenAI; analysts expect significant market impact "
            "across enterprise AI adoption."
        ),
        scoring_reasoning=(
            "Scored from a business-strategy angle: this launch reshapes the "
            "competitive landscape for enterprise AI adoption and may influence "
            "budget allocation decisions for agentic SDLC initiatives."
        ),
        is_duplicate=False,
        duplicate_of=None,
    )

    # Bedrock mock: returns is_duplicate=false only when scoring_reasoning text
    # is present in the prompt — simulating a well-informed LLM that recognises
    # the developer-tools and business-strategy angles as genuinely distinct.
    # Without reasoning in the prompt the mock returns is_duplicate=true, which
    # causes the test to fail (RED) for the current implementation.
    def invoke_model_side_effect(modelId, body, **kwargs):
        request = json.loads(body)
        prompt_text = ""
        for msg in request.get("messages", []):
            content = msg.get("content", "")
            if isinstance(content, str):
                prompt_text += content

        reasoning_present = (
            "developer-tools angle" in prompt_text
            or "business-strategy angle" in prompt_text
        )
        result = {"is_duplicate": not reasoning_present}

        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps(
            {"content": [{"text": json.dumps(result)}]}
        ).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = invoke_model_side_effect

    with patch("src.scoring.deduplication.boto3.client", return_value=mock_bedrock):
        result = deduplicate_by_semantics([item_developer, item_business])

    by_id = {item.content_item_id: item for item in result}

    # Both items must be retained as distinct entries — neither flagged as duplicate
    assert by_id["item-gpt5-developer-tools"].is_duplicate is False, (
        "The developer-tools-angle item must not be flagged as a duplicate."
    )
    assert by_id["item-gpt5-business-strategy"].is_duplicate is False, (
        "The business-strategy-angle item must not be flagged as a duplicate — "
        "it covers the same topic as the other item but from a genuinely different "
        "angle. The dedup prompt must include scoring_reasoning so the LLM can "
        "distinguish angle coverage from same-development duplication."
    )
    assert by_id["item-gpt5-business-strategy"].duplicate_of is None, (
        "duplicate_of must be None for an item retained as a distinct entry."
    )
