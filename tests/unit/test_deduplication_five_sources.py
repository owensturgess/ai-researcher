# tests/unit/test_deduplication_five_sources.py
#
# Behavior B030: When the same development is announced across 5+ sources,
# the deduplication step selects the single best representative item, with
# other source links optionally listed as "also reported by".
#
# Tests the public interface deduplicate_by_semantics(scored_items) in
# src/scoring/deduplication.py. When 5 ScoredItems all cover the same core
# development, the highest-relevance item must be retained as primary and all
# four others flagged as duplicates. The primary item must expose an
# also_reported_by attribute listing the content_item_ids of the other
# sources — enabling the briefing template to surface "also covered by 4
# other sources" without cluttering the main item list.
#
# This test fails (RED) because ScoredItem has no also_reported_by field and
# deduplicate_by_semantics does not populate it.
import json
from unittest.mock import MagicMock, patch

from src.scoring.deduplication import deduplicate_by_semantics
from src.shared.models import ScoredItem


def test_five_sources_same_development_best_item_retained_with_also_reported_by():
    """
    Given five ScoredItems from different sources all covering the same GPT-5
    release (scores 90, 75, 65, 55, 45), when deduplicate_by_semantics() runs:

    1. Exactly one item has is_duplicate=False (the score-90 primary).
    2. All four remaining items have is_duplicate=True and duplicate_of equal
       to the primary item's content_item_id.
    3. The primary item has an also_reported_by attribute that is a list
       containing the content_item_ids of all four duplicate items — so the
       briefing renderer can append "also reported by: source-b, source-c, …"
       without re-querying the full scored list.
    """
    items = [
        ScoredItem(
            content_item_id="item-gpt5-source-a",
            relevance_score=90,
            urgency="action_needed",
            relevance_tag="Competitive Intelligence",
            executive_summary=(
                "OpenAI releases GPT-5 with reasoning and agentic capabilities "
                "that set a new industry benchmark for AI-assisted software development."
            ),
            scoring_reasoning="Primary source with deepest technical analysis.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-b",
            relevance_score=75,
            urgency="worth_discussing",
            relevance_tag="Competitive Intelligence",
            executive_summary=(
                "GPT-5 announced by OpenAI; industry observers note significant "
                "improvements over GPT-4 in coding benchmarks."
            ),
            scoring_reasoning="Same GPT-5 release from a different outlet.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-c",
            relevance_score=65,
            urgency="worth_discussing",
            relevance_tag="Competitive Intelligence",
            executive_summary=(
                "OpenAI's GPT-5 model launched today with multimodal and agentic features."
            ),
            scoring_reasoning="Same release, shorter coverage.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-d",
            relevance_score=55,
            urgency="informational",
            relevance_tag="AI Tools",
            executive_summary=(
                "GPT-5 is here: OpenAI drops its most powerful model yet."
            ),
            scoring_reasoning="Consumer-angle reporting on the same release.",
            is_duplicate=False,
            duplicate_of=None,
        ),
        ScoredItem(
            content_item_id="item-gpt5-source-e",
            relevance_score=45,
            urgency="informational",
            relevance_tag="AI Tools",
            executive_summary=(
                "OpenAI announces GPT-5 availability for ChatGPT Plus users."
            ),
            scoring_reasoning="Brief product-availability notice for the same release.",
            is_duplicate=False,
            duplicate_of=None,
        ),
    ]

    # All five items cover the same GPT-5 release — LLM returns is_duplicate=true
    # for every pairwise comparison initiated by the implementation.
    def invoke_model_side_effect(modelId, body, **kwargs):
        mock_stream = MagicMock()
        mock_stream.read.return_value = json.dumps(
            {"content": [{"text": json.dumps({"is_duplicate": True})}]}
        ).encode("utf-8")
        return {"body": mock_stream}

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.side_effect = invoke_model_side_effect

    with patch("src.scoring.deduplication.boto3.client", return_value=mock_bedrock):
        result = deduplicate_by_semantics(items)

    by_id = {item.content_item_id: item for item in result}

    # --- Assertion 1: exactly one non-duplicate (the highest-scoring primary) ---
    non_duplicates = [item for item in result if not item.is_duplicate]
    assert len(non_duplicates) == 1, (
        f"Expected exactly 1 non-duplicate item, got {len(non_duplicates)}: "
        f"{[i.content_item_id for i in non_duplicates]}"
    )
    primary = non_duplicates[0]
    assert primary.content_item_id == "item-gpt5-source-a", (
        f"The highest-relevance item (score 90) must be the primary; "
        f"got: {primary.content_item_id}"
    )

    # --- Assertion 2: all four remaining items flagged as duplicates of the primary ---
    duplicate_ids = {"item-gpt5-source-b", "item-gpt5-source-c",
                     "item-gpt5-source-d", "item-gpt5-source-e"}
    for item_id in duplicate_ids:
        item = by_id[item_id]
        assert item.is_duplicate is True, (
            f"{item_id} must be flagged is_duplicate=True when 5 sources cover "
            "the same development and it is not the highest-relevance item."
        )
        assert item.duplicate_of == "item-gpt5-source-a", (
            f"{item_id}.duplicate_of must point to the primary item "
            f"'item-gpt5-source-a', got: {item.duplicate_of!r}"
        )

    # --- Assertion 3: primary item exposes also_reported_by list of duplicate IDs ---
    # This will FAIL (RED) because ScoredItem has no also_reported_by field and
    # deduplicate_by_semantics does not populate it.
    assert hasattr(primary, "also_reported_by"), (
        "The primary ScoredItem must have an 'also_reported_by' attribute so that "
        "the briefing renderer can append 'also reported by: …' without re-scanning "
        "the full scored list. Add also_reported_by to ScoredItem and populate it "
        "in deduplicate_by_semantics()."
    )
    also_reported = set(primary.also_reported_by)
    assert also_reported == duplicate_ids, (
        f"primary.also_reported_by must contain the ids of all 4 duplicate items. "
        f"Expected: {duplicate_ids}, got: {also_reported}"
    )
