Test fails as required (stub handler has no `yt_dlp` attribute — the patch target doesn't exist yet, which is the expected RED state).

```
FILE: tests/unit/test_youtube_transcription.py
```

The test fails with `AttributeError: module 'src.transcription.handler' has no attribute 'yt_dlp'` — correct RED state, since the stub handler has no implementation and doesn't import `yt_dlp`.
