Test fails at import — correct RED state.

```
FILE: tests/unit/test_consecutive_source_failure_tracking.py
```

The test imports `get_failing_sources` and `track_source_failure` from `src.ingestion.handler`, which don't exist yet. The `ImportError` confirms a valid RED state. The test exercises the full observable contract for B034:

1. `track_source_failure(source_id, date, succeeded=False)` increments consecutive failure count for a source
2. `track_source_failure(source_id, date, succeeded=True)` resets the count on recovery
3. `get_failing_sources(threshold=3)` returns `(source_id, count)` tuples where count ≥ threshold — and excludes sources that have recovered
