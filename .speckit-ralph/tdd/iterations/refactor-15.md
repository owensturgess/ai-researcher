All 9 tests pass.

```
REFACTORED: src/ingestion/handler.py
```

**Change**: Replaced silent `except Exception: pass` with `logger.warning(...)` including `exc_info=True`. The bare `pass` silently swallowed all ingestion errors, making production debugging impossible. The error isolation behavior is preserved (failed sources are still skipped), but failures are now logged with the source ID and full traceback.
