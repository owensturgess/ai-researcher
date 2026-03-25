```
FILE: tests/unit/test_source_config_new_entry.py
```

The test calls `load_sources(config_path)` from `src/ingestion/config.py` (which doesn't exist yet) with a YAML file containing a newly added source entry, then asserts the new source appears in the returned list with the correct `name`, `type`, `url`, and `category`. It will fail immediately with `ModuleNotFoundError` until the implementation is written.
