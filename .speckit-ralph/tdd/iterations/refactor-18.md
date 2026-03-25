All 12 tests pass.

```
REFACTORED: src/ingestion/handler.py
REFACTORED: src/transcription/handler.py
```

Changes made:
- **`src/ingestion/handler.py`**: Moved the `ingesters` dispatch dict to module-level constant `_INGESTERS` — it's static and doesn't need rebuilding per handler invocation.
- **`src/transcription/handler.py`**: Extracted the "read item → set transcript_status=failed → write back" logic into `_mark_transcript_failed()`, reducing the complexity of the handler's except block.
