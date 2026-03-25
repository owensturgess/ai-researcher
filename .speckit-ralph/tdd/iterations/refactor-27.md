All 21 tests pass.

```
REFACTORED: src/ingestion/config.py
```

The `config.get("sources", [])` was parsed twice — once into `raw` for duplicate-ID validation, then a second time for building Source objects. The list comprehension now reuses the already-validated `raw` variable, eliminating the redundant dictionary lookup.

The rest of the codebase is clean: functions are focused, naming is clear, and there's no dead code or unnecessary complexity.
