Test fails cleanly at the stub's `NotImplementedError`.

```
FILE: tests/unit/test_pipeline_completion_logging.py
```

The test fails with `NotImplementedError: monitoring handler not yet implemented` — confirming RED. The test:

- Writes a `PipelineRun` record to S3 with known values (11 sources, 47 items, 8 above threshold, 3 transcription jobs, $2.47 cost)
- Calls `monitoring.handler.handler()` with mocked CloudWatch and SES at AWS boundaries
- Asserts that each of the five required metric values appears in the captured log output
