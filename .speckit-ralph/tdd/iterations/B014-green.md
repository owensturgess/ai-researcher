All 8 tests pass.

```
FILE: src/ingestion/sources/x_api.py
FILE: conftest.py
```

**Changes made:**

1. **`src/ingestion/sources/x_api.py`** — added a pagination loop that passes `next_token` on subsequent calls, catches `tweepy.errors.TooManyRequests`, logs a warning containing "rate limit", and returns whatever items were collected before the error.

2. **`conftest.py`** — added `tweepy.errors` submodule stub with a `TooManyRequests` exception class, so both the test (`raise tweepy.errors.TooManyRequests(...)`) and the implementation (`except tweepy.errors.TooManyRequests`) resolve correctly against the stub.
