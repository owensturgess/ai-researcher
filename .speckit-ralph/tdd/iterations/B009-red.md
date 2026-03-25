Both files already exist on disk from a previous session — the RED test and GREEN implementation for B009 are complete. The test at `tests/unit/test_youtube_ingestion.py` is already written and matches the behavior under test exactly.

```
FILE: tests/unit/test_youtube_ingestion.py
```

The test was already written in a prior session (visible as untracked in git status). It:
- Mocks `googleapiclient.discovery.build` at the external API boundary
- Calls `ingest(source, since)` through the public interface
- Asserts `content_format == "video"`, correct `source_id`, `title`, `published_date`, and `original_url` containing the video ID

The B009-red.md, B009-green.md, and B009-validate.md iteration files also already exist, indicating this behavior has progressed through all TDD phases. No action needed — the RED step for B009 is complete.
