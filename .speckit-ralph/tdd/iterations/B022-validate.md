```
VALIDATION_RESULT: PASS
```

All eight checklist items pass:

1. **Behavior-based naming** — `test_same_content_item_scores_consistently_across_two_consecutive_days` names the observable outcome (score consistency), not an implementation detail. ✓

2. **Public interface only** — Test calls `handler({}, None)` (the documented public entry point) and reads scored output from S3. No private attributes or internal methods are accessed. ✓

3. **Survives refactor** — The `temperature=0` requirement is explicitly part of the scoring handler's documented public contract ("Calls Bedrock/Claude (temperature=0)"), so verifying it is verifying the interface specification, not an arbitrary implementation detail. Any rewrite that preserves the contract passes. ✓

4. **Mocks only at system boundaries** — S3 is mocked via `@mock_aws` and Bedrock via `mock_bedrock` injected through `patch("src.scoring.handler.boto3.client", ...)`. Both are external AWS service boundaries. No internal project collaborators are mocked. ✓

5. **No unmocked external deps** — S3 is fully mocked by moto; Bedrock is replaced by `mock_bedrock`. Context is written to `tmp_path` (no real filesystem concern). ✓

6. **One logical assertion** — Single `assert abs(score_day1 - score_day2) <= 10` targeting one outcome (score consistency across runs). ✓

7. **Independence** — `monkeypatch` scoping cleans env vars between test runs; `@mock_aws` isolates S3 state; `tmp_path` is ephemeral. No shared mutable state with other tests. ✓

8. **Meaningful failure** — Failure message explicitly reports the actual delta, both scores, and the corrective action (`"Ensure the scoring handler passes temperature=0 to Bedrock."`). ✓
