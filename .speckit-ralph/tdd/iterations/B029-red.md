Test fails exactly as expected. The business-strategy item gets flagged `is_duplicate=True` because the current prompt omits `scoring_reasoning`, so the mock returns `is_duplicate: true`.

```
FILE: tests/unit/test_semantic_deduplication_different_angles.py
```

**What the test verifies**: When two items share a topic but have genuinely different angles documented in `scoring_reasoning`, the LLM deduplication prompt must include `scoring_reasoning` so the LLM can distinguish "same development reported twice" from "same topic, different angle." The mock returns `is_duplicate: true` whenever reasoning is absent from the prompt — which is the current state — causing the business-strategy item to be incorrectly flagged as a duplicate.

**Fix required**: Update `_are_duplicates` in `src/scoring/deduplication.py` to include `item.scoring_reasoning` in the prompt sent to Bedrock.
