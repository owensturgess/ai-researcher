Test fails as expected (RED).

```
FILE: tests/unit/test_podcast_ingestion.py
```

The test:
- Mocks `feedparser.parse` at the network boundary with a feed entry that has an enclosure URL
- Calls `ingest(source, since)` on a podcast-type Source
- Asserts the result contains one ContentItem with `content_format=audio`, correct `source_id`, `title`, `original_url` (the enclosure URL), and `published_date >= since`

Fails with `NotImplementedError` from the stub — ready for GREEN.
