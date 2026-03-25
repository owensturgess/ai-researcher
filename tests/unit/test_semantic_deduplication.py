# tests/unit/test_semantic_deduplication.py
#
# Behavior B028: Given two content items from different sources cover the same
# development, only the highest-relevance version appears in the briefing.
#
# Tests the public interface deduplicate_by_semantics(scored_items) in
# src/scoring/deduplication.py. When two ScoredItems cover the same core
# development, the lower-relevance item must be flagged with is_duplicate=True
# and duplicate_of pointing to the higher-relevance item's content_item_id.
import json
from unittest.mock import MagicMock, patch

from src.scoring.deduplication import deduplicate_by_semantics
from src.shared.models import ScoredItem


def test_lower_relevance_item_flagged_as_duplicate_when_two_sources_cover_same_development():
    """
    Given two ScoredItems from different sources covering the same Claude 4
    release (score 85 and score 60), when deduplicate_by_semantics() runs,
    the lower-relevance item has is_duplicate=True and duplicate_of set to
    the higher-relevance item's content_item_id, while the higher-relevance
    item remains is_duplicate=False.
    """
    item_primary = ScoredItem(
        content_item_id="item-claude4-techcrunch",
        relevance_score=85,
        urgency="worth_discussing",
        relevance_tag="AI Tools",
        executive_summary=(
            "Anthropic releases Claude 4 with major agentic software development "
            "capabilities, enabling autonomous multi-step coding workflows."
        ),
        scoring_reasoning="Directly relevant to agentic SDLC transformation goals.",
        is_duplicate=False,
        duplicate_of=None,
    )

    item_duplicate = ScoredItem(
        content_item_id="item-claude4-verge",
        relevance_score=60,
        urgency="informational",
        relevance_tag="AI Tools",
        executive_summary=(
            "Claude 4 AI assistant launched by Anthropic with new coding and "
            "agentic features announced today."
        ),
        scoring_reasoning="Same Claude 4 release covered from a consumer angle.",
        is_duplicate=False,
        duplicate_of=None,
    )

    # Mock Bedrock at the AWS service boundary — LLM identifies the pair as duplicates
    # and nominates item-claude4-techcrunch (higher score) as the primary version.
    llm_response = json.dumps({"is_duplicate": True})
    mock_stream = MagicMock()
    mock_stream.read.return_value = json.dumps(
        {"content": [{"text": llm_response}]}
    ).encode("utf-8")

    mock_bedrock = MagicMock()
    mock_bedrock.invoke_model.return_value = {"body": mock_stream}

    with patch("src.scoring.deduplication.boto3.client", return_value=mock_bedrock):
        result = deduplicate_by_semantics([item_primary, item_duplicate])

    by_id = {item.content_item_id: item for item in result}

    # Higher-relevance item must remain primary — not flagged as duplicate
    assert by_id["item-claude4-techcrunch"].is_duplicate is False, (
        "The highest-relevance item must not be flagged as a duplicate."
    )
    assert by_id["item-claude4-techcrunch"].duplicate_of is None

    # Lower-relevance item must be flagged as a duplicate of the primary
    assert by_id["item-claude4-verge"].is_duplicate is True, (
        "The lower-relevance item covering the same development must be flagged "
        "is_duplicate=True so it is excluded from the briefing."
    )
    assert by_id["item-claude4-verge"].duplicate_of == "item-claude4-techcrunch", (
        f"duplicate_of must point to the primary item id, "
        f"got: {by_id['item-claude4-verge'].duplicate_of!r}"
    )
