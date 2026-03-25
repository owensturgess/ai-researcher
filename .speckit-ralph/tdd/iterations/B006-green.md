Test passes. Here's what was written:

```
FILE: src/ingestion/sources/rss.py
FILE: src/ingestion/sources/web.py
FILE: src/ingestion/handler.py
```

**Summary of changes:**
- `rss.py`: calls `feedparser.parse(url)`, returns list of items from feed entries
- `web.py`: calls `urllib.request.urlopen(url)`, parses HTML with BeautifulSoup, returns items from `<article>` tags
- `handler.py`: reads `SOURCES_CONFIG` YAML → loads active sources → dispatches to `rss`/`web` ingesters → writes `pipeline-runs/{date}/run.json` to S3 with `sources_attempted`, `sources_succeeded`, `items_ingested`, `transcription_jobs`, `delivery_status`
