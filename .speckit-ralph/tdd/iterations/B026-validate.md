Reviewing against all 8 checklist items:

1. **Behavior-based naming** — `test_updated_context_prompt_file_is_returned_on_next_call_without_code_changes` describes the observable behavior (hot reload without code changes). ✓

2. **Public interface only** — imports only `load_context_prompt` from `src/shared/config.py`, which is explicitly listed in the interfaces. No private attributes accessed. ✓

3. **Survives refactor** — test only cares that the return value reflects current disk contents per call. Any implementation that satisfies that contract passes. ✓

4. **Mocks only at system boundaries** — no mocking at all. Uses `tmp_path` (real filesystem via pytest fixture). Filesystem is a legitimate system boundary; using actual temp files is correct. ✓

5. **No unmocked external deps** — no network, no real AWS, no external services. ✓

6. **One logical assertion** — three assert statements, all testing a single logical claim: "each call reads fresh from disk." First assert is a setup sanity check; second and third together verify the hot-reload contract. Tightly coupled to one behavior. ✓

7. **Independence** — `tmp_path` is a per-test isolated fixture. No shared mutable state, no ordering dependency. ✓

8. **Meaningful failure** — all three asserts include descriptive messages quoting the actual return value. ✓

```
VALIDATION_RESULT: PASS
```
