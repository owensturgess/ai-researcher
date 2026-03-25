Test passes.

```
FILE: src/ingestion/sources/youtube.py
```

Added pagination loop with `nextPageToken`, catches `HttpError` with status 403, logs a quota warning, and returns partial results.
