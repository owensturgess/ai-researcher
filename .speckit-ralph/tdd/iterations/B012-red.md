The test fails correctly. `yt_dlp.YoutubeDL` is stubbed to `None` in conftest (expected for tests that don't patch it), so calling it raises `TypeError` — proving the handler has no `content_format=audio` branch that routes to AWS Transcribe. The test is in proper RED state.

```
FILE: tests/unit/test_podcast_transcription.py
```

The test fails because `handler()` unconditionally calls `yt_dlp.YoutubeDL` even for `content_format=audio` items — the podcast AWS Transcribe code path doesn't exist yet. GREEN requires branching on `content_format` and implementing the Transcribe workflow.
