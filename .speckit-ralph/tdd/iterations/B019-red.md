```
FILE: tests/unit/test_scoring_relevance.py
```

The test:
- Writes two `ContentItem` JSON blobs to mocked S3 (`raw/2026-03-24/{source_id}/{item_id}.json`)
- Mocks Bedrock at the AWS service boundary, returning structured JSON with a `score` field
- Calls `handler({}, None)` from `src/scoring/handler.py` (which doesn't exist yet → import fails → test fails RED)
- Asserts each item has a `scored/{date}/{item_id}.json` in S3 with `relevance_score` in [0, 100]
