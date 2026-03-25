Reviewing the test against all 8 checklist items:

1. **Behavior-based naming** — `test_load_sources_raises_when_config_contains_duplicate_source_ids` describes observable behavior (raises on duplicate IDs), not implementation. ✅

2. **Public interface only** — Calls `load_sources(config_path: str)` from `src/ingestion/config.py`, exactly as documented in the interface spec. ✅

3. **Survives refactor** — Only asserts on the raised exception type and message. A full rewrite of the internals that preserves the contract would still pass. ✅

4. **Mocks only at system boundaries** — No mocks at all. Uses `tmp_path` to exercise the real filesystem boundary, which is appropriate since `load_sources` takes a file path. ✅

5. **No unmocked external deps** — The URLs in the YAML are never fetched; they're config values. No network calls are made. ✅

6. **One logical assertion** — Single `pytest.raises(ValueError, match="duplicate")`. Tests exactly one outcome. ✅

7. **Independence** — `tmp_path` is a per-test fixture; no shared mutable state or ordering dependency. ✅

8. **Meaningful failure** — A failure would produce `Failed: DID NOT RAISE <class 'ValueError'>` or a match failure with the actual error message shown, making the broken behavior immediately clear. ✅

```
VALIDATION_RESULT: PASS
```
