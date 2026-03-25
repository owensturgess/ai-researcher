Test passes.

```
FILE: src/transcription/handler.py
```

The implementation adds a `content_format` branch in `handler()`:
- `"audio"` → `_transcribe_audio()`: downloads audio via `urllib.request.urlopen`, uploads to S3, starts an AWS Transcribe job, polls until COMPLETED, parses the `TranscriptFileUri` to get the S3 key, reads the transcript JSON, and returns the text.
- Everything else (video) → existing `yt_dlp` path unchanged.
