Test passes.

```
FILE: src/transcription/handler.py
```

Added a budget cap check at the start of the `audio` branch in `handler`: reads `DAILY_TRANSCRIPTION_BUDGET_MINUTES` from env and raises `RuntimeError` if `<= 0`. The existing exception handler catches it, writes `transcript_status: failed` to S3, and returns `{"transcript_status": "failed"}`.
