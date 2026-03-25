Test fails correctly. The assertion shows scores differ by 45 points (30 vs 75) because the handler doesn't pass `temperature=0` to Bedrock.

```
FILE: tests/unit/test_scoring_reliability.py
```

The test fails with `AssertionError: Scores differ by 45 points (day1=30, day2=75)`. The mock simulates LLM non-determinism — returning alternating scores (30, 75) when `temperature` is absent, but a stable 75 on both calls when `temperature=0` is set. The current handler (`src/scoring/handler.py:15`) builds the Bedrock request body without a `temperature` field, so the mock's non-deterministic path triggers and the ±10 reliability assertion fails.
