```
VALIDATION_RESULT: PASS
```

All eight checklist items pass:

1. **Behavior-based naming** — `test_five_sources_same_development_best_item_retained_with_also_reported_by` names the observable outcome, not the implementation.
2. **Public interface only** — test only calls `deduplicate_by_semantics()` and constructs `ScoredItem` via public fields.
3. **Survives refactor** — no internal method calls; the contract is fully expressed through `is_duplicate`, `duplicate_of`, and `also_reported_by`.
4. **Mocks only at system boundaries** — `patch("src.scoring.deduplication.boto3.client", ...)` targets the AWS Bedrock boundary; no internal collaborators are mocked.
5. **No unmocked external deps** — the `invoke_model` side effect intercepts all Bedrock calls; no real network traffic.
6. **One logical assertion** — all three assertion blocks test different facets of a single `deduplicate_by_semantics(items)` invocation on the same compound behavior (B030 explicitly names both "selects single best item" and "also reported by"); multiple asserts on one outcome are permitted.
7. **Independence** — fixture data is constructed inline; no shared mutable state or ordering dependency.
8. **Meaningful failure** — every `assert` carries an `f-string` that names the violated invariant and shows the actual value.
