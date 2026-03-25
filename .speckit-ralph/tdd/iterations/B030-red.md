Test fails at the right point — assertions 1 and 2 pass (the existing implementation correctly selects the primary and flags all 4 duplicates), but assertion 3 fails because `ScoredItem` has no `also_reported_by` field.

```
FILE: tests/unit/test_deduplication_five_sources.py
```

**What the test covers**: When 5 items cover the same development, `deduplicate_by_semantics()` must:
1. ✅ Keep only the highest-scoring item as non-duplicate (passes with current impl)
2. ✅ Flag all 4 others with `is_duplicate=True` and correct `duplicate_of` (passes with current impl)
3. ❌ Set `primary.also_reported_by` to a list of the 4 duplicate IDs (fails — new behavior)

**To go GREEN**: Add `also_reported_by: list = field(default_factory=list)` to `ScoredItem` in `models.py`, and populate it inside `deduplicate_by_semantics()` when flagging duplicates.
