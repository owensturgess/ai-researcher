The write needs your approval — please allow it when prompted. Once the file is written:

```
FILE: tests/unit/test_rss_ingestion.py
```

The test:
- Mocks `feedparser.parse` at the system boundary (external HTTP call)
- Creates a `Source` with `type="rss"` and calls the public `ingest(source, since)` interface
- Asserts one `ContentItem` is returned with the correct `title`, `source_id`, `original_url`, and `published_date >= since`
- Will fail immediately since `src/ingestion/sources/rss.py` does not exist yet
