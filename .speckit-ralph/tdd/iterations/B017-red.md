The test now fails for the right reason — current implementation returns `completed` (no budget cap logic exists).

```
FILE: tests/unit/test_podcast_budget_cap.py
```

The test:
- Sets `DAILY_TRANSCRIPTION_BUDGET_MINUTES=0` to exhaust the budget cap
- Mocks only `urllib.request.urlopen` (network) and `boto3.client("transcribe")` (AWS) at system boundaries
- Uses a real 417-byte MPEG1/Layer3 fixture in `tests/fixtures/short_podcast.mp3` — no `mutagen` mock
- Pre-populates the Transcribe output in S3 so the baseline path would return `completed`, confirming the assertion `== 'failed'` tests the budget cap specifically
- Fails: `assert 'completed' == 'failed'` — implementation has no budget cap check
