Full suite: 1 failed (B020 RED, correct), 13 passed (all existing tests restored).

```
FILE: tests/unit/test_briefing_threshold_filtering.py
```

**Summary of changes made:**

1. **Restored `src/scoring/handler.py`** — the previous GREEN attempt incorrectly filtered items at the scoring stage (only writing above-threshold items to S3). This broke B019. Restored it to write ALL scored items to `scored/`, and only count `items_above_threshold` for reporting.

2. **Created `src/briefing/__init__.py`** and **`src/briefing/handler.py`** stubs — the briefing package didn't exist. The stub raises `NotImplementedError` so the test fails at runtime (not collection time).

3. **Written `tests/unit/test_briefing_threshold_filtering.py`** — B020's RED test targets the **briefing handler** (not the scoring handler), which is the correct interface: per the spec, the briefing handler "loads ScoredItems above threshold." The test pre-populates S3 with two scored items (scores 75 and 40), calls the briefing handler, and asserts `items_included == 1`.
