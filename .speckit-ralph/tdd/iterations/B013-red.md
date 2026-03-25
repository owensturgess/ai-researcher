```
FILE: tests/unit/test_ingestion_error_isolation.py
```

The test:
- Sets up two active RSS sources (one at `failing.example.com`, one at `healthy.example.com`)
- Mocks `feedparser.parse` at the network boundary with a `side_effect` that raises `HTTPError(429)` for the failing URL and returns a valid feed for the healthy one
- Asserts `sources_attempted == 2`, `sources_succeeded == 1` — proving the failure was isolated and the handler didn't abort
- Asserts the healthy source's items were written to S3 — proving normal processing continued past the failed source
