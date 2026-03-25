Results are exactly right:
- 7 existing tests pass (including `test_x_api_ingestion.py` which was previously broken)
- New B014 test fails with `AssertionError: 0 >= 1` — no rate-limit log emitted because pagination isn't implemented, so `TooManyRequests` is never raised and never logged

```
FILE: tests/unit/test_x_api_rate_limit_mid_ingestion.py
```

**What was fixed:** `x_api.py` had two bugs from a prior GREEN step (`source["url"]`/`source["id"]` dict access on a dataclass, and returning plain dicts instead of `ContentItem` objects). Fixed both to restore the full suite.

**Why the B014 test fails:** The current `ingest()` makes a single `search_recent_tweets` call with no pagination loop. The mock's first page response has `meta.next_token = "page2_token"`, but because no pagination is implemented, the second call (which would raise `TooManyRequests`) is never made, so no rate-limit warning is logged. The assertion `len(rate_limit_logs) >= 1` → `0 >= 1` fails.

The GREEN step must implement: paginated fetching that catches `tweepy.errors.TooManyRequests`, logs a `"rate limit"` warning, and returns already-retrieved items.
