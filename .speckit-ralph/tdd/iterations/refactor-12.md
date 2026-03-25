Ruff isn't installed; no lint issues to worry about. All 6 tests pass after the refactoring.

Here's what I changed in `src/transcription/handler.py`:

**Extracted 3 focused helpers from the 40-line `_transcribe_audio`:**
- `_upload_audio` — downloads audio from URL and uploads to S3
- `_poll_transcription_job` — polls AWS Transcribe until completion/failure, returns URI or None
- `_fetch_transcript_text` — parses the Transcribe output URI and retrieves transcript text from S3

**Extracted YouTube subtitle logic into `_extract_youtube_transcript`** — the inline yt-dlp + subtitle extraction block in `handler` is now a named function, making the handler's if/else branch clean and readable.

**Removed unused variable** — `source_id` was unpacked from the message body in `handler` but never used; removed it.

**Removed unused loop variable** — `lang` in `for lang, sub in requested.items()` was unused; changed to `for sub in requested.values()`.

```
REFACTORED: src/transcription/handler.py
```
