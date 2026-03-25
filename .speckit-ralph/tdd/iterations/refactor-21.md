All 15 tests pass.

```
REFACTORED: src/scoring/handler.py
```

**Change**: Moved `_score_item` above `handler` to follow the helpers-before-orchestrator convention used consistently in `transcription/handler.py` and `ingestion/handler.py`. Also removed a redundant comment. No behavioral changes.

The rest of the codebase is clean — functions are small and focused, naming is clear, no duplication worth extracting, and no dead code.
