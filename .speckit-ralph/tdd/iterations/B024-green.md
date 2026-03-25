```
FILE: src/ingestion/handler.py
```

Added `"source_ids_attempted": [s.get("id") for s in sources]` to the run record. This gives operators an explicit list of source IDs that participated in each run.
