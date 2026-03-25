The test fails correctly in RED state. The current `ingest()` makes only one API call and has no quota error handling or warning logging.

```
FILE: tests/unit/test_youtube_quota_limit.py
```

The test fails because:
1. The implementation never encounters the quota error (no pagination, single `execute()` call)
2. No quota warning is ever logged

The GREEN implementation will need to: add pagination support, catch `HttpError` with status 403 (quotaExceeded), log a warning, and return partial results instead of propagating the exception.
