Test fails at import — `src.scoring.deduplication` doesn't exist. This is the correct RED state (no implementation yet, `ScoredItem` also missing from models).

```
FILE: tests/unit/test_semantic_deduplication.py
```

The test fails with `ModuleNotFoundError: No module named 'src.scoring.deduplication'` — confirming RED phase. It also implicitly requires `ScoredItem` in `src/shared/models.py`, which doesn't exist yet.
