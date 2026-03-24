Both writes need your approval. Please allow them when prompted.

---

```
VALIDATION_RESULT: PASS
```

**Summary of review:**

| Check | Result |
|-------|--------|
| 1. Behavior-based naming | PASS |
| 2. Public interface only | PASS |
| 3. Survives refactor | PASS |
| 4. Mocks only at system boundaries (`feedparser.parse`) | PASS |
| 5. No unmocked external deps | PASS |
| 6. One logical assertion (all asserts on same ContentItem outcome) | PASS |
| 7. Independence | PASS |
| 8. Meaningful failure messages | PASS |

The test is ready for the GREEN phase — implement `src/ingestion/sources/rss.py` with the `ingest(source, since)` function returning `ContentItem` objects parsed from feedparser entries.
