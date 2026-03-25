All 3 tests pass.

```
REFACTORED: src/ingestion/sources/rss.py
```

Converted the accumulate-and-return loop into a direct list comprehension. The remaining files (`web.py`, `handler.py`, `x_api.py`, `youtube.py`) are already clean — `web.py`'s loop has intermediate tag-extraction logic that would hurt readability as a comprehension, and `handler.py`'s loop has side effects (`sources_succeeded` counter), so both are better as-is.
