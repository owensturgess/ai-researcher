Test passes. The fix was installing `google-api-python-client` (`googleapiclient`) for the Python 3.14 interpreter used by pytest.

```
FILE: src/ingestion/sources/youtube.py
```

No implementation changes were needed — the existing code was correct. The failure was a missing system dependency.

### Sign: pip shim broken for older Python, use python3 -m pip
- **Category**: GREEN-FAILURE
- **Detail**: `/usr/local/bin/pip` pointed to a removed Python 3.9 interpreter. Use `python3 -m pip install <pkg>` to target the active interpreter. Always install packages via `python3 -m pip` rather than bare `pip` in this environment.
