Reviewing the test against all 8 checklist items:

**1. Behavior-based naming** — Name describes observable behavior (item preserved with failed flag when both subtitle and audio transcription fail). ✓

**2. Public interface only** — Test calls `handler(event, None)` from `src.transcription.handler`, which is the documented public entry point. ✓

**3. Survives refactor** — Test drives through the SQS event interface and asserts on S3 state + return dict. Internal rewrites wouldn't break this. ✓

**4. Mocks only at system boundaries** — `yt_dlp.YoutubeDL` is an external library; patching it at `src.transcription.handler.yt_dlp.YoutubeDL` is the correct system boundary. No internal collaborators are mocked. ✓

**5. No unmocked external deps** — S3 is covered by `@mock_aws` (moto). AWS Transcribe (a potential fallback code path) is also intercepted by `@mock_aws` in moto v4+. yt-dlp is mocked. ✓

**6. One logical assertion** — All assertions target the same observable outcome: "transcription failure leaves the item intact in S3 with `transcript_status=failed`." The handler return value and the S3 state are two facets of the same outcome, not independent behaviors. ✓

**7. Independence** — Uses `@mock_aws` for isolated S3, `monkeypatch` for env vars, no shared mutable state, no ordering dependencies. ✓

**8. Meaningful failure** — Assertion messages would clearly surface which field was wrong (e.g., `transcript_status` not set to `'failed'`, or item fields dropped from S3). ✓

```
VALIDATION_RESULT: PASS
```
