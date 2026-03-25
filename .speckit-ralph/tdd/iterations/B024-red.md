Test fails as expected — `source_ids_attempted` is absent from the current run record.

```
FILE: tests/unit/test_source_removal_stops_ingestion.py
```

The test fails with:
```
AssertionError: pipeline run record missing 'source_ids_attempted' field
assert 'source_ids_attempted' in {'delivery_status': 'pending', 'items_ingested': 0, 'sources_attempted': 1, ...}
```

The handler currently writes only count fields (`sources_attempted`, `sources_succeeded`, etc.) — no explicit list of source IDs. The test requires adding `source_ids_attempted` to the S3 pipeline run record, which gives operators a verifiable record of exactly which sources participated in each run (and implicitly proves removed sources are excluded by ID, not just by count).
