All 30 tests still pass.

```
REFACTORED: src/monitoring/handler.py
```

Removed unused `timezone` import — the only issue flagged by ruff across the entire `src/` tree. The rest of the codebase is clean: functions are short and focused, naming is clear, no duplication worth extracting, and no dead code.
