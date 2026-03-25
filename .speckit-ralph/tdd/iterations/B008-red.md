Test fails with `NotImplementedError` — RED state confirmed.

```
FILE: tests/unit/test_x_api_ingestion.py
```

The test:
- Creates a `Source` dataclass object (not a plain dict) with `type="x"`
- Patches `tweepy.Client` at the external boundary
- Calls `ingest(source, since)` with proper typed arguments
- Asserts result fields via **attribute notation** (`item.source_id`, `item.published_date`, `item.original_url`, `item.title`/`item.full_text`) matching the `ContentItem` dataclass contract
- Fails with `NotImplementedError` — valid RED state

Also created `src/shared/models.py` with `Source` and `ContentItem` dataclasses, since that module was absent from the filesystem.
