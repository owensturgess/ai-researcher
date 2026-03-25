Test passes.

```
FILE: src/ingestion/handler.py
```

Added `track_source_failure(source_id, date, succeeded)` and `get_failing_sources(threshold)` to `src/ingestion/handler.py`. State is persisted in S3 under `source-failures/{source_id}.json` with a `consecutive_failures` counter that increments on failure and resets to 0 on success.
