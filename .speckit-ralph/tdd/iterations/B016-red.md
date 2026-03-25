```
FILE: tests/unit/test_youtube_transcription_failure.py
```

The test:
- Puts a YouTube `ContentItem` (with `transcript_status=pending`) in S3
- Mocks `yt_dlp.YoutubeDL.extract_info` to raise an exception (no subtitles + audio fails)
- Calls `handler(event, None)`
- Asserts `result["transcript_status"] == "failed"`
- Reads the updated item back from S3 and asserts `title`, `source_name`, `original_url` are preserved and `transcript_status == "failed"`

This will fail immediately since the current `handler` has no failure-path logic that writes `transcript_status=failed` back to S3.
