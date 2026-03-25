The test fails correctly — `NoSuchKey` because the stub handler doesn't write the PipelineRun record to S3. This is the right failure for a RED test.

```
FILE: tests/unit/test_pipeline_run_metadata.py
```

The test fails with `NoSuchKey` when trying to read `pipeline-runs/2026-03-24/run.json` from S3 — exactly the right RED failure, since the `handler` stub returns `{}` and writes nothing.

**What changed from the previous version:**

| Issue | Fix |
|---|---|
| Rule 4: mocked `load_sources` (internal) | Writes a real `sources.yaml` via `tmp_path`; path passed via `SOURCES_CONFIG` env var |
| Rule 4: mocked `rss.ingest` / `web.ingest` (internal) | Mocks `feedparser.parse` (external library network call) and `urllib.request.urlopen` (network boundary) |
| Rule 3: patches tightly coupled to module layout | Patches target external libraries, not internal module paths — survives any internal refactor |
| Rule 6: `sources_succeeded >= 0` (meaningless) | `sources_succeeded == 2` (specific expected value) |
